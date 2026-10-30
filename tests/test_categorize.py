"""Module 2 tests — fallback mapping, validation, JSON parsing, and applying categories.

No live API calls: these test the deterministic paths so they are fast and reliable.
"""
import pandas as pd
import pytest

from src.categorize import (
    BUCKETS,
    DISCRETIONARY,
    apply_categories,
    fallback_bucket,
    fallback_mapping,
    is_discretionary,
    _parse_json_object,
    _validate_and_fill,
)

SAMPLE_MCC = {
    "5812": "Eating Places and Restaurants",
    "5411": "Grocery Stores, Supermarkets",
    "4900": "Utilities Electric Gas Water Sanitary",
    "3000": "Some Airline",
    "9999": "Totally Unknown Thing",
}


def test_fallback_all_valid_buckets():
    mapping = fallback_mapping(SAMPLE_MCC)
    assert set(mapping) == set(SAMPLE_MCC)
    assert all(b in BUCKETS for b in mapping.values())


def test_fallback_specific_rules():
    assert fallback_bucket("Eating Places and Restaurants") == "Dining"
    assert fallback_bucket("Grocery Stores, Supermarkets") == "Groceries"
    assert fallback_bucket("Totally Unknown Thing") == "Other"


def test_is_discretionary_matches_set():
    assert is_discretionary("Dining") is True
    assert is_discretionary("Groceries") is False
    assert DISCRETIONARY.issubset(set(BUCKETS))


def test_parse_json_object_strips_fences():
    assert _parse_json_object('```json\n{"5812": "Dining"}\n```') == {"5812": "Dining"}
    assert _parse_json_object('Here you go: {"a": 1} thanks') == {"a": 1}


def test_validate_and_fill_replaces_bad_buckets():
    raw = {"5812": "Dining", "5411": "NotARealBucket"}  # 4900/3000/9999 missing
    clean = _validate_and_fill(raw, SAMPLE_MCC)
    assert clean["5812"] == "Dining"           # valid kept
    assert clean["5411"] == "Groceries"        # invalid -> fallback
    assert all(b in BUCKETS for b in clean.values())
    assert set(clean) == set(SAMPLE_MCC)        # every code present


def test_apply_categories_adds_columns():
    df = pd.DataFrame({"mcc": pd.array([5812, 5411], dtype="Int64"), "amount": [10.0, 20.0]})
    mapping = {"5812": "Dining", "5411": "Groceries"}
    out = apply_categories(df, mapping)
    assert out["category"].tolist() == ["Dining", "Groceries"]
    assert out["is_discretionary"].tolist() == [True, False]
