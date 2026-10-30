"""Module 4a — Category-level savings recommendations.

Pure, deterministic logic (no LLM) grounded in the user's own reference-month spend and
the model's month-end projection. Returns a list of {title, detail} dicts the dashboard
renders and the chat coach can reuse.
"""
from __future__ import annotations

import pandas as pd


def build_recommendations(category_spend: pd.Series, projected: float,
                          limit: float, top_n: int = 3) -> list[dict]:
    """Suggest where to cut, based on this month's discretionary spend by category.

    `category_spend`: index = category, value = this month's discretionary spend.
    `projected`: model's projected month-end discretionary total.
    `limit`: the user's monthly discretionary limit.
    """
    recs: list[dict] = []
    gap = projected - limit

    # Dollar signs are escaped (\$) because Streamlit's markdown renderer treats a
    # pair of unescaped "$" in one string as LaTeX math delimiters — with two dollar
    # amounts in one message, that silently ate both "$" and rendered the numbers
    # in monospace math styling instead of plain currency text.
    if gap > 0:
        recs.append({
            "title": f"Projected to exceed your limit by \\${gap:,.0f}",
            "detail": f"You're on track for \\${projected:,.0f} vs. your \\${limit:,.0f} "
                      f"limit. Trimming the categories below can close the gap.",
        })
    else:
        recs.append({
            "title": f"On track to stay \\${-gap:,.0f} under your limit",
            "detail": f"Projected \\${projected:,.0f} vs. your \\${limit:,.0f} limit — nice work.",
        })

    top = category_spend.sort_values(ascending=False).head(top_n)
    for category, amount in top.items():
        if amount <= 0:
            continue
        saving = amount * 0.15
        recs.append({
            "title": f"{category}: ${amount:,.0f} this month",
            "detail": f"A 15% trim here would save about ${saving:,.0f}.",
        })
    return recs
