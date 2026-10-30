# ClearLedger — AI-Assisted Development Chat Trail

**Project:** ClearLedger Personal Finance Coach & Spending Analyzer (JHU Week 3, Project 1)
**AI pair-programmer:** Claude (Anthropic), used inside PyCharm.
**Purpose of this document:** a structured record of the back-and-forth AI-assisted build,
organized around milestones. It is a living log, updated as the project progresses.

> **Provenance note.** This is an organized record of the collaborative session. The full
> verbatim IDE chat transcript is the primary artifact; this document maps that same
> back-and-forth to the build milestones and the grading rubric.

---

## Rubric alignment (Criteria 1 — AI-Assisted Build, 20 pts)

| Item | Pts | Evidence in this trail |
|---|---|---|
| Planning prompt → end-to-end plan | 5 | §1 below (prompt reproduced) → produced `PROJECT_SPEC.md` |
| Step-by-step execution with clear guardrails | 10 | §2 build log (Modules 1–4 so far), §3 guardrails |
| Validation hooks + unit tests | 5 | §4 — 25 passing tests + headless UI test |

---

## 1. Planning phase

**Approach.** Before writing code, the student authored a formal planning prompt asking the
AI to produce an end-to-end implementation plan structured to the rubric's 9 spec sections.
The prompt was iterated twice: (v1) accidentally described a different project → corrected;
(v2) added ground-truth data facts + a design-justification requirement.

**Final planning prompt (verbatim, abridged header):**
> *MISSION: Generate a comprehensive, step-by-step implementation plan for the ClearLedger
> Personal Finance Coach & Spending Analyzer. Role: Lead GenAI Architect & FinTech Solutions
> Engineer. Target user 1696. Stack: Python + Streamlit + external LLM (categorization) +
> scikit-learn regression. Includes verified ground-truth data facts (699,938 transactions;
> $-formatted currency strings; mcc int↔json-string cast; user 1696 = 30,672 txns; data ends
> per-user, simulate a reference date). Output organized into 9 sections: Intro, Problem
> Statement, Architecture, Folder Structure, Dataset Spec, Module Spec (5 modules), Environment
> & Config, Known Constraints, Evaluation Checklist & QA. For each major design decision,
> justify against an alternative.*

**Output:** `PROJECT_SPEC.md` (all 9 sections + design justifications). Student reviewed against
the rubric and approved. Added Module 6 (enhancements: unusual-charge detection, recurring/
subscription finder, what-if slider) as explicitly build-after-core.

---

## 2. Step-by-step build log (core, module by module)

Each module was built in flow order, with guardrails and unit tests before moving on.

### Module 1 — Data loading & cleaning (`src/data_loader.py`, `src/config.py`)
- Loads the 4 raw files; `parse_currency()` converts `"$1,755"`→float; casts `mcc` int→str
  for the JSON join; `build_master()` joins transactions↔users↔cards↔mcc; `load_user()` filters.
- Config in `config.yaml` + secrets in `.env` (no hard-coding).
- **Result:** 699,938 rows, 100% parse/coverage. User 1696 = 30,672 txns, limit $2,238.
- **Tests:** 9 passing.

### Module 2 — LLM categorization (`src/categorize.py`)
- LLM classifies the **109 unique MCC codes once** → 13 fixed buckets → cached to
  `data/processed/mcc_category_map.json`. Transactions categorized by cheap dict-join.
- Priority: cache → LLM (via Great Learning gateway, gpt-4o-mini) → deterministic keyword
  fallback. `_validate_and_fill()` guarantees every code maps to a valid bucket.
- **Result:** 109 codes → 12 buckets; spot-checks correct. User 1696 discretionary = 11% of spend.
- **Tests:** 6 passing (offline).

### Module 3 — Month-end prediction (`src/features.py`, `src/predict.py`)
- Builds per-(user, month) features (MTD spend, history, seasonality); target = full-month
  discretionary. Trains `GradientBoostingRegressor(seed=42)` + `LinearRegression` baseline on
  ALL users; leakage-safe (features use only days ≤ reference day).
- **Fix discovered during build:** users' histories end at different times, so "current month"
  = each user's *latest active month* (user 1696 ends 2018-02, not the global 2019-10).
- **Result:** R² ≈ 0.85–0.86. User 1696 @ 2018-02-15: MTD $520 → projected $1,018 vs $2,238 limit.
- **Tests:** 6 passing.

### Module 4 — Streamlit dashboard (`app/app.py`, `src/recommend.py`)
- All rubric UI elements: customer controls (user selector, toggles, category filter), MTD +
  predicted-month-end + limit metric cards, monthly limit meter (gauge), category breakdown
  donut, category spending-trend line chart, recommendations (rule-based, grounded).
- **Tests:** 4 passing, including a headless `AppTest` that runs the whole app and asserts no
  exception. **(Visual polish deferred to a design pass at the end.)**

