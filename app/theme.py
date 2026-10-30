"""Shared visual polish for both Streamlit pages: colors, CSS, and small UI helpers.

Kept separate from app/_shared.py (which is the *data* pipeline) because this file is
pure presentation — colors, injected CSS, and copy helpers — reused by both pages so
they look like one product.

Design direction (Batch 2, 7th iteration): corporate-navy "portfolio-grade" theme,
now with a fully custom masthead header (logo + wordmark + tabs + New Entry action)
replacing Streamlit's native top-nav chrome, and an editorial "Ledger Daily" eyebrow
(VOL. XII / date / dynamic greeting) above a massive hero figure. No decorative
emoji — icons are either real navigation affordances or omitted. Off-white canvas,
white card containers with real borders, slate body text, and a green/amber/red
status triad reserved for state (never used as a category color).
"""
from datetime import datetime

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------- #
# Theme tokens (mirrors .streamlit/config.toml)
# --------------------------------------------------------------------------- #
PAGE_BG = "#F8F9FA"       # off-white canvas
CARD_BG = "#FFFFFF"       # card containers / header bar
PRIMARY = "#0f2052"       # deep corporate navy — brand, header, hero numerals
INK = "#343A40"           # slate — primary body text
INK_MUTED = "#6C757D"     # muted slate — secondary metadata/labels
DIVIDER = "#DEE2E6"       # hairline rules / card borders

# Traffic-light status triad — reserved for state, never used as a category color.
GOOD = "#16A34A"          # green — action CTAs + positive/under-budget state
WARNING = "#CA8A04"       # amber — near-limit state / "under, but watch it"
CRITICAL = "#DC2626"      # red — over-limit / critical state
ACCENT = GOOD             # primary action color (buttons)
ACCENT_HOVER = "#128A3E"

FONT_SERIF = "'Playfair Display', Georgia, 'Times New Roman', serif"
FONT_MONO = "'Space Mono', 'JetBrains Mono', 'Courier New', monospace"

# CSS hook (st.container(key=...) -> class "st-key-<key>") for the single metric
# that should render unbolded without affecting every other st.metric on the page.
PROJECTED_METRIC_KEY = "projected-metric"

# Chat avatars so user vs. coach turns are visually distinct at a glance.
CHAT_AVATARS = {"user": "👤", "assistant": "🧠"}

# --------------------------------------------------------------------------- #
# Category identity: the dataviz skill's pre-validated 8-slot categorical palette
# (light mode; CVD-safe adjacent-pair contrast, fixed hue order preserved exactly
# as validated). None of these hues overlap the status triad above, so a category
# color never impersonates a status signal.
# --------------------------------------------------------------------------- #
_CATEGORICAL_RAMP = ["#2a78d6", "#1baf7a", "#eda100", "#008300",
                     "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
_CATEGORY_ORDER = ["Dining", "Entertainment", "Shopping", "Travel", "Personal Care",
                    "Subscriptions", "Housing", "Groceries"]
CATEGORY_COLORS = dict(zip(_CATEGORY_ORDER, _CATEGORICAL_RAMP))
CATEGORY_COLORS["Other"] = "#898781"
MAX_SLOTS = 8

# The masthead tabs. All four are in-page anchor jumps within 1_Overview.py.
# Chat Coach is a separate page (rendered as its own styled pill, not a 5th tab).
NAV_TABS = ["Overview", "Trends", "What-If", "Insights"]
NAV_ANCHORS = {"Overview": "top", "Trends": "trends", "What-If": "whatif", "Insights": "insights"}


def color_for(category: str) -> str:
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])


