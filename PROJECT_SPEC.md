# PROJECT_SPEC.md — ClearLedger Personal Finance Coach & Spending Analyzer

## I. Intro

ClearLedger is a Python + Streamlit application that turns a user's raw card-transaction
history into a personal finance coach. For a target user it (1) cleans and joins four raw
data sources, (2) uses an LLM to categorize spending into interpretable buckets, (3) trains
a regression model to project month-end discretionary spend against the user's stated limit,
(4) renders an interactive dashboard, and (5) exposes a grounded, multi-turn chat coach.

All deliverable outputs are scoped to **target user ID 1696**.

- **Language / runtime:** Python 3.12, local `.venv`, developed in PyCharm.
- **Frontend:** Streamlit (dashboard + chat).
- **AI layer:** external LLM (provider-configurable) for transaction categorization + chat grounding.
- **ML layer:** scikit-learn regression (`random_state=42`) for month-end spend projection.
- **Design principle:** the LLM categorizes the **109 unique MCC codes once** (cached), never
  the 699,938 individual transactions — keeping the app fast, cheap, reproducible, and
  runnable offline after the first pass.

## II. Problem Statement

ClearLedger (pre-Series-B fintech, ~55k users) suffers ~71% second-session churn: users
abandon the app before it delivers value. The strategic fix is proactive, personalized
coaching that (a) makes spending legible, (b) warns users *before* they blow their monthly
discretionary limit, and (c) answers money questions conversationally.

**Design requirements**
- Ingest raw transaction/card/user data with no manual tagging.
- Categorize every transaction into a small, human-meaningful set of spending buckets.
- Track month-to-date (MTD) discretionary spend and project the month-end total vs. the
  user's `monthly_discretionary_limits`.
- Surface category-level savings recommendations grounded in the user's own data.
- Provide a chat coach that answers only from user-specific context (no hallucinated numbers).
- Demonstrate the full flow for **user 1696** (30,672 transactions on record).

## III. Architecture

```
                      ┌─────────────────────────────────────────────┐
   RAW FILES          │                DATA LAYER                    │
 ┌───────────────┐    │  data_loader.py                              │
 │ transactions  │───▶│   • parse "$" currency strings → float       │
 │ cards         │───▶│   • cast mcc int ↔ json str keys             │
 │ users         │───▶│   • join transactions↔users↔cards↔mcc        │
 │ mcc_codes.json│───▶│   • filter to a user (e.g. 1696)              │
 └───────────────┘    └───────────────────┬─────────────────────────┘
                                           │ clean, joined frame
                         ┌─────────────────┴──────────────────┐
                         ▼                                     ▼
        ┌────────────────────────────┐        ┌──────────────────────────────┐
        │  CATEGORIZATION (LLM)       │        │  PREDICTION (scikit-learn)     │
        │  categorize.py              │        │  features.py + predict.py      │
        │   • map 109 MCC descs →     │        │   • build user-month features  │
        │     spending buckets (once) │        │   • regress month-end spend    │
        │   • cache to processed/     │        │   • MTD + projection vs limit  │
        └──────────────┬──────────────┘        └───────────────┬───────────────┘
                       │ categorized transactions              │ metrics + forecast
                       └───────────────┬───────────────────────┘
                                       ▼
                     ┌──────────────────────────────────────────┐
                     │              STREAMLIT UI                 │
                     │  app.py / pages/                          │
                     │   • Dashboard: limit meter, MTD, projected,│
                     │     category trend chart, recommendations │
                     │   • Chat coach: grounded, multi-turn      │
                     └──────────────────────────────────────────┘
```

Data flows one direction: files → cleaned frame → (categorization ∥ prediction) → UI. The
chat coach reads the *same* computed metrics the dashboard uses, so numbers never diverge.

## IV. Folder Structure