### Module 5 — Chat coach (`src/coach.py`, `app/pages/2_💬_Chat_Coach.py`)
- Grounded, multi-turn Streamlit chat. `build_summary()` assembles the user's real metrics;
  `build_user_context()` renders them into a factual block injected into a constrained system
  prompt (use ONLY provided facts, no invented numbers, stay on this user's finances).
  `coach_reply()` calls the LLM (gateway) and accepts an injected client for testing.
- Shared pipeline factored into `app/_shared.py` (`load_everything`, `get_user_view`) so the
  dashboard and chat page reuse one cached load/train and show consistent figures.
- Chat page shows the required MTD / Projected / Limit figures + a chat box with per-user memory.
- **Tests:** 4 (context/messages/summary + a mocked coach reply). Verified live: a real grounded
  reply for user 1696 cited the correct $1,018 / $2,238 figures.

### Module 6 — Enhancements (`src/insights.py` + dashboard What-if)
- `unusual_charges()` — flags transactions above (category mean + 3·std), only for categories
  with enough history. `recurring_merchants()` — merchants billed repeatedly at a stable amount
  (low CV) with ~monthly cadence → likely subscriptions.
- **What-if savings slider** on the dashboard: pick a category + % cut → live-recomputes
  projected month-end vs. limit.
- **Tests:** 3. Verified on user 1696: 10 unusual charges (e.g. $1,916 cruise), 1 recurring
  merchant (~$74/mo). All core + enhancement work is now complete.

---

## 3. Guardrails (implemented across modules)
- Required-column checks with clear errors (`_check_columns`).
- Safe currency parsing: bad/blank values → NaN, never a crash.
- `load_user()` raises if a user has no transactions.
- Categorization: LLM output validated against the allowed bucket set; missing/invalid →
  keyword fallback; whole LLM path wrapped in try/except → offline fallback.
- JSON-from-LLM parsing tolerates code fences / prose.
- Prediction cannot return a month-end below money already spent (MTD floor).

## 4. Validation hooks & unit tests
- `tests/test_data_loader.py` (9), `tests/test_categorize.py` (6), `tests/test_predict.py` (6),
  `tests/test_recommend.py` (4, incl. headless dashboard run), `tests/test_coach.py` (4),
  `tests/test_insights.py` (3). **Total: 32 passing.**
- `validation_report()` health metrics (row counts, parse rates, mcc coverage).
- Run all: `./.venv/bin/python -m pytest`

## 5. Key design decisions (each vs. an alternative)
- **Categorize 109 codes once, cached** (vs. per-transaction LLM calls) → ~6,000× fewer calls.
- **Train on all users, predict per user** (vs. single-user model) → more robust.
- **GradientBoosting + LinearRegression baseline** (vs. single model) → honest comparison.
- **Per-user latest month as "current"** (vs. global fixed date) → works for every user.
- **Great Learning gateway** via `base_url` (course-issued `gl-` key) with `.env` kept private.

## 6. Environment
- Python 3.12; deps pinned in `requirements.txt` (pandas, scikit-learn, streamlit, plotly,
  openai, pyyaml, python-dotenv, pyarrow, pytest).

---

## Running log
- 2026-07-09: Planning prompt iterated + `PROJECT_SPEC.md` generated; env created; Module 1 built.
- 2026-07-10: Modules 2–4 built; 25 tests passing; dashboard launched & viewed; code walkthrough
  begun (data_loader ✅, categorize ✅). Created this CHAT_TRAIL.md.
- 2026-07-10: Code-review refactor (student-spotted): `reference_date` (only its day was ever
  used, after the per-user-latest-month fix) → replaced with explicit `reference_day: 15` +
  a validating `get_reference_day()` (clamped 1..28). Updated config.yaml, features.py,
  predict.py, app/app.py, tests, PROJECT_SPEC. All 25 tests still pass; predictions unchanged.
- 2026-07-10: Silenced 3 sklearn type-checker false-positives in predict._metrics (# type: ignore).
- 2026-07-10: Module 5 (chat coach) built; pipeline factored into app/_shared.py; dashboard
  refactored to use it. 29 tests passing. Core project (Modules 1–5) COMPLETE. Verified a live
  grounded coach reply for user 1696.
- 2026-07-10: Module 6 enhancements built (src/insights.py: unusual charges + recurring
  merchants; dashboard What-if slider). 32 tests passing. Verified on user 1696.
- 2026-07-10: README.md written (intro, project structure, execution steps, output files,
  guardrails). Remaining: optional visual polish + export/generate submission PDFs.
- 2026-07-10: Visual polish pass, iterated in two rounds (good example of the guardrail/
  validation-hook back-and-forth this rubric section rewards). Round 1: built app/theme.py
  (shared CSS + fixed category-color map) to match the assignment's frontend mockup —
  dark sidebar, gradient header, card-style metrics, consistent chart colors, applied to
  both Streamlit pages. Then implemented 3 targeted enhancements per a follow-up spec:
  KPI metric grid (st.columns(3)), a conditional st.error/warning/success budget-status
  banner, and chat message avatars (👤/🧠). Round 2: pivoted the whole visual direction to
  a black-and-white editorial style per a design reference the student provided, after
  confirming scope with the student first (color strictness + whether to replace or layer
  the prior theme). Rebuilt theme.py around a grayscale category ramp + one reserved accent
  color (red, over-budget only); added direct labels to the donut and line-dash patterns to
  the trend chart so category identity never depends on color alone; replaced the built-in
  st.error/warning/success calls with a custom theme.budget_banner() component, since
  Streamlit's built-in alert colors can't be cleanly restyled to stay near-B&W — a deliberate,
  disclosed deviation from the literal enhancement spec, not a silent one. Verified with
  32/32 tests passing plus a headless AppTest run of both pages (no exceptions) after a stale
  dev-server process (module caching, not a code bug) briefly showed an AttributeError.
  Visual direction is a checkpoint, not final — student is pausing to gather concrete font/
  color/screenshot references before the next round.
