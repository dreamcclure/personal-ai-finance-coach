"""Module 5 — Streamlit chat coach page (multi-turn, grounded in the user's data).

Appears as a second page alongside the dashboard. Shows the required figures
(MTD spend, limit, projected) and a chat box; each answer is grounded in the user's
computed metrics via src/coach.py.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app import theme
from app._shared import get_user_view, load_everything, new_entry_popover
from src.coach import build_summary, coach_reply

# --- cost guardrail for the public demo: per-visitor rate limit ---
# (the hard ceiling is the spending cap set on the API account itself)
RATE_LIMIT = 10        # questions...
RATE_WINDOW = 3600     # ...per hour, per browser session


def within_rate_limit() -> bool:
    now = time.time()
    hits = [t for t in st.session_state.get("coach_hits", []) if now - t < RATE_WINDOW]
    st.session_state.coach_hits = hits
    return len(hits) < RATE_LIMIT


cfg, master, monthly, res = load_everything()
model = res["model"]
user_ids = sorted(int(u) for u in monthly["client_id"].unique())
default_uid = cfg["target_user"] if cfg["target_user"] in user_ids else user_ids[0]

with st.sidebar:
    st.markdown('<p class="cl-eyebrow">Customer</p>', unsafe_allow_html=True)
    uid = st.selectbox("Customer (user id)", user_ids, index=user_ids.index(default_uid),
                       label_visibility="collapsed")

user_df, proj, limit, cat_spend = get_user_view(cfg, master, monthly, model, uid)
summary = build_summary(uid, proj, limit, cat_spend)

header_l, header_r = st.columns([5, 1])
with header_l:
    theme.masthead(active_tab="Chat Coach")
with header_r:
    new_entry_popover(uid, limit, proj["reference_date"])

theme.masthead_eyebrow("VOL. XII", "CHAT COACH")
theme.greeting_line(f"Customer {uid}")
theme.user_badge(uid)

# Required figures (rubric: MTD Spend, Limit, and Projected present).
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("MTD discretionary spend", f"${summary['mtd']:,.0f}")
    c2.metric("Projected month-end", f"${summary['projected']:,.0f}")
    c3.metric("Monthly limit", f"${summary['limit']:,.0f}")

# In the public demo there's no API key; make the coach's limitation clear and intentional.
if not cfg["llm"].get("api_key"):
    st.info("💬 Live chat is disabled in this public demo (no API key configured). "
            "The dashboard is fully functional — run the app locally with your own key to chat.")
else:
    st.caption(f"Public demo: up to {RATE_LIMIT} questions per hour per visitor.")

# Per-user chat history (switching users starts a fresh conversation).
state_key = f"chat_history_{uid}"
if state_key not in st.session_state:
    st.session_state[state_key] = []
history = st.session_state[state_key]

for msg in history:
    with st.chat_message(msg["role"], avatar=theme.CHAT_AVATARS.get(msg["role"])):
        st.markdown(msg["content"].replace("$", "\\$"))

prompt = st.chat_input("Ask your finance coach…")
if prompt:
    with st.chat_message("user", avatar=theme.CHAT_AVATARS["user"]):
        st.markdown(prompt.replace("$", "\\$"))
    with st.chat_message("assistant", avatar=theme.CHAT_AVATARS["assistant"]):
        if cfg["llm"].get("api_key") and not within_rate_limit():
            reply = ("⏳ You've reached this demo's hourly question limit. Please try again later "
                     "— or run the app locally with your own API key (see the GitHub repo).")
        else:
            st.session_state.coach_hits = st.session_state.get("coach_hits", []) + [time.time()]
            with st.spinner("Coaching…"):
                try:
                    reply = coach_reply(cfg, summary, history, prompt)
                except Exception as e:  # keep the UI alive if the API hiccups / no key in the demo
                    if not cfg["llm"].get("api_key"):
                        reply = ("💬 *Live chat is turned off in this public demo* (no API key is "
                                 "configured). The dashboard above is fully functional — or run the "
                                 "app locally with your own key to chat with the coach.")
                    else:
                        reply = f"Sorry — I couldn't reach the coach service right now ({type(e).__name__})."
        st.markdown(reply.replace("$", "\\$"))
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})
