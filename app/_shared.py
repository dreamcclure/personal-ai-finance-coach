"""Shared, cached data pipeline for the Streamlit pages (dashboard + chat coach).

Both `app/pages/1_Overview.py` and `app/pages/2_💬_Chat_Coach.py` import from here so
the heavy load/categorize/train pipeline runs at most once (via @st.cache_resource)
and the two pages always show consistent numbers.
"""
import sys
import uuid
from pathlib import Path

# Make the project root importable so `from src...` works under `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from src.categorize import BUCKETS, DISCRETIONARY, apply_categories, categorize_mcc_codes
from src.config import load_config
from src.data_loader import load_master, load_mcc_codes
from src.features import build_monthly_features, get_reference_day
from src.predict import predict_month_end, train_models


@st.cache_resource
def load_everything():
    """Load + categorize + build features + train once, cached across reruns/pages."""
    cfg = load_config()
    master = load_master(cfg)
    mcc = load_mcc_codes(cfg["paths"]["data_dir"] / "mcc_codes.json")
    master = apply_categories(master, categorize_mcc_codes(mcc, cfg))
    monthly = build_monthly_features(master, ref_day=get_reference_day(cfg))
    res = train_models(monthly, seed=cfg["random_seed"])
    return cfg, master, monthly, res


def get_user_view(cfg, master, monthly, model, uid):
    """Compute one user's frame, projection, limit, and this-month category spend."""
    user_df = master[master["client_id"] == uid].copy()
    proj = predict_month_end(model, monthly, cfg, uid)
    limit = float(user_df["monthly_discretionary_limit"].iloc[0])
    ref_period = pd.Period(proj["reference_month"], "M")
    ref_df = user_df[(user_df["date"].dt.to_period("M") == ref_period)
                     & (user_df["date"].dt.day <= proj["ref_day"])]
    cat_spend = (ref_df[ref_df["is_discretionary"].fillna(False)]
                 .groupby("category")["amount"].sum())
    return user_df, proj, limit, cat_spend


def new_entry_popover(uid: int, limit: float, reference_date: str) -> None:
    """The "+ New Entry" action, shared by both pages so it's identical everywhere.

    Session-only (st.session_state["manual_entries"]) — never touches the CSVs on
    disk. Appends to a list any page can fold into its own display data.
    """
    st.session_state.setdefault("manual_entries", [])
    with st.popover("+ New Entry"):
        st.caption("Session only — not saved to the source data.")
        with st.form("new_entry_form", clear_on_submit=True):
            entry_date = st.date_input("Date", value=pd.Timestamp(reference_date),
                                        help=f"This dataset's \"today\" is simulated as "
                                             f"{reference_date} — pick a date in that "
                                             f"month to see it reflected in MTD spend.")
            merchant = st.text_input("Merchant / description", placeholder="e.g. Trader Joe's")
            category = st.selectbox("Category", BUCKETS)
            amount = st.number_input("Amount ($)", min_value=0.01, step=1.0, format="%.2f")
            submitted = st.form_submit_button("Add entry")
            if submitted:
                if not merchant.strip():
                    st.error("Merchant / description is required.")
                else:
                    st.session_state["manual_entries"].append({
                        "id": f"manual-{uuid.uuid4().hex[:8]}",
                        "date": pd.Timestamp(entry_date),
                        "client_id": uid,
                        "card_id": None,
                        "amount": float(amount),
                        "use_chip": "Manual Entry",
                        "merchant_id": f"manual-{merchant.strip().lower().replace(' ', '-')}",
                        "merchant_city": merchant.strip(),
                        "merchant_state": None,
                        "zip": None,
                        "mcc": None,
                        "errors": None,
                        "mcc_description": category,
                        "monthly_discretionary_limit": limit,
                        "card_type": None,
                        "category": category,
                        "is_discretionary": category in DISCRETIONARY,
                    })
                    st.success(f"Added ${amount:,.2f} at {merchant.strip()}.")
                    st.toast(f"New entry added: ${amount:,.2f} · {merchant.strip()}")


def fold_manual_entries(uid: int, user_df, proj: dict, mtd: float, cat_spend):
    """Fold this customer's session-added entries into display-only data. The cached
    master/monthly pipeline (and therefore the ML projection) stays untouched."""
    own_manual = [r for r in st.session_state.get("manual_entries", []) if r["client_id"] == uid]
    manual_df = pd.DataFrame(own_manual)
    if manual_df.empty:
        return user_df, mtd, cat_spend, own_manual
    display_df = pd.concat([user_df, manual_df], ignore_index=True)
    ref_period = pd.Period(proj["reference_month"], "M")
    manual_ref = manual_df[manual_df["date"].dt.to_period("M") == ref_period]
    extra_mtd = manual_ref.loc[manual_ref["is_discretionary"], "amount"].sum()
    extra_by_cat = manual_ref[manual_ref["is_discretionary"]].groupby("category")["amount"].sum()
    return display_df, mtd + extra_mtd, cat_spend.add(extra_by_cat, fill_value=0.0), own_manual
