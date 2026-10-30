"""Module 4 — ClearLedger Streamlit dashboard (Overview page).

Dispatched by app/app.py's st.navigation() router (top nav). Shows, for a selected
user (default 1696): the monthly limit meter, MTD & projected discretionary spend,
a category spending trend, a category breakdown, a transaction ledger, and
data-grounded recommendations.
"""
import sys
from datetime import datetime
from pathlib import Path

# Make the project root importable so `from src...` works under `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app._shared import fold_manual_entries, get_user_view, load_everything, new_entry_popover
from src.features import category_time_series, user_month_row
from src.insights import recurring_merchants, unusual_charges
from src.recommend import build_recommendations

cfg, master, monthly, res = load_everything()
model = res["model"]

user_ids = sorted(int(u) for u in monthly["client_id"].unique())
default_uid = cfg["target_user"] if cfg["target_user"] in user_ids else user_ids[0]

# --------------------------------------------------------------------------- #
# Customer picker: the mockup this design is based on doesn't show one (it's a
# single-account reference), but our data covers 66 real customers and switching
# between them is a required control — kept in a slim sidebar rather than
# crowding the masthead, since it's a functional necessity, not decoration.
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown('<p class="cl-eyebrow">Customer</p>', unsafe_allow_html=True)
    uid = st.selectbox("Customer (user id)", user_ids, index=user_ids.index(default_uid),
                       label_visibility="collapsed")
    disc_only = st.toggle("Trend: discretionary only", value=True)

if st.session_state.get("_last_uid") is not None and st.session_state["_last_uid"] != uid:
    st.toast(f"Switched to Customer {uid}")
st.session_state["_last_uid"] = uid

# --------------------------------------------------------------------------- #
# Per-user computations (shared with the chat page via app/_shared.py)
# --------------------------------------------------------------------------- #
user_df, proj, limit, cat_spend = get_user_view(cfg, master, monthly, model, uid)
mtd, projected = proj["mtd_discretionary"], proj["projected_month_end"]

# Real month-over-month comparison (prev_month_disc is the user's actual completed
# prior month, not a projection) — grounds the "up/down X% this month" line.
prev_row = user_month_row(monthly, uid, pd.Period(proj["reference_month"], "M"))
prev_month_disc = float(prev_row["prev_month_disc"].iloc[0]) if prev_row is not None else None
mom_pct = ((projected - prev_month_disc) / prev_month_disc * 100.0
           if prev_month_disc and prev_month_disc > 0 else None)

# --------------------------------------------------------------------------- #
# Masthead: logo/wordmark/tabs + New Entry (session-only; flows into MTD spend,
# category breakdown, trend, ledger, and insights below — not into the ML
# projection, which is trained on the full historical dataset).
# --------------------------------------------------------------------------- #
header_l, header_r = st.columns([5, 1])
with header_l:
    theme.masthead(active_tab="Overview")
with header_r:
    new_entry_popover(uid, limit, proj["reference_date"])

st.markdown('<div id="top"></div>', unsafe_allow_html=True)

display_df, mtd_display, cat_spend_display, own_manual = fold_manual_entries(
    uid, user_df, proj, mtd, cat_spend)

# --------------------------------------------------------------------------- #
# Editorial masthead eyebrow + dynamic greeting (tied to the selected customer,
# not a fabricated name — this dataset has no real customer names).
# --------------------------------------------------------------------------- #
theme.masthead_eyebrow("VOL. XII", datetime.now().strftime("%A · %B %-d, %Y").upper())
theme.greeting_line(f"Customer {uid}")

# Budget status: "good" (green) / "warning" (amber, within 15% of limit) / "critical"
# (red, over limit) — drives the banner, the gauge color, and (inverted, per the
# requested rule) the MoM delta chip below.
near_limit = limit * 0.85
if projected > limit:
    status, status_color = "critical", theme.CRITICAL
elif projected >= near_limit:
    status, status_color = "warning", theme.WARNING
else:
    status, status_color = "good", theme.GOOD

# --------------------------------------------------------------------------- #
# Hero: predicted month-end spend (this app's real centerpiece figure — there's
# no net-worth or income data in this dataset) + a real tracking sentence, with
# the MTD/Predicted/Limit trio set to the right per the reference layout.
# --------------------------------------------------------------------------- #
hero_col, stat_col = st.columns([1.5, 1.3])
with hero_col:
    theme.hero_metric("Predicted Month-End Spend", f"${projected:,.0f}")

