"""Module 6 — Enhancement insights (built after the core).

Two detectors, both pure/deterministic and grounded in a single user's transactions:
  1. unusual_charges()      — transactions far above the user's normal for that category.
  2. recurring_merchants()  — merchants billed repeatedly at a similar amount (subscriptions).

The "what-if savings" enhancement lives in the dashboard (interactive slider), since it is
purely a UI recomputation.
"""
from __future__ import annotations

import pandas as pd


def unusual_charges(df: pd.DataFrame, z: float = 3.0, min_count: int = 5,
                    top_n: int = 10) -> pd.DataFrame:
    """Flag transactions above (category mean + z * category std).

    Only categories with at least `min_count` transactions and nonzero variance are judged,
    so we never call a charge "unusual" without enough history to know what normal is.
    """
    d = df[df["amount"] > 0].dropna(subset=["category"]).copy()
    if d.empty:
        return d

    grp = d.groupby("category")["amount"]
    d["cat_mean"] = grp.transform("mean")
    d["cat_std"] = grp.transform("std")
    d["cat_count"] = grp.transform("count")
    d["threshold"] = d["cat_mean"] + z * d["cat_std"]

    flagged = d[(d["cat_count"] >= min_count) & (d["cat_std"] > 0)
                & (d["amount"] > d["threshold"])]
    cols = [c for c in ["date", "amount", "category", "merchant_city",
                        "mcc_description", "threshold"] if c in flagged.columns]
    return flagged.sort_values("amount", ascending=False)[cols].head(top_n)


def recurring_merchants(df: pd.DataFrame, min_occurrences: int = 6, cv_max: float = 0.15,
                        min_per_month: float = 0.5, top_n: int = 15) -> pd.DataFrame:
    """Detect merchants charged repeatedly at a stable amount (likely subscriptions).

    A merchant qualifies if it has >= `min_occurrences` charges, low amount variability
    (coefficient of variation <= `cv_max`), and a cadence of at least `min_per_month`.
    """
    d = df[df["amount"] > 0].dropna(subset=["merchant_id"]).copy()
    if d.empty:
        return pd.DataFrame()

    def _mode(s):
        m = s.mode()
        return m.iat[0] if not m.empty else None

    agg = d.groupby("merchant_id").agg(
        occurrences=("amount", "size"),
        typical_amount=("amount", "median"),
        mean_amt=("amount", "mean"),
        std_amt=("amount", "std"),
        first=("date", "min"),
        last=("date", "max"),
        category=("category", _mode),
        merchant_city=("merchant_city", _mode),
    )
    agg["cv"] = (agg["std_amt"] / agg["mean_amt"]).fillna(0.0)
    span_months = ((agg["last"] - agg["first"]).dt.days / 30.0).clip(lower=1)
    agg["per_month"] = agg["occurrences"] / span_months

    rec = agg[(agg["occurrences"] >= min_occurrences) & (agg["cv"] <= cv_max)
              & (agg["per_month"] >= min_per_month)]
    rec = rec.sort_values("typical_amount", ascending=False)
    cols = ["occurrences", "typical_amount", "category", "merchant_city", "per_month"]
    return rec[cols].head(top_n)
