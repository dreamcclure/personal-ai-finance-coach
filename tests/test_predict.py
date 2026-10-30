"""Module 3 tests — feature building and prediction on synthetic, controlled data."""
import numpy as np
import pandas as pd
import pytest

from src.features import (
    FEATURES,
    build_monthly_features,
    user_month_row,
)
from src.predict import predict_month_end, train_models


def _synthetic_master(n_users=6, n_months=18, seed=0):
    """Build a categorized transaction frame: known discretionary spend per user-month."""
    rng = np.random.default_rng(seed)
    rows = []
    for uid in range(1, n_users + 1):
        base = 500 + uid * 100
        for k in range(n_months):
            period = pd.Timestamp("2018-01-01") + pd.DateOffset(months=k)
            # a few transactions across the month (days 5, 12, 20, 27)
            for day in (5, 12, 20, 27):
                rows.append({
                    "client_id": uid,
                    "date": period + pd.Timedelta(days=day - 1),
                    "amount": base / 4 + rng.normal(0, 10),
                    "mcc": 5812,
                    "category": "Dining",
                    "is_discretionary": True,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def monthly():
    return build_monthly_features(_synthetic_master(), ref_day=15)


def test_mtd_less_than_full(monthly):
    # MTD (through day 15) should never exceed the full month total.
    assert (monthly["mtd_disc"] <= monthly["full_month_disc"] + 1e-6).all()


def test_first_month_dropped(monthly):
    # History features require a prior month, so each user's first month is dropped.
    # 18 months - 1 per user.
    assert monthly.groupby("client_id").size().eq(17).all()


def test_history_features_present(monthly):
    assert monthly["prev_month_disc"].notna().all()
    assert monthly["avg_monthly_disc"].notna().all()


def test_train_models_returns_metrics_and_model(monthly):
    res = train_models(monthly, seed=42)
    assert {"GradientBoosting", "LinearRegression"} <= set(res["metrics"])
    for m in res["metrics"].values():
        assert m["MAE"] >= 0 and m["RMSE"] >= 0
    preds = res["model"].predict(monthly[FEATURES].head())
    assert (preds > 0).all()


def test_predict_month_end_projection(monthly):
    res = train_models(monthly, seed=42)
    cfg = {"reference_day": 15, "target_user": 3, "random_seed": 42}
    out = predict_month_end(res["model"], monthly, cfg, client_id=3)
    assert out["projected_month_end"] >= out["mtd_discretionary"]  # cannot go below MTD
    assert out["ref_day"] == 15
    assert out["client_id"] == 3


def test_user_month_row_missing_returns_none(monthly):
    assert user_month_row(monthly, client_id=999, period=pd.Period("2019-06", "M")) is None
