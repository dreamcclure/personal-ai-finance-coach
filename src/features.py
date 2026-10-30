"""Module 3a — Feature engineering for the month-end spend regression.

We turn the transaction log into one row per (user, calendar-month), with features
that are KNOWN partway through the month (as of a fixed `ref_day`, e.g. the 15th) and
a target of the FULL-month discretionary spend. This lets a model learn:
    "given spend-so-far + this user's history, what will the month total be?"

Everything here is leakage-safe: no feature uses spend after `ref_day`.
"""
from __future__ import annotations

import pandas as pd

# The columns fed to the regression model (order matters for predict()).
FEATURES = ["mtd_disc", "mtd_txns", "prev_month_disc",
            "avg_monthly_disc", "days_in_month", "month"]
TARGET = "full_month_disc"


def get_reference_day(cfg: dict, default: int = 15) -> int:
    """Simulated mid-month cutoff day used for MTD (the "as of the Nth" point).

    Reads `reference_day` from config; falls back to `default` if missing/invalid,
    and clamps to 1..28 so it is a valid day in every month (including February).
    """
    try:
        day = int(cfg.get("reference_day", default))
    except (TypeError, ValueError):
        return default
    return min(max(day, 1), 28)


def _monthly_aggregate(df: pd.DataFrame, ref_day: int) -> pd.DataFrame:
    """Aggregate categorized transactions to one row per (client_id, month)."""
    d = df.copy()
    d = d[d["date"].notna()]
    day = d["date"].dt.day
    disc = d["is_discretionary"].fillna(False)

    # Helper columns: discretionary amounts, and the month-to-date slice (day <= ref_day).
    d["_disc_amt"] = d["amount"].where(disc, 0.0)
    d["_disc_amt_mtd"] = d["_disc_amt"].where(day <= ref_day, 0.0)
    d["_disc_txn_mtd"] = (disc & (day <= ref_day)).astype(int)
    d["_ym"] = d["date"].dt.to_period("M")
    d["_days_in_month"] = d["date"].dt.days_in_month
    d["_month"] = d["date"].dt.month

    g = d.groupby(["client_id", "_ym"]).agg(
        full_month_disc=("_disc_amt", "sum"),
        mtd_disc=("_disc_amt_mtd", "sum"),
        mtd_txns=("_disc_txn_mtd", "sum"),
        days_in_month=("_days_in_month", "first"),
        month=("_month", "first"),
    ).reset_index()
    return g


def _add_history_features(monthly: pd.DataFrame) -> pd.DataFrame:
    """Add prior-month total and expanding average of prior months (per user)."""
    m = monthly.sort_values(["client_id", "_ym"]).copy()
    grp = m.groupby("client_id")["full_month_disc"]
    m["prev_month_disc"] = grp.shift(1)
    # Mean of all STRICTLY prior months (shift(1) so the current month is excluded).
    m["avg_monthly_disc"] = grp.apply(lambda s: s.shift(1).expanding().mean()).reset_index(level=0, drop=True)
    return m


def build_monthly_features(df: pd.DataFrame, ref_day: int) -> pd.DataFrame:
    """Full pipeline: categorized transactions -> per-user-month feature rows.

    Rows without history (a user's first month) are dropped, since prev/avg are NaN.
    """
    monthly = _monthly_aggregate(df, ref_day)
    monthly = _add_history_features(monthly)
    monthly = monthly.dropna(subset=["prev_month_disc", "avg_monthly_disc"]).reset_index(drop=True)
    return monthly


def user_month_row(monthly: pd.DataFrame, client_id: int, period: pd.Period) -> pd.DataFrame | None:
    """Return the single feature row for one user's given month, or None if absent."""
    sel = monthly[(monthly["client_id"] == client_id) & (monthly["_ym"] == period)]
    return sel if not sel.empty else None


def category_time_series(df: pd.DataFrame, discretionary_only: bool = True) -> pd.DataFrame:
    """Monthly spend per category as a (month x category) table, for the trend chart."""
    d = df[df["date"].notna()].copy()
    if discretionary_only:
        d = d[d["is_discretionary"].fillna(False)]
    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    ts = (d.groupby(["month", "category"])["amount"].sum()
            .unstack(fill_value=0.0).sort_index())
    return ts