```
P1_Finance_McClureDrea/
├── data/
│   ├── transactions.csv          # raw (read-only)
│   ├── cards.csv                 # raw
│   ├── users.csv                 # raw
│   ├── mcc_codes.json            # raw
│   └── processed/                # generated
│       ├── mcc_category_map.json # cached LLM MCC→bucket mapping
│       └── user_1696_clean.parquet
├── src/
│   ├── config.py                 # loads config.yaml + .env
│   ├── data_loader.py            # load, clean, join, filter
│   ├── categorize.py             # LLM MCC→bucket mapping (+ cache + fallback)
│   ├── features.py               # user-month feature engineering
│   ├── predict.py                # train/load regression, MTD + projection
│   ├── recommend.py              # category-level savings suggestions
│   ├── coach.py                  # grounded chat logic (LLM + user context)
│   └── insights.py               # ENHANCEMENT: unusual-charge + recurring/subscription detection
├── app/
│   ├── app.py                    # Streamlit entry point: top-nav router (st.navigation)
│   ├── theme.py                  # shared CSS/palette/UI helpers for both pages
│   └── pages/
│       ├── 1_Overview.py         # dashboard content (dispatched by the router)
│       └── 2_💬_Chat_Coach.py    # Streamlit chat page (emoji in the filename gives it a nav icon)
├── tests/
│   ├── test_data_loader.py
│   ├── test_categorize.py
│   ├── test_predict.py
│   ├── test_coach.py
│   └── test_insights.py          # ENHANCEMENT tests
├── .env.example                  # API key template (no secrets committed)
├── config.yaml                   # paths, reference date, seeds, buckets
├── requirements.txt
├── PROJECT_SPEC.md
└── README.md
```

## V. Dataset Spec

| File | Rows | Key fields | Cleaning / notes |
|---|---|---|---|
| `transactions.csv` | 699,938 | id, date, client_id, card_id, amount, mcc, merchant_* | `amount` is text `"$4.81"` → strip `$`,`,` → float; parse `date` → datetime; dates 2010-01-01…2019-10-31 |
| `users.csv` | 100 | id, monthly_discretionary_limits, demographics | money fields are `$`-strings → float |
| `cards.csv` | 300 | id, client_id (→users.id), credit_limit, card_type | `credit_limit` `$`-string → float |
| `mcc_codes.json` | 109 | code → description | **keys are strings** (`"5812"`); `transactions.mcc` is **int** → cast on join |

**Join logic:** `transactions.client_id → users.id`; `transactions.card_id → cards.id`;
`str(transactions.mcc) → mcc_codes` key. Filter to `client_id == 1696` for deliverables.

**Currency parser (shared util):** `"$1,755" → 1755.0`; empty/NaN → configurable default;
non-parseable → logged + coerced to NaN (never a silent crash).

**Validation protocols:** row-count checks after each load; assert no unmatched `mcc` after
join (report coverage %); assert `amount` parse success rate ≥ threshold; verify user 1696
has > 0 rows before proceeding.

## VI. Module Spec

**Module 1 — Data Logistics (`data_loader.py`)**
Load 4 files; parse currency + dates; cast `mcc`; join into one frame; expose
`load_user(client_id)`. Defensive: missing file/column → explicit error; bad rows logged.

**Module 2 — LLM Categorization (`categorize.py`)**
Map each of the **109 MCC descriptions** → one spending bucket + `is_discretionary` flag,
via a structured LLM prompt returning strict JSON. **Cache** to `processed/mcc_category_map.json`.
Fallback: if the API is unavailable or a code is unmapped, a deterministic keyword rule
assigns a bucket (default `"Other"`). Transactions are categorized by *joining* this small
map — no per-transaction LLM calls.
- Buckets (initial): Housing, Utilities, Groceries, Transportation, Healthcare, Insurance
  (non-discretionary); Dining, Entertainment, Shopping, Travel, Personal Care, Subscriptions,
  Other (discretionary). Discretionary buckets feed the limit meter.

**Module 3 — Prediction (`features.py` + `predict.py`)**
Build user-month rows: features = [MTD discretionary spend at reference day, day-of-month,
days-in-month, user rolling avg monthly discretionary, prior-month total, category mix].
Target = full-month discretionary total. Train `GradientBoostingRegressor(random_state=42)`
with a `LinearRegression` baseline; report MAE/RMSE/R². At runtime: compute **MTD spend** and
**projected month-end spend** for the reference month; compare to the user's limit.

**Module 4 — Streamlit Dashboard (`app/app.py` router + `app/pages/1_Overview.py`)**
For user 1696: (a) **monthly limit meter** actual-MTD vs projected vs limit; (b) **customer
controls** (user selector, reference-date/category filters); (c) **predicted month-end spend**;
(d) **MTD discretionary spend**; (e) **category trend chart** (spend per bucket over time) +
category buckets breakdown; (f) **recommendations** section (from `recommend.py`).

