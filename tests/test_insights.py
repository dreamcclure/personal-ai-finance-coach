"""Module 6 tests — unusual-charge and recurring-merchant detection."""
import pandas as pd

from src.insights import recurring_merchants, unusual_charges


def test_unusual_charge_flagged():
    # 10 normal ~$20 Dining charges + one $2000 outlier in the same category.
    rows = [{"date": pd.Timestamp("2019-01-01"), "amount": 20.0, "category": "Dining",
             "merchant_id": 1, "merchant_city": "Bronx"} for _ in range(10)]
    rows.append({"date": pd.Timestamp("2019-02-01"), "amount": 2000.0, "category": "Dining",
                 "merchant_id": 2, "merchant_city": "Bronx"})
    df = pd.DataFrame(rows)
    flagged = unusual_charges(df)
    assert len(flagged) == 1
    assert flagged.iloc[0]["amount"] == 2000.0


def test_no_flag_without_enough_history():
    # Only 2 charges in the category -> not enough history to call anything unusual.
    df = pd.DataFrame({"date": pd.to_datetime(["2019-01-01", "2019-01-02"]),
                       "amount": [10.0, 5000.0], "category": ["Travel", "Travel"],
                       "merchant_id": [1, 2], "merchant_city": ["A", "B"]})
    assert unusual_charges(df, min_count=5).empty


def test_recurring_merchant_detected():
    # Merchant 100: ~monthly $15 charge for 12 months (stable) -> recurring.
    # Merchant 200: a couple of one-off, varied charges -> not recurring.
    rows = []
    for k in range(12):
        rows.append({"date": pd.Timestamp("2019-01-15") + pd.DateOffset(months=k),
                     "amount": 15.0, "merchant_id": 100, "category": "Subscriptions",
                     "merchant_city": "ONLINE"})
    rows += [{"date": pd.Timestamp("2019-03-01"), "amount": 200.0, "merchant_id": 200,
              "category": "Shopping", "merchant_city": "Bronx"},
             {"date": pd.Timestamp("2019-07-01"), "amount": 40.0, "merchant_id": 200,
              "category": "Shopping", "merchant_city": "Bronx"}]
    df = pd.DataFrame(rows)
    rec = recurring_merchants(df)
    assert 100 in rec.index
    assert 200 not in rec.index
    assert rec.loc[100, "typical_amount"] == 15.0
