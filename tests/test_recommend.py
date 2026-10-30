"""Module 4 tests — recommendations + category trend, plus a headless dashboard run."""
import pandas as pd
import pytest

from src.features import category_time_series
from src.recommend import build_recommendations


def test_recommendation_flags_over_limit():
    spend = pd.Series({"Dining": 400, "Shopping": 300, "Travel": 100})
    recs = build_recommendations(spend, projected=1200, limit=1000)
    assert "exceed" in recs[0]["title"].lower()
    # top categories appear, biggest first
    assert "Dining" in recs[1]["title"]


def test_recommendation_under_limit():
    spend = pd.Series({"Dining": 100})
    recs = build_recommendations(spend, projected=500, limit=1000)
    assert "under" in recs[0]["title"].lower()


def test_category_time_series_shape():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2019-01-05", "2019-01-20", "2019-02-10"]),
        "amount": [10.0, 20.0, 5.0],
        "category": ["Dining", "Dining", "Shopping"],
        "is_discretionary": [True, True, True],
    })
    ts = category_time_series(df, discretionary_only=True)
    assert ts.loc["2019-01-01", "Dining"] == 30.0   # two Jan dining txns summed
    assert ts.loc["2019-02-01", "Shopping"] == 5.0
    assert list(ts.index) == [pd.Timestamp("2019-01-01"), pd.Timestamp("2019-02-01")]


def test_dashboard_runs_without_error():
    """Execute the whole Streamlit app headlessly and assert no exception."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app/app.py", default_timeout=120).run()
    assert not at.exception, f"Dashboard raised: {at.exception}"
    labels = [m.label for m in at.metric]
    assert any("MTD" in l for l in labels)
    assert any("limit" in l.lower() for l in labels)
