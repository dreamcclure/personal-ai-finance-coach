"""Module 5 — Grounded conversational finance coach.

Builds a factual context block from the user's own computed metrics, injects it into a
constrained system prompt, and calls the LLM. The coach is told to use ONLY the provided
facts (no invented numbers) and to stay on this user's personal finances.
"""
from __future__ import annotations

import pandas as pd

from src.categorize import get_client

SYSTEM_PROMPT = (
    "You are ClearLedger's personal finance coach for ONE specific customer. "
    "Help them understand their spending and stay within their monthly discretionary limit.\n"
    "Rules:\n"
    "- Use ONLY the facts in the CUSTOMER FINANCIAL CONTEXT below. Never invent numbers, "
    "transactions, merchants, or accounts.\n"
    "- If the context doesn't contain the answer, say you don't have that data.\n"
    "- Stay on this customer's personal finances; politely decline unrelated requests.\n"
    "- Be concise, encouraging, and specific — cite the real figures and categories."
)


def build_summary(client_id: int, proj: dict, limit: float,
                  category_spend: pd.Series, top_n: int = 3) -> dict:
    """Assemble the compact metrics dict the coach (and chat page) are grounded on."""
    top = [(str(c), float(a))
           for c, a in category_spend.sort_values(ascending=False).head(top_n).items()
           if a > 0]
    return {
        "client_id": client_id,
        "reference_month": proj["reference_month"],
        "ref_day": proj["ref_day"],
        "mtd": proj["mtd_discretionary"],
        "projected": proj["projected_month_end"],
        "limit": limit,
        "top_categories": top,
    }


def build_user_context(summary: dict) -> str:
    """Render the summary dict into a factual context block for the prompt."""
    over = summary["projected"] > summary["limit"]
    lines = [
        "CUSTOMER FINANCIAL CONTEXT",
        f"- Customer ID: {summary['client_id']}",
        f"- Current month: {summary['reference_month']} (as of day {summary['ref_day']})",
        f"- Month-to-date discretionary spend: ${summary['mtd']:,.0f}",
        f"- Projected month-end discretionary spend: ${summary['projected']:,.0f}",
        f"- Monthly discretionary limit: ${summary['limit']:,.0f}",
        f"- Status: {'OVER budget' if over else 'within budget'}",
    ]
    if summary.get("top_categories"):
        lines.append("- Top discretionary categories this month:")
        for cat, amt in summary["top_categories"]:
            lines.append(f"    * {cat}: ${amt:,.0f}")
    return "\n".join(lines)


def build_messages(context: str, history: list[dict], user_message: str) -> list[dict]:
    """Compose the OpenAI-style message list: system+context, prior turns, new question."""
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context}"}]
    messages.extend(history)  # each item: {"role": "user"|"assistant", "content": str}
    messages.append({"role": "user", "content": user_message})
    return messages


def coach_reply(cfg: dict, summary: dict, history: list[dict],
                user_message: str, client=None) -> str:
    """Return the coach's reply. `client` can be injected for testing (no network)."""
    context = build_user_context(summary)
    messages = build_messages(context, history, user_message)
    client = client or get_client(cfg)
    resp = client.chat.completions.create(
        model=cfg["llm"]["model"], messages=messages,
    )
    return resp.choices[0].message.content
