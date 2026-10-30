"""Module 1 — Data Logistics: load, clean, join, and filter the raw ClearLedger data.

All steps here are row-wise and deterministic (no network, no LLM). The public entry
point is `load_user(client_id, cfg)`, which returns one tidy, joined frame for a user.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Columns each raw file MUST contain. Missing any -> explicit, early failure.
REQUIRED_COLUMNS = {
    "transactions": ["id", "date", "client_id", "card_id", "amount", "mcc"],
    "users": ["id", "monthly_discretionary_limits"],
    "cards": ["id", "client_id", "credit_limit"],
}


# --------------------------------------------------------------------------- #
# Cleaning helpers
# --------------------------------------------------------------------------- #
def parse_currency(values):
    """Convert '$1,755' / '$4.81' style text into float.

    Accepts a single value or an iterable. Blank / None / unparseable -> NaN
    (never raises), so bad rows degrade gracefully instead of crashing a load.
    """
    is_scalar = np.isscalar(values) or values is None
    s = pd.Series([values] if is_scalar else values, dtype="object")
    cleaned = (
        s.astype(str)
        .str.replace(r"[$,]", "", regex=True)
        .str.strip()
        .replace({"": None, "nan": None, "NaN": None, "None": None})
    )
    out = pd.to_numeric(cleaned, errors="coerce")
    return float(out.iloc[0]) if is_scalar else out


def _check_columns(df: pd.DataFrame, name: str) -> None:
    """Guardrail: fail early and clearly if a required column is missing."""
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    if missing:
        raise ValueError(f"{name}.csv is missing required columns: {missing}")


# --------------------------------------------------------------------------- #
# Individual file loaders
# --------------------------------------------------------------------------- #
def load_transactions(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    _check_columns(df, "transactions")
    df["amount"] = parse_currency(df["amount"])
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df["mcc"] = df["mcc"].astype("Int64")  # nullable int so the str-cast join is clean
    return df


def load_users(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    _check_columns(df, "users")
    for col in ["monthly_discretionary_limits", "per_capita_income",
                "yearly_income", "total_debt"]:
        if col in df.columns:
            df[col] = parse_currency(df[col])
    return df


def load_cards(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    _check_columns(df, "cards")
    df["credit_limit"] = parse_currency(df["credit_limit"])
    return df


def load_mcc_codes(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)  # {"5812": "Eating Places and Restaurants", ...}


# --------------------------------------------------------------------------- #
# Join + filter
# --------------------------------------------------------------------------- #
def build_master(transactions, users, cards, mcc_codes) -> pd.DataFrame:
    """Join transactions -> mcc description, user limit, and card type."""
    df = transactions.copy()

    # mcc (int) -> string key -> description. Unmatched codes become NaN (reported later).
    df["mcc_description"] = df["mcc"].astype(str).map(mcc_codes)

    df = df.merge(
        users[["id", "monthly_discretionary_limits"]].rename(
            columns={"id": "client_id",
                     "monthly_discretionary_limits": "monthly_discretionary_limit"}),
        on="client_id", how="left",
    )
    df = df.merge(
        cards[["id", "card_type"]].rename(columns={"id": "card_id"}),
        on="card_id", how="left",
    )
    return df


def validation_report(master: pd.DataFrame) -> dict:
    """Quick health metrics used by tests and by the __main__ smoke check."""
    return {
        "rows": int(len(master)),
        "amount_parse_rate": float(master["amount"].notna().mean()),
        "date_parse_rate": float(master["date"].notna().mean()),
        "mcc_coverage": float(master["mcc_description"].notna().mean()),
    }


def load_master(cfg: dict) -> pd.DataFrame:
    """Load all four files and return the full joined frame."""
    data_dir = Path(cfg["paths"]["data_dir"])
    tx = load_transactions(data_dir / "transactions.csv")
    users = load_users(data_dir / "users.csv")
    cards = load_cards(data_dir / "cards.csv")
    mcc = load_mcc_codes(data_dir / "mcc_codes.json")
    return build_master(tx, users, cards, mcc)


def load_user(client_id: int, cfg: dict, master: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return the joined, cleaned transactions for one user.

    Pass an already-loaded `master` to avoid re-reading the 700k-row file.
    Raises if the user has no transactions (guardrail).
    """
    if master is None:
        master = load_master(cfg)
    user_df = master[master["client_id"] == client_id].copy()
    if user_df.empty:
        raise ValueError(f"No transactions found for user {client_id}")
    return user_df


if __name__ == "__main__":
    # Smoke check: load everything and summarize the target user.
    from src.config import load_config

    cfg = load_config()
    master = load_master(cfg)
    print("Validation report:", validation_report(master))
    u = load_user(cfg["target_user"], cfg, master=master)
    print(f"User {cfg['target_user']}: {len(u):,} transactions, "
          f"total spend ${u['amount'].sum():,.2f}, "
          f"limit ${u['monthly_discretionary_limit'].iloc[0]:,.0f}")