**Module 5 — Chat Coach (`app/pages/2_💬_Chat_Coach.py` + `coach.py`)**
Multi-turn chat using `st.session_state` for history. Every prompt is grounded with user
1696's computed metrics (MTD, limit, projected, top categories) so answers cite real numbers.
Guardrail: system prompt restricts scope to the user's finances; refuses/deflects off-domain
or fabricated-number requests.

**Module 6 — Enhancements (`insights.py` + dashboard controls) — BUILD AFTER CORE IS END-TO-END**
These are stretch features layered on only once Modules 1–5 run cleanly for user 1696. Each
reuses data already computed, so it adds value without new data plumbing.
1. **Unusual-charge detection** — flag transactions far above the user's normal for that
   category (e.g. amount > mean + 3·std, or a robust MAD rule). Surfaces as a dashboard
   "insights" alert and feeds `recommend.py`. *(Shown in the project's frontend mockup.)*
2. **Recurring / subscription finder** — detect merchants with regular repeat charges of
   similar amount/cadence; report count and monthly total (e.g. "4 subscriptions, $52/mo")
   to power "cancel unused" savings advice.
3. **"What-if" savings slider** — a Streamlit slider that cuts a chosen category by X% and
   live-recomputes projected month-end spend vs. limit, showing the dollar impact.

Sequencing rule: ship a complete core first; if time is short, these are dropped without
breaking the graded deliverables.

## VII. Environment & Config

**`.env.example`**
```
LLM_PROVIDER=anthropic          # or openai
LLM_API_KEY=your_key_here
LLM_MODEL=claude-haiku-4-5
```

**`config.yaml`**
```
paths:
  data_dir: data
  processed_dir: data/processed
reference_day: 15                # simulated mid-month cutoff day for MTD / projection
random_seed: 42
target_user: 1696
buckets_file: data/processed/mcc_category_map.json
```
Config is loaded once by `config.py`; no paths/keys/seeds hard-coded in logic.

## VIII. Known Constraints & Limitations

- **API cost/rate:** mitigated by categorizing only 109 codes once and caching; chat is the
  only live-API surface at runtime.
- **LLM latency / tokens-per-minute:** chat responses depend on provider latency; categorization
  is a one-time batch.
- **Temporal edge case:** the dataset ends 2019-10-31, but each user's history ends at a
  different time (e.g. user 1696 ends 2018-02). The "current month" is therefore each user's
  **latest active month**, with `reference_day` (the 15th) as the simulated mid-month
  MTD cutoff — not wall-clock time.
- **No ground-truth categories:** LLM bucketing is unvalidated against labels; treated as
  best-effort and spot-checked in tests.
- **Per-user sparsity:** only 66/100 users have transactions; single-user (1696) demo scope.
- **Discretionary definition** is an assumption (bucket→flag map), documented and editable.

## IX. Evaluation Checklist & QA Quality Gates

| Gate | Check | Where |
|---|---|---|
| Load integrity | row counts match expected; required columns present | test_data_loader |
| Currency parse | `"$1,755"`→1755.0; commas/symbols stripped; bad→NaN not crash | test_data_loader |
| MCC join | `int`↔`str` cast works; coverage % reported; no silent drops | test_data_loader |
| User filter | user 1696 returns > 0 rows | test_data_loader |
| Categorization | every bucket in allowed set; unmapped→fallback "Other"; JSON schema valid | test_categorize |
| Prediction shapes | feature matrix has expected columns; no NaN into model; projection ≥ MTD | test_predict |
| Reference day | MTD only counts spend on/before reference_day within the month | test_predict |
| Chat grounding | coach output includes MTD/limit/projected when asked; refuses off-domain | test_coach |

**Guardrails (runtime):** typed exceptions for missing files/columns, empty user, unseen MCC,
empty chat input, missing API key (→ fallback path). **Validation hooks:** shape/dtype asserts
at each module boundary. **Unit tests:** `pytest` suites above, runnable via `pytest` from root.

---
*This spec is the build blueprint. Implementation proceeds module-by-module (1→5), each with
its validation hooks and tests before moving on.*
