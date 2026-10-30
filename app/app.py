"""ClearLedger — Streamlit entry point / router.

Run from the project root:
    streamlit run app/app.py

This file only sets page config, injects the shared theme, and dispatches to the
two real pages (Overview, Chat Coach). Navigation uses position="hidden" — routing
stays fully functional (st.page_link, st.switch_page) but Streamlit renders none of
its own nav chrome, since the page content builds a fully custom masthead instead
(app/theme.py's masthead()). Page content lives in app/pages/1_Overview.py and
app/pages/2_💬_Chat_Coach.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app import theme

st.set_page_config(page_title="ClearLedger Finance Coach", layout="wide")
theme.inject_css()

pg = st.navigation(
    [
        st.Page("pages/1_Overview.py", title="Overview", default=True),
        st.Page("pages/2_💬_Chat_Coach.py", title="Chat Coach"),
    ],
    position="hidden",
)
pg.run()