with stat_col:
    st.markdown('<div class="cl-stat-cluster">', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("MTD Spend", f"${mtd_display:,.0f}")
    with s2:
        with st.container(key=theme.PROJECTED_METRIC_KEY):
            st.metric("Predicted Month-End", f"${projected:,.0f}")
        if mom_pct is not None:
            # Per spec: red if projected to be OVER the limit, amber/yellow if under —
            # a simpler 2-state rule than the 3-tier status used for the banner/gauge.
            chip_color = theme.CRITICAL if status == "critical" else theme.INK
            st.markdown(theme.delta_chip(f"{mom_pct:+.1f}% vs last month", chip_color),
                       unsafe_allow_html=True)
    with s3:
        st.metric("Monthly Limit", f"${limit:,.0f}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
if status == "critical":
    theme.budget_banner("critical", f"Projected spend (${projected:,.0f}) is over your "
                                     f"${limit:,.0f} limit by ${projected - limit:,.0f}.")
elif status == "warning":
    theme.budget_banner("warning", f"Projected spend (${projected:,.0f}) is within 15% "
                                    f"of your ${limit:,.0f} limit — ${limit - projected:,.0f} left.")
else:
    theme.budget_banner("good", f"Projected spend (${projected:,.0f}) is comfortably under "
                                 f"your ${limit:,.0f} limit — ${limit - projected:,.0f} left.")

st.divider()

# --------------------------------------------------------------------------- #
# Recent Ledger + Monthly Limit Meter
# --------------------------------------------------------------------------- #
ledger_col, meter_col = st.columns([2, 1])

with ledger_col:
    with st.container(border=True):
        lh1, lh2 = st.columns([3, 1])
        with lh1:
            st.markdown("#### Recent Ledger")
        with lh2:
            st.session_state.setdefault("ledger_view_all", False)
            if st.button("VIEW ALL →", key="view_all_ledger"):
                st.session_state["ledger_view_all"] = not st.session_state["ledger_view_all"]

        ref_period = pd.Period(proj["reference_month"], "M")
        month_txns = display_df[display_df["date"].dt.to_period("M") == ref_period]

        with st.container(border=True):
            st.markdown('<p class="cl-eyebrow">Filter Ledger</p>', unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                month_start = ref_period.start_time.date()
                month_end = ref_period.end_time.date()
                date_range = st.date_input("Date range", value=(month_start, month_end),
                                           min_value=month_start, max_value=month_end,
                                           label_visibility="collapsed")
            with fc2:
                cat_options = sorted(month_txns["category"].dropna().unique())
                chosen_cats = st.multiselect("Categories", cat_options,
                                             placeholder="All categories",
                                             label_visibility="collapsed")
            with fc3:
                acct_options = sorted(month_txns["card_type"].dropna().unique())
                chosen_acct = st.selectbox("Account", ["All accounts"] + acct_options,
                                           label_visibility="collapsed")

        filtered = month_txns
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start, end = date_range
            filtered = filtered[(filtered["date"].dt.date >= start) &
                                (filtered["date"].dt.date <= end)]
        if chosen_cats:
            filtered = filtered[filtered["category"].isin(chosen_cats)]
        if chosen_acct != "All accounts":
            filtered = filtered[filtered["card_type"] == chosen_acct]

        filtered = filtered.sort_values("date", ascending=False)
        ledger_df = filtered if st.session_state["ledger_view_all"] else filtered.head(15)

        if not ledger_df.empty:
            manual_ids = {r["id"] for r in own_manual}
            for _, row in ledger_df.iterrows():
                merchant = row.get("merchant_city") or "Unknown merchant"
                meta = f"{row['category']} · {row['date'].strftime('%b %d')}"
                theme.ledger_row(str(merchant), meta, float(row["amount"]),
                                 is_new=row["id"] in manual_ids)
        else:
            st.caption("No transactions match these filters.")

with meter_col:
    with st.container(border=True):
        st.markdown('<p class="cl-hero-label">Monthly Spending</p>', unsafe_allow_html=True)
        pct = (projected / limit * 100) if limit else 0.0
        warn_pct = 90.0
        axis_max_pct = max(125.0, pct * 1.1)
        # Intentionally uses the "Shopping" categorical amber (#eda100), not
        # theme.WARNING (#CA8A04) — a deliberate exception to the usual rule that
        # category colors stay independent from the status triad, per user request
        # to visually match the "Where It Goes" Shopping bar exactly.
        bar_color = theme.CRITICAL if pct >= warn_pct else "#eda100"
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%", "valueformat": ".0f",
                    "font": {"family": theme.FONT_SERIF, "color": theme.PRIMARY, "size": 56}},
            gauge={
                "axis": {"range": [0, axis_max_pct], "tickcolor": theme.INK_MUTED},
                "bar": {"color": bar_color},
                "threshold": {"line": {"color": theme.CRITICAL, "width": 4}, "value": warn_pct},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0, warn_pct], "color": "#E9ECEF"},
                    {"range": [warn_pct, 100], "color": "#F5D9D9"},
                    {"range": [100, axis_max_pct], "color": theme.DIVIDER},
                ],
            },
        ))
        gauge.update_layout(height=220, margin=dict(t=50, b=0, l=10, r=10),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color=theme.INK_MUTED, family=theme.FONT_MONO))
        st.plotly_chart(gauge, use_container_width=True)
        st.markdown(
            f'<p class="cl-mono" style="text-align:center; color:{theme.INK_MUTED}; '
            f'letter-spacing:0.1em; font-size:0.78rem; margin-top:0.25rem;">'
            f'OF ${limit:,.0f} BUDGET</p>',
            unsafe_allow_html=True,
        )
        st.markdown('<hr style="margin: 1.25rem 0 1rem 0;">', unsafe_allow_html=True)
        sp_col, rem_col = st.columns(2)
        with sp_col:
            st.markdown(f'<p class="cl-mono cl-gauge-label" style="text-align:left;">SPENT</p>'
                       f'<p class="cl-gauge-value" style="text-align:left; color:{theme.INK};">'
                       f'${mtd_display:,.0f}</p>', unsafe_allow_html=True)
        with rem_col:
            st.markdown(f'<p class="cl-mono cl-gauge-label" style="text-align:right;">REMAINING</p>'
                       f'<p class="cl-gauge-value" style="text-align:right; color:{theme.PRIMARY};">'
                       f'${max(limit - projected, 0):,.0f}</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center; padding:6rem 1rem 1.5rem 1rem;">'
        f'<p class="cl-hero-label">Editor\'s Note</p>'
        f'<p style="font-family:{theme.FONT_SERIF}; font-weight:800; font-size:1.9rem; '
        f'color:{theme.PRIMARY}; line-height:1.5; margin:1.5rem 0 0 0;">'
        f'"A ledger isn\'t a scorecard.<br>It\'s a story about<br>the choices you made<br>'
        f'this week —<br>and the ones you\'ll<br>make next."</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# --------------------------------------------------------------------------- #
# Category Spending Trend + Where It Goes
# --------------------------------------------------------------------------- #
st.markdown('<div id="trends"></div>', unsafe_allow_html=True)
workflow_col, state_col = st.columns([2, 1])

with workflow_col:
    with st.container(border=True):
        st.markdown("#### Category Spending Trend")
        ts = theme.cap_categories_df(category_time_series(display_df, discretionary_only=disc_only))
        if not ts.empty:
            chosen = st.multiselect("Filter categories", list(ts.columns), default=list(ts.columns))
            if chosen:
                fig = px.bar(ts[chosen], x=ts.index, y=chosen, barmode="stack",
                            labels={"value": "spend ($)", "x": "month", "variable": "category"},
                            color_discrete_map={c: theme.color_for(c) for c in chosen})
                fig.for_each_trace(lambda t: t.update(
                    hovertemplate=f"<b>{t.name}</b><br>%{{x|%b %Y}}: $%{{y:,.2f}}<extra></extra>",
                ))
                fig.update_layout(
                    height=420, margin=dict(t=10, b=0, l=0, r=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=theme.INK_MUTED, family=theme.FONT_MONO),
                    legend=dict(font=dict(color=theme.INK_MUTED, family=theme.FONT_MONO), title=None),
                    xaxis=dict(gridcolor=theme.DIVIDER, zerolinecolor=theme.DIVIDER, title=None,
                              tickfont=dict(color=theme.INK_MUTED, family=theme.FONT_MONO)),
                    yaxis=dict(gridcolor=theme.DIVIDER, zerolinecolor=theme.DIVIDER,
                              tickfont=dict(color=theme.INK_MUTED, family=theme.FONT_MONO)),
                    hoverlabel=dict(font=dict(family=theme.FONT_MONO)),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available for this user.")

with state_col:
    with st.container(border=True):
        st.markdown("#### Where It Goes")
        capped = theme.cap_categories(cat_spend_display)
        total = capped.sum()
        if total > 0:
            for cat, amt in capped.sort_values(ascending=False).items():
                theme.progress_row(cat, amt / total * 100.0, theme.color_for(cat))
        else:
            st.caption("No discretionary spend recorded for this month.")

        st.divider()
        st.markdown('<p class="cl-hero-label" style="margin-top:0.5rem;">Six-Month Trend</p>',
                   unsafe_allow_html=True)
        monthly_totals = ts.sum(axis=1).tail(6) if not ts.empty else pd.Series(dtype=float)
        if not monthly_totals.empty:
            bar_colors = [theme.PRIMARY] * (len(monthly_totals) - 1) + [theme.GOOD]
            trend_fig = px.bar(x=monthly_totals.index.strftime("%b").str.upper(),
                              y=monthly_totals.values)
            trend_fig.update_traces(marker_color=bar_colors, marker_line_width=0)
            trend_fig.update_layout(
                height=200, margin=dict(t=10, b=10, l=0, r=0), showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=theme.INK_MUTED, family=theme.FONT_MONO),
                xaxis=dict(showgrid=False, title=None, tickfont=dict(family=theme.FONT_MONO)),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(trend_fig, use_container_width=True)
        else:
            st.caption("Not enough history for a six-month trend yet.")

st.divider()

# --------------------------------------------------------------------------- #
# What-if: Trim a Category
# --------------------------------------------------------------------------- #
st.markdown('<div id="whatif"></div>', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("#### What-if: Trim a Category")
    if not cat_spend_display.empty and cat_spend_display.sum() > 0:
        options = list(cat_spend_display.sort_values(ascending=False).index)
        wc1, wc2 = st.columns([1, 2])
        whatif_cat = wc1.selectbox("Category to trim", options)
        pct = wc2.slider("Reduce this category by (%)", 0, 100, 20)
        share = cat_spend_display[whatif_cat] / cat_spend_display.sum()
        reduction = (pct / 100.0) * share * projected
        new_proj = projected - reduction
        m1, m2 = st.columns(2)
        m1.metric("New projected month-end", f"${new_proj:,.0f}", delta=f"-${reduction:,.0f}",
                  delta_color="off")
        m2.metric("vs limit", f"${new_proj - limit:,.0f}",
                  delta=("under budget" if new_proj <= limit else "over budget"),
                  delta_color="off")
    else:
        st.caption("No discretionary spend to simulate this month.")

st.divider()

# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #
st.markdown('<div id="insights"></div>', unsafe_allow_html=True)
recs_col, insights_col = st.columns([1, 1.6])

with recs_col:
    with st.container(border=True):
        st.markdown("#### Recommendations")
        recs = build_recommendations(cat_spend_display, projected, limit)
        for i, rec in enumerate(recs):
            if i > 0:
                st.divider()
            st.markdown(f"**{rec['title']}**")
            st.caption(rec["detail"])

with insights_col:
    with st.container(border=True):
        st.markdown("#### Insights")
        st.markdown("**Unusual charges**")
        uc = unusual_charges(display_df)
        if not uc.empty:
            st.dataframe(uc, hide_index=True, use_container_width=True)
        else:
            st.caption("No unusual charges detected.")
        st.divider()
        st.markdown("**Recurring / subscriptions**")
        rc = recurring_merchants(display_df)
        if not rc.empty:
            st.caption(f"{len(rc)} recurring merchant(s) · "
                       f"~${rc['typical_amount'].sum():,.0f}/mo estimated")
            st.dataframe(rc, use_container_width=True)
        else:
            st.caption("No recurring charges detected.")

st.divider()

# --------------------------------------------------------------------------- #
# Footer: real coaching/resource links + a closing note.
# --------------------------------------------------------------------------- #
st.divider()
with st.container(key="footer-chat-link"):
    st.page_link("pages/2_💬_Chat_Coach.py", label="Chat with your Coach →")
with st.expander("Guardrails & documentation"):
    st.caption("Every figure above is computed from your own transaction history — "
              "the coach never invents a number. See PROJECT_SPEC.md and README.md "
              "in the project root for the full architecture and guardrail definitions.")
