"""Module 1 tests — currency parsing, joins, and user filtering."""
import math

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data_loader import (
    build_master,
    load_master,
    load_user,
    parse_currency,
    validation_report,
    _check_columns,
)


# --------------------------------------------------------------------------- #
# Fast, pure-function unit tests (no data files needed)
# --------------------------------------------------------------------------- #
def test_parse_currency_scalar():
    assert parse_currency("$4.81") == 4.81
    assert parse_currency("$1,755") == 1755.0
    assert parse_currency("$0") == 0.0


def test_parse_currency_blank_is_nan():
    assert math.isnan(parse_currency(""))
    assert math.isnan(parse_currency(None))
    assert math.isnan(parse_currency("n/a"))


def test_parse_currency_series():
    out = parse_currency(["$1,000", "$2.50", ""])
    assert list(out[:2]) == [1000.0, 2.5]
    assert math.isnan(out.iloc[2])
    assert pd.api.types.is_float_dtype(out)


def test_check_columns_raises_on_missing():
    bad = pd.DataFrame({"id": [1]})  # missing amount, mcc, etc.
    with pytest.raises(ValueError, match="missing required columns"):
        _check_columns(bad, "transactions")


def test_build_master_casts_mcc_and_joins():
    tx = pd.DataFrame({
        "id": [1, 2], "date": pd.to_datetime(["2019-10-01", "2019-10-02"]),
        "client_id": [1696, 1696], "card_id": [10, 10],
        "amount": [4.81, 87.09], "mcc": pd.array([5812, 4900], dtype="Int64"),
    })
    users = pd.DataFrame({"id": [1696], "monthly_discretionary_limits": [1755.0]})
    cards = pd.DataFrame({"id": [10], "card_type": ["Debit"]})
    mcc = {"5812": "Eating Places and Restaurants", "4900": "Utilities"}

    master = build_master(tx, users, cards, mcc)
    assert master["mcc_description"].tolist() == ["Eating Places and Restaurants", "Utilities"]
    assert master["monthly_discretionary_limit"].tolist() == [1755.0, 1755.0]
    assert master["card_type"].tolist() == ["Debit", "Debit"]


# --------------------------------------------------------------------------- #
# Integration tests against the real data files (loaded once)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def master(cfg):
    return load_master(cfg)


def test_master_health(master):
    rep = validation_report(master)
    # Health check, not an exact count: the repo ships a ~30k-row demo dataset
    # (customer 1696); the full dataset is ~700k rows. Both are "healthy".
    assert rep["rows"] > 10_000
    assert rep["amount_parse_rate"] > 0.99      # nearly all amounts parsed
    assert rep["date_parse_rate"] > 0.99
    assert rep["mcc_coverage"] > 0.99           # nearly all mcc codes matched


def test_amount_is_numeric(master):
    assert pd.api.types.is_float_dtype(master["amount"])


def test_target_user_has_expected_rows(cfg, master):
    u = load_user(cfg["target_user"], cfg, master=master)
    assert len(u) == 30_672
    assert u["monthly_discretionary_limit"].notna().all()


def test_unknown_user_raises(cfg, master):
    with pytest.raises(ValueError, match="No transactions"):
        load_user(-1, cfg, master=master)
