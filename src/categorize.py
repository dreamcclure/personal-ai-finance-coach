"""Module 2 — LLM Transaction Categorization.

Design: the LLM classifies the ~109 unique MCC *descriptions* into a small set of
spending buckets ONE time, and the result is cached to disk. Transactions are then
categorized by a cheap dictionary join — never a per-transaction API call.

A deterministic keyword fallback guarantees the app runs even with no API access.
`is_discretionary` is derived from the bucket (fixed rule) for consistency.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from openai import OpenAI

# The allowed spending buckets. The LLM must choose exactly one of these per code.
BUCKETS = [
    "Housing", "Utilities", "Groceries", "Transportation", "Healthcare", "Insurance",
    "Dining", "Entertainment", "Shopping", "Travel", "Personal Care", "Subscriptions",
    "Other",
]

# Buckets a user can realistically cut => count toward the discretionary limit.
DISCRETIONARY = {"Dining", "Entertainment", "Shopping", "Travel",
                 "Personal Care", "Subscriptions"}

# Keyword rules for the offline fallback (checked in order; first match wins).
_FALLBACK_RULES = [
    ("Groceries", ["grocer", "supermarket", "food stores"]),
    ("Dining", ["restaurant", "eating", "fast food", "bar", "caterer", "drinking"]),
    ("Utilities", ["utilit", "electric", "gas company", "water", "telecom",
                   "cable", "phone", "telephone"]),
    ("Travel", ["hotel", "lodging", "airline", "air carrier", "cruise", "travel",
                "car rental", "motel", "resort"]),
    ("Transportation", ["service station", "fuel", "automotive", "auto ", "toll",
                        "parking", "taxi", "transportation", "bridge", "railroad",
                        "bus ", "transit"]),
    ("Healthcare", ["medical", "health", "doctor", "hospital", "pharmacy", "drug",
                    "dental", "optical", "physician"]),
    ("Insurance", ["insurance"]),
    ("Housing", ["real estate", "rent", "housing", "lumber", "hardware",
                 "home supply", "furniture"]),
    ("Entertainment", ["amusement", "entertainment", "theater", "theatrical",
                       "motion picture", "recreation", "sport", "golf", "billiard",
                       "bowling", "carnival", "movie"]),
    ("Subscriptions", ["subscription", "digital goods", "software", "streaming",
                       "cable", "book"]),
    ("Personal Care", ["salon", "spa", "beauty", "barber", "personal care",
                       "health and beauty"]),
    ("Shopping", ["store", "retail", "shop", "apparel", "clothing", "department",
                  "jewelry", "electronics", "merchandise", "catalog"]),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def is_discretionary(bucket: str) -> bool:
    return bucket in DISCRETIONARY


def fallback_bucket(description: str) -> str:
    """Rule-based bucket for one MCC description. Always returns a valid bucket."""
    text = (description or "").lower()
    for bucket, keywords in _FALLBACK_RULES:
        if any(kw in text for kw in keywords):
            return bucket
    return "Other"


def fallback_mapping(mcc_codes: dict) -> dict:
    """Offline mapping: {code: bucket} using keyword rules for every code."""
    return {code: fallback_bucket(desc) for code, desc in mcc_codes.items()}


def _parse_json_object(text: str) -> dict:
    """Parse a JSON object from an LLM reply, tolerating ```json fences/prose."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end + 1])


def get_client(cfg: dict) -> OpenAI:
    """OpenAI client pointed at the configured endpoint (gateway or direct)."""
    llm = cfg["llm"]
    return OpenAI(api_key=llm["api_key"], base_url=llm["base_url"] or None)


def _build_prompt(mcc_codes: dict) -> str:
    listing = "\n".join(f"{code}: {desc}" for code, desc in mcc_codes.items())
    return (
        "You are a personal-finance transaction categorizer. Assign each merchant "
        "category code (MCC) to EXACTLY ONE of these spending buckets:\n"
        f"{', '.join(BUCKETS)}.\n\n"
        "Return ONLY a JSON object mapping each MCC code (as a string) to its bucket "
        'name, e.g. {"5812": "Dining"}. No commentary, no markdown.\n\n'
        f"MCC codes:\n{listing}"
    )


def _validate_and_fill(raw: dict, mcc_codes: dict) -> dict:
    """Keep only valid buckets; fill missing/invalid codes via the fallback."""
    clean = {}
    for code in mcc_codes:
        bucket = raw.get(code) or raw.get(str(code))
        clean[code] = bucket if bucket in BUCKETS else fallback_bucket(mcc_codes[code])
    return clean


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def categorize_mcc_codes(mcc_codes: dict, cfg: dict, use_cache: bool = True,
                         use_llm: bool = True) -> dict:
    """Return {code: bucket} for all MCC codes, using cache -> LLM -> fallback.

    Order: (1) cached file if present, (2) one LLM call, (3) keyword fallback.
    Always writes the result to the cache file.
    """
    cache_file = Path(cfg["buckets_file"])

    if use_cache and cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    mapping = None
    if use_llm and cfg["llm"].get("api_key"):
        try:
            client = get_client(cfg)
            resp = client.chat.completions.create(
                model=cfg["llm"]["model"],
                messages=[{"role": "user", "content": _build_prompt(mcc_codes)}],
                temperature=0,
            )
            raw = _parse_json_object(resp.choices[0].message.content)
            mapping = _validate_and_fill(raw, mcc_codes)
        except Exception as e:  # any API/parse failure -> graceful fallback
            print(f"[categorize] LLM path failed ({type(e).__name__}); using fallback.")

    if mapping is None:
        mapping = fallback_mapping(mcc_codes)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
    return mapping


def apply_categories(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Add 'category' and 'is_discretionary' columns to a transactions frame."""
    df = df.copy()
    codes = df["mcc"].astype(str)
    df["category"] = codes.map(mapping).fillna("Other")
    df["is_discretionary"] = df["category"].map(is_discretionary)
    return df


if __name__ == "__main__":
    from src.config import load_config
    from src.data_loader import load_mcc_codes

    cfg = load_config()
    mcc = load_mcc_codes(cfg["paths"]["data_dir"] / "mcc_codes.json")
    mapping = categorize_mcc_codes(mcc, cfg, use_cache=False)  # force a fresh build
    counts = pd.Series(mapping).value_counts()
    print(f"Categorized {len(mapping)} MCC codes into {counts.size} buckets:")
    print(counts.to_string())
    print(f"\nCached to: {cfg['buckets_file']}")