def cap_categories(spend: pd.Series, max_slots: int = MAX_SLOTS) -> pd.Series:
    """Collapse everything past the top (max_slots - 1) categories into 'Other'.

    Keeps every chart to <= max_slots series (dataviz rule: a 9th series is never
    a new hue, it folds into Other) without ever hiding spend.
    """
    if len(spend) <= max_slots:
        return spend
    ranked = spend.sort_values(ascending=False)
    head, tail = ranked.iloc[: max_slots - 1], ranked.iloc[max_slots - 1 :]
    capped = head.copy()
    capped["Other"] = capped.get("Other", 0.0) + tail.sum()
    return capped


def cap_categories_df(ts: pd.DataFrame, max_slots: int = MAX_SLOTS) -> pd.DataFrame:
    """Same idea as cap_categories, but for a (month x category) trend table."""
    if ts.shape[1] <= max_slots:
        return ts
    totals = ts.sum().sort_values(ascending=False)
    keep, fold = list(totals.index[: max_slots - 1]), list(totals.index[max_slots - 1 :])
    capped = ts[keep].copy()
    capped["Other"] = ts[fold].sum(axis=1) + (ts["Other"] if "Other" in ts.columns else 0.0)
    return capped


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800;900&family=Space+Mono:wght@400;700&display=swap');

        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
            background: {PAGE_BG};
            color: {INK};
        }}
        [data-testid="stHeader"] {{ background: {CARD_BG}; border-bottom: 1px solid {DIVIDER}; }}

        h1, h2, h3, h4, [data-testid="stMetricValue"] {{ font-family: {FONT_SERIF}; }}
        h5, h6, [data-testid="stMetricLabel"], [data-testid="stDataFrame"],
        .cl-mono {{ font-family: {FONT_MONO}; }}

        hr {{ border: none; border-top: 1px solid {DIVIDER}; margin: 1.5rem 0; }}

        /* Real card containers (st.container(border=True)): white bg, clean padding.
           This Streamlit build doesn't expose a stable hook for an added drop-shadow
           on top of the native border, so this is border + padding, not a full shadow. */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {CARD_BG}; border-radius: 8px;
        }}

        /* A slim sidebar for the one control the mockup doesn't show: the customer
           (user id) picker — required for real, multi-customer data. */
        section.stSidebar, [data-testid="stSidebarContent"] {{ background: {PRIMARY}; }}
        [data-testid="stSidebarContent"] * {{ color: {PAGE_BG} !important; }}

        /* --- Masthead header row (logo, wordmark, tabs, New Entry) --- */
        .cl-masthead {{ display: flex; align-items: center; padding: 0.6rem 0;
                         border-bottom: 1px solid {DIVIDER}; margin-bottom: 1.5rem; }}
        .cl-logo-box {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 28px; height: 28px; background: {PRIMARY}; color: #FFFFFF;
            font-family: {FONT_SERIF}; font-weight: 800; border-radius: 6px; margin-right: 0.5rem;
        }}
        .cl-wordmark {{ font-family: {FONT_SERIF}; font-weight: 800; font-size: 1.3rem; color: {PRIMARY}; }}
        .cl-tab, a.cl-tab {{
            font-family: {FONT_MONO}; letter-spacing: 0.1em; font-size: 0.8rem;
            text-transform: uppercase; color: {INK_MUTED}; padding-top: 0.6rem; opacity: 0.5;
            text-decoration: none; cursor: pointer;
        }}
        a.cl-tab:hover {{ opacity: 0.85; }}
        .cl-tab.active {{ color: {PRIMARY}; font-weight: 700; opacity: 1; }}

        .st-key-chat-coach-badge [data-testid="stPageLink"] a,
        .st-key-chat-coach-badge-active [data-testid="stPageLink"] a {{
            font-family: {FONT_MONO} !important; letter-spacing: 0.08em; font-size: 0.78rem !important;
            text-transform: uppercase; background: transparent !important;
            border: 1.5px solid {PRIMARY} !important; border-radius: 999px !important;
            padding: 0.35rem 1rem !important; box-shadow: none !important; color: {PRIMARY} !important;
        }}
        .st-key-chat-coach-badge-active [data-testid="stPageLink"] a {{
            background: {PRIMARY} !important; color: #FFFFFF !important;
        }}
        .st-key-chat-coach-badge [data-testid="stPageLink"] a:hover {{
            background: {PRIMARY} !important; color: #FFFFFF !important;
        }}

        .cl-masthead-eyebrow {{
            display: flex; align-items: center; gap: 0.75rem;
            font-family: {FONT_MONO}; letter-spacing: 0.15em; font-size: 0.78rem;
            color: {INK_MUTED}; text-transform: uppercase; margin: 1.5rem 0 0.5rem 0;
        }}
        .cl-masthead-eyebrow .rule {{ flex: 0 0 40px; height: 1px; background: {DIVIDER}; }}
        .cl-greeting {{ font-family: {FONT_SERIF}; font-weight: 800; font-size: 1.6rem;
                         color: {PRIMARY}; margin: 0 0 1.25rem 0; }}

        .cl-hero-label {{
            font-family: {FONT_MONO}; text-transform: uppercase; letter-spacing: 0.15em;
            font-size: 0.78rem; color: {INK_MUTED}; margin-bottom: 0.4rem;
        }}
        .cl-hero-value {{ font-family: {FONT_SERIF}; font-weight: 800; font-size: 5.4rem;
                           color: {PRIMARY}; line-height: 1; margin-bottom: 0.75rem; }}
        .cl-hero-tagline {{ color: {INK}; font-size: 1.05rem; max-width: 32rem; line-height: 1.5; }}

        .cl-stat-cluster {{ border-left: 1px solid {DIVIDER}; padding-left: 1.5rem; height: 100%; }}
        .cl-stat-label {{ font-family: {FONT_MONO}; text-transform: uppercase; letter-spacing: 0.1em;
                           font-size: 0.68rem; color: {INK_MUTED}; margin-bottom: 0.2rem; }}
        .cl-stat-value {{ font-family: {FONT_SERIF}; font-weight: 800; font-size: 1.5rem; color: {PRIMARY}; }}
        .cl-delta-chip {{ font-family: {FONT_MONO}; font-size: 0.72rem; font-weight: 700; margin-top: 0.15rem; }}

        /* The MTD/Predicted/Limit labels are long, tracked, and uppercase in a narrow
           column — let them wrap to two lines instead of clipping (the bug where only
           part of each heading was visible). */
        [data-testid="stMetric"] [data-testid="stMetricLabel"] {{
            white-space: normal; overflow: visible; line-height: 1.25; letter-spacing: 0.06em;
        }}
        [data-testid="stMetric"] [data-testid="stMetricLabel"] p {{ white-space: normal; overflow-wrap: break-word; }}

        .cl-badge {{
            display: inline-block; font-family: {FONT_MONO}; font-size: 0.72rem;
            letter-spacing: 0.08em; text-transform: uppercase; color: {PRIMARY};
            background: #E9ECFB; border: 1px solid {PRIMARY}; border-radius: 999px;
            padding: 0.2rem 0.7rem;
        }}

        [data-testid="stMetric"] {{ background: transparent; border: none; padding: 0.25rem 0; }}
        [data-testid="stMetricLabel"] {{
            color: {INK_MUTED}; text-transform: uppercase;
            letter-spacing: 0.04em; font-size: 0.68rem; font-family: {FONT_MONO};
        }}
        [data-testid="stMetricValue"] {{ color: {PRIMARY}; font-weight: 800; }}
        .st-key-{PROJECTED_METRIC_KEY} [data-testid="stMetricValue"] {{ font-weight: 400; }}

        .cl-banner {{ border-left: 3px solid {GOOD}; padding: 0.7rem 1rem; margin: 1.1rem 0;
                       font-weight: 500; color: {INK}; background: {CARD_BG};
                       font-family: {FONT_MONO}; font-size: 0.9rem; letter-spacing: 0.01em; }}
        .cl-banner.warning {{ border-left-color: {WARNING}; }}
        .cl-banner.critical {{ border-left-color: {CRITICAL}; }}

        .cl-ledger-row {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 0.6rem 0.5rem; margin: 0 -0.5rem; border-bottom: 1px solid {DIVIDER};
            border-radius: 6px; transition: background-color 0.15s ease;
        }}
        .cl-ledger-row:hover {{ background: rgba(0,0,0,0.035); }}
        .cl-ledger-left {{ display: flex; align-items: center; gap: 0.75rem; }}
        .cl-ledger-avatar {{
            width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
            background: {DIVIDER}; color: {PRIMARY};
            font-family: {FONT_SERIF}; font-weight: 700; font-size: 0.95rem;
            display: flex; align-items: center; justify-content: center;
        }}
        .cl-ledger-merchant {{ color: {INK}; font-weight: 600; }}
        .cl-ledger-meta {{ color: {INK_MUTED}; font-family: {FONT_MONO}; font-size: 0.72rem;
                            text-transform: uppercase; letter-spacing: 0.08em; }}
        .cl-ledger-amount {{ font-family: {FONT_SERIF}; font-weight: 700; font-size: 1.1rem; color: {INK}; }}
        .cl-ledger-amount.new {{ color: {GOOD}; }}
        .cl-ledger-amount.credit {{ color: {GOOD}; }}
        .cl-ledger-tag {{
            font-family: {FONT_MONO}; font-size: 0.62rem; letter-spacing: 0.1em;
            color: #FFFFFF; background: {GOOD}; padding: 0.05rem 0.4rem;
            margin-left: 0.5rem; text-transform: uppercase;
        }}
        .st-key-view_all_ledger button {{
            background: transparent !important; border: none !important; box-shadow: none !important;
            font-family: {FONT_MONO} !important; font-size: 0.72rem !important;
            letter-spacing: 0.08em; text-transform: uppercase; color: {PRIMARY} !important;
            padding: 0 !important;
        }}
        .st-key-view_all_ledger button:hover {{ text-decoration: underline; }}

        .cl-progress-row {{ margin: 0.9rem 0; }}
        .cl-progress-label {{ display: flex; justify-content: space-between;
                               font-weight: 600; color: {INK}; margin-bottom: 0.3rem; }}
        .cl-progress-track {{ background: {DIVIDER}; border-radius: 999px; height: 8px; overflow: hidden; }}
        .cl-progress-fill {{ height: 100%; border-radius: 999px; }}

        [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
        [data-testid="stDownloadButton"] button, [data-testid="stPopoverButton"] {{
            background-color: {GOOD}; color: #FFFFFF; border: none;
            border-radius: 6px; box-shadow: none; font-family: {FONT_MONO};
            text-transform: uppercase; letter-spacing: 0.06em;
        }}
        [data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover, [data-testid="stPopoverButton"]:hover {{
            background-color: {ACCENT_HOVER}; color: #FFFFFF;
        }}
        [data-testid="stPopoverBody"] {{ background: {CARD_BG}; border: 1px solid {DIVIDER}; }}
        [data-testid="stPopoverBody"] * {{ color: {INK} !important; }}

        /* Force native multiselect/selectbox controls to light card styling in the
           main content area, regardless of what .streamlit/config.toml sets for
           secondaryBackgroundColor (that token styles these controls app-wide, and
           was likely only intended for the sidebar). */
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
            background: {CARD_BG} !important;
            border: 1px solid {DIVIDER} !important;
        }}
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] span,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] div,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] div {{
            color: {INK} !important;
        }}
        /* The open dropdown menu renders in a portal outside the main content area,
           so it needs a global (unscoped) rule rather than one nested under stMain. */
        [data-baseweb="popover"] [data-baseweb="menu"] {{
            background: {CARD_BG} !important;
        }}
        [data-baseweb="popover"] [data-baseweb="menu"] li {{
            color: {INK} !important;
        }}

        /* 1. Chat Coach pill: force white text on hover (covers nested spans/p tags
           that sometimes don't inherit color from the parent <a>). */
        .st-key-chat-coach-badge [data-testid="stPageLink"] a:hover,
        .st-key-chat-coach-badge-active [data-testid="stPageLink"] a:hover {{
            background: {PRIMARY} !important;
            color: #FFFFFF !important;
        }}
        .st-key-chat-coach-badge [data-testid="stPageLink"] a:hover *,
        .st-key-chat-coach-badge-active [data-testid="stPageLink"] a:hover * {{
            color: #FFFFFF !important;
        }}

        /* 2. Pull "LEDGER" wordmark closer to the L logo box. */
        .cl-wordmark {{
            margin-left: -0.5rem !important;
        }}

        /* 3. Fix mid-word breaking in the MTD/Predicted/Monthly Limit stat labels —
           force wrapping only at word boundaries, not character breaks. */
        [data-testid="stMetricLabel"] {{
            word-break: normal !important;
            overflow-wrap: normal !important;
            white-space: normal !important;
            line-height: 1.3 !important;
        }}

        /* Extends the earlier navy-widget-box fix to stDateInput (a different widget type
           entirely, not covered before) and reinforces stSelectbox with a descendant
           selector instead of a direct-child one, in case of extra wrapper divs. */
        [data-testid="stMain"] [data-testid="stDateInput"] input,
        [data-testid="stMain"] [data-testid="stDateInput"] div[data-baseweb="input"],
        [data-testid="stMain"] [data-testid="stDateInput"] [data-baseweb="select"] {{
            background: {CARD_BG} !important;
            border: 1px solid {DIVIDER} !important;
            color: {INK} !important;
        }}
        [data-testid="stMain"] [data-testid="stDateInput"] * {{
            color: {INK} !important;
        }}
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] {{
            background: {CARD_BG} !important;
            border: 1px solid {DIVIDER} !important;
        }}
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] * {{
            color: {INK} !important;
        }}

        /* Streamlit's newer st.selectbox renders as a real <input> inside a
           react-aria ComboBox wrapper — a different internal structure than the
           data-baseweb="select" widget our earlier rules targeted, which is why
           this one wasn't being caught. Target the actual input/group directly. */
        [data-testid="stSelectbox"] input {{
            background: {CARD_BG} !important;
            color: {INK} !important;
            border: 1px solid {DIVIDER} !important;
        }}
        [data-testid="stSelectbox"] [role="group"] {{
            background: {CARD_BG} !important;
            border: 1px solid {DIVIDER} !important;
        }}

        .cl-gauge-label {{ color: {INK_MUTED}; text-transform: uppercase; letter-spacing: 0.08em;
                            font-size: 0.72rem; margin-bottom: 0.1rem; }}
        .cl-gauge-value {{ font-family: {FONT_SERIF}; font-weight: 800; font-size: 2.4rem; margin: 0; }}
        .cl-footer-quote {{
            font-family: {FONT_SERIF}; font-weight: 800; font-size: 1.9rem;
            color: {INK_MUTED}; line-height: 1.5; text-align: left;
            margin: 1.75rem 0 0 0;
        }}
        .cl-quote-block {{ text-align: center; padding: 2.5rem 1rem 1rem 1rem; }}
        .cl-quote-text {{
            font-family: {FONT_SERIF}; font-weight: 800; font-size: 1.6rem;
            color: {PRIMARY}; line-height: 1.45; margin: 0.6rem 0 0 0;
        }}

        /* Plotly hardcodes "Open Sans", verdana, arial, sans-serif directly onto its
           rendered SVG text elements, overriding whatever font= is set in Python's
           fig.update_layout() — confirmed via DevTools inspection. This forces every
           text element inside a Plotly chart to use the site's mono font instead. */
        .js-plotly-plot text,
        .js-plotly-plot .xtick text,
        .js-plotly-plot .ytick text,
        .js-plotly-plot .legendtext,
        .js-plotly-plot .gtitle,
        .js-plotly-plot .g-gtitle {{
            font-family: {FONT_MONO} !important;
        }}

        /* Exception to the blanket Plotly-font override above: the big percentage number
           in gauge indicators (like Monthly Spending) is deliberately serif, not mono —
           this restores that without loosening the mono rule for everything else. */
        .js-plotly-plot .numbers text {{
            font-family: {FONT_SERIF} !important;
        }}

        .st-key-footer-chat-link [data-testid="stPageLink"] a {{
            font-family: {FONT_SERIF} !important; font-weight: 800 !important;
            font-size: 1.6rem !important; color: {PRIMARY} !important;
            text-transform: none !important; letter-spacing: normal !important;
        }}
        .st-key-footer-chat-link [data-testid="stPageLink"] a:hover {{
            text-decoration: underline;
        }}

        /* Same nested-element issue as the hover fix earlier — extends it to the
           always-on active-page state (solid navy fill), not just on hover. */
        .st-key-chat-coach-badge-active [data-testid="stPageLink"] a * {{
            color: #FFFFFF !important;
        }}

        [data-testid="stChatInput"] {{
            background: {PRIMARY} !important;
            min-height: 110px !important;
            border-radius: 10px !important;
        }}
        [data-testid="stChatInput"] textarea {{
            color: #FFFFFF !important;
            font-size: 2rem !important;
        }}
        [data-testid="stChatInput"] textarea::placeholder {{
            color: rgba(255,255,255,0.55) !important;
        }}

        /* "Filter categories" multiselect pills: white background, navy text, instead
           of the default green fill. */
        [data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
            background-color: {CARD_BG} !important;
            border: 1px solid {DIVIDER} !important;
        }}
        [data-testid="stMultiSelect"] span[data-baseweb="tag"] span {{
            color: {PRIMARY} !important;
        }}
        [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {{
            fill: {PRIMARY} !important;
        }}

        /* New Entry popover form: Date, Merchant, and Amount inputs render with a navy
           background (same root cause as the earlier widget-color bug, just inside a
           popover this time) — force white text/placeholder so it's readable. */
        [data-testid="stPopoverBody"] [data-testid="stDateInput"] input,
        [data-testid="stPopoverBody"] [data-testid="stTextInput"] input,
        [data-testid="stPopoverBody"] [data-testid="stNumberInput"] input {{
            color: #FFFFFF !important;
        }}
        [data-testid="stPopoverBody"] [data-testid="stDateInput"] input::placeholder,
        [data-testid="stPopoverBody"] [data-testid="stTextInput"] input::placeholder,
        [data-testid="stPopoverBody"] [data-testid="stNumberInput"] input::placeholder {{
            color: rgba(255,255,255,0.6) !important;
        }}
        [data-testid="stPopoverBody"] [data-testid="stNumberInput"] button {{
            color: #FFFFFF !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def masthead(active_tab: str = "Overview") -> None:
    """Logo + wordmark, 4 in-page anchor tabs (real scroll-jumps within the Overview
    page; when viewed from Chat Coach they link back to Overview + the anchor), and
    the Chat Coach page-link styled as its own navy-outlined pill — it's a real page
    change, not a scroll, so it reads as a distinct action rather than a 5th tab."""
    on_overview = active_tab in NAV_TABS
    cols = st.columns([0.35, 0.9, 0.7, 0.7, 0.7, 0.7, 1.3], gap="small")
    with cols[0]:
        st.markdown('<div class="cl-logo-box">L</div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown('<div class="cl-wordmark">LEDGER</div>', unsafe_allow_html=True)
    for i, tab in enumerate(NAV_TABS, start=2):
        anchor = NAV_ANCHORS[tab]
        href = f"#{anchor}" if on_overview else f"1_Overview#{anchor}"
        cls = "cl-tab active" if tab == active_tab else "cl-tab"
        with cols[i]:
            st.markdown(f'<a class="{cls}" href="{href}">{tab}</a>', unsafe_allow_html=True)
    with cols[6]:
        badge_key = "chat-coach-badge-active" if active_tab == "Chat Coach" else "chat-coach-badge"
        with st.container(key=badge_key):
            st.page_link("pages/2_💬_Chat_Coach.py", label="Chat Coach")


def masthead_eyebrow(volume: str, date_str: str) -> None:
    st.markdown(
        f'<div class="cl-masthead-eyebrow">{volume}<span class="rule"></span>{date_str}</div>',
        unsafe_allow_html=True,
    )


def greeting_line(name: str) -> None:
    st.markdown(f'<div class="cl-greeting">{greeting()}, {name}.</div>', unsafe_allow_html=True)


def hero_metric(label: str, value: str) -> None:
    """The banner directly below already states projected-vs-limit in full
    sentence form, so the hero no longer repeats it — just the label + number."""
    st.markdown(
        f"""
        <div class="cl-hero-label">{label}</div>
        <div class="cl-hero-value">{value}</div>
        """,
        unsafe_allow_html=True,
    )


def compact_stat(label: str, value: str, delta_html: str = "") -> None:
    st.markdown(
        f"""
        <div class="cl-stat-label">{label}</div>
        <div class="cl-stat-value">{value}</div>
        {delta_html}
        """,
        unsafe_allow_html=True,
    )


def delta_chip(text: str, color: str) -> str:
    """Returns HTML for a small colored delta line (caller embeds it in compact_stat)."""
    return f'<div class="cl-delta-chip" style="color:{color};">{text}</div>'


def user_badge(uid: int) -> None:
    """A clean badge showing the active customer/user id."""
    st.markdown(f'<span class="cl-badge">Customer ID · {uid}</span>', unsafe_allow_html=True)


def progress_row(label: str, pct: float, color: str) -> None:
    """One row of the 'Where it goes' category share list — a labeled progress bar."""
    st.markdown(
        f"""
        <div class="cl-progress-row">
            <div class="cl-progress-label"><span>{label}</span><span>{pct:.0f}%</span></div>
            <div class="cl-progress-track">
                <div class="cl-progress-fill" style="width:{min(pct, 100):.1f}%; background:{color};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def budget_banner(state: str, message: str) -> None:
    """`state` is 'critical' (red), 'warning' (amber), or 'good' (green) — the
    traffic-light triad, told apart by color + wording, never color alone."""
    css_class = "cl-banner" if state == "good" else f"cl-banner {state}"
    st.markdown(f'<div class="{css_class}">{message}</div>', unsafe_allow_html=True)


def ledger_row(merchant: str, meta: str, amount: float, is_new: bool = False) -> None:
    """One line of the transaction ledger. This dataset is purchases only (all
    amounts are positive spend), so amounts render as "-$X" in ink by default —
    entries added this session (is_new) get a green highlight + NEW tag instead."""
    if is_new:
        amount_class = "cl-ledger-amount new"
    elif amount < 0:
        amount_class = "cl-ledger-amount credit"
    else:
        amount_class = "cl-ledger-amount"
    tag = '<span class="cl-ledger-tag">NEW</span>' if is_new else ""
    avatar_letter = (merchant.strip()[:1] or "?").upper()
    sign = "+" if amount < 0 else "-"
    st.markdown(
        f"""
        <div class="cl-ledger-row">
            <div class="cl-ledger-left">
                <div class="cl-ledger-avatar">{avatar_letter}</div>
                <div>
                    <div class="cl-ledger-merchant">{merchant}{tag}</div>
                    <div class="cl-ledger-meta">{meta}</div>
                </div>
            </div>
            <div class="{amount_class}">{sign}${abs(amount):,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
