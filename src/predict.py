"""Module 3b — Month-end spend prediction.

Trains a GradientBoostingRegressor (with a LinearRegression baseline) on all users'
monthly histories, reports MAE/RMSE/R2 on a held-out split, then projects the target
user's month-end discretionary spend vs. their limit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split

from src.features import (
    FEATURES,
    TARGET,
    build_monthly_features,
    get_reference_day,
    user_month_row,
)


def _metrics(y_true, y_pred) -> dict:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),   # type: ignore[arg-type]
        "RMSE": float(root_mean_squared_error(y_true, y_pred)),  # type: ignore[arg-type]
        "R2": float(r2_score(y_true, y_pred)),               # type: ignore[arg-type]
    }


def train_models(monthly: pd.DataFrame, seed: int = 42) -> dict:
    """Train model + baseline on all-user monthly data; report held-out metrics.

    Returns the final model refit on ALL rows (standard once evaluation is done).
    """
    X, y = monthly[FEATURES], monthly[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.20, random_state=seed)

    model = GradientBoostingRegressor(random_state=seed)
    baseline = LinearRegression()
    model.fit(X_tr, y_tr)
    baseline.fit(X_tr, y_tr)

    results = {
        "metrics": {
            "GradientBoosting": _metrics(y_te, model.predict(X_te)),
            "LinearRegression": _metrics(y_te, baseline.predict(X_te)),
        },
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
    }
    # Refit the chosen model on all available data for deployment/runtime use.
    results["model"] = GradientBoostingRegressor(random_state=seed).fit(X, y)
    return results


def predict_month_end(model, monthly: pd.DataFrame, cfg: dict,
                      client_id: int) -> dict:
    """Project total discretionary spend for a user's most-recent active month.

    Different users' histories end at different times, so the "current month" is that
    user's LATEST active month. The simulated mid-month cutoff day comes from
    cfg['reference_day'] (e.g. the 15th), applied uniformly.
    """
    ref_day = get_reference_day(cfg)
    user_rows = monthly[monthly["client_id"] == client_id]
    if user_rows.empty:
        raise ValueError(f"No feature rows for user {client_id}")
    period = user_rows["_ym"].max()          # user's most recent active month
    row = user_month_row(monthly, client_id, period)

    mtd = float(row["mtd_disc"].iloc[0])
    projected = float(model.predict(row[FEATURES])[0])
    projected = max(projected, mtd)  # cannot end below what's already spent

    return {
        "client_id": client_id,
        "reference_month": str(period),
        "reference_date": f"{period}-{ref_day:02d}",
        "ref_day": ref_day,
        "days_in_month": int(row["days_in_month"].iloc[0]),
        "mtd_discretionary": round(mtd, 2),
        "projected_month_end": round(projected, 2),
        "avg_monthly_disc": round(float(row["avg_monthly_disc"].iloc[0]), 2),
    }


if __name__ == "__main__":
    from src.config import load_config
    from src.data_loader import load_master, load_mcc_codes
    from src.categorize import apply_categories, categorize_mcc_codes

    cfg = load_config()
    master = load_master(cfg)
    mcc = load_mcc_codes(cfg["paths"]["data_dir"] / "mcc_codes.json")
    master = apply_categories(master, categorize_mcc_codes(mcc, cfg))

    monthly = build_monthly_features(master, ref_day=get_reference_day(cfg))
    print(f"Training rows (user-months): {len(monthly):,}")

    res = train_models(monthly, seed=cfg["random_seed"])
    for name, m in res["metrics"].items():
        print(f"  {name:18s} MAE ${m['MAE']:,.0f} | RMSE ${m['RMSE']:,.0f} | R2 {m['R2']:.3f}")

    out = predict_month_end(res["model"], monthly, cfg, cfg["target_user"])
    limit = float(master.loc[master.client_id == cfg["target_user"],
                             "monthly_discretionary_limit"].iloc[0])
    print(f"\nUser {cfg['target_user']} @ {out['reference_date']} (day {out['ref_day']}/"
          f"{out['days_in_month']}):")
    print(f"  MTD discretionary : ${out['mtd_discretionary']:,.0f}")
    print(f"  Projected month-end: ${out['projected_month_end']:,.0f}")
    print(f"  Monthly limit      : ${limit:,.0f}  ->  "
          f"{'OVER' if out['projected_month_end'] > limit else 'within'} budget")
