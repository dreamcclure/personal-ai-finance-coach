"""Module 5 tests — context building, message assembly, and a mocked coach reply.

No live API calls: a fake client captures the messages and returns a canned reply.
"""
from types import SimpleNamespace

import pandas as pd

from src.categorize import categorize_mcc_codes, fallback_mapping
from src.coach import (
    SYSTEM_PROMPT,
    build_messages,
    build_summary,
    build_user_context,
    coach_reply,
)


def _summary():
    proj = {"reference_month": "2018-02", "ref_day": 15,
            "mtd_discretionary": 520.0, "projected_month_end": 1018.0}
    cat_spend = pd.Series({"Dining": 300.0, "Shopping": 150.0, "Travel": 70.0, "Other": 0.0})
    return build_summary(1696, proj, limit=2238.0, category_spend=cat_spend)


def test_build_summary_picks_top_nonzero_categories():
    s = _summary()
    assert s["client_id"] == 1696
    cats = [c for c, _ in s["top_categories"]]
    assert cats == ["Dining", "Shopping", "Travel"]   # sorted desc, zero dropped
    assert s["mtd"] == 520.0 and s["limit"] == 2238.0


def test_context_contains_required_figures():
    ctx = build_user_context(_summary())
    for token in ["520", "1,018", "2,238", "within budget", "Dining"]:
        assert token in ctx


def test_build_messages_structure():
    ctx = build_user_context(_summary())
    history = [{"role": "user", "content": "hi"},
               {"role": "assistant", "content": "hello"}]
    msgs = build_messages(ctx, history, "how am I doing?")
    assert msgs[0]["role"] == "system"
    assert SYSTEM_PROMPT.split("\n")[0] in msgs[0]["content"]
    assert ctx in msgs[0]["content"]                 # grounding injected
    assert msgs[1:3] == history                      # prior turns preserved
    assert msgs[-1] == {"role": "user", "content": "how am I doing?"}


class _FakeClient:
    """Minimal stand-in for the OpenAI client; records the messages it received."""
    def __init__(self):
        self.captured = None
        create = self._create
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _create(self, model, messages, **kwargs):
        self.captured = messages
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Test coach reply."))])


def test_coach_reply_uses_client_and_grounds():
    cfg = {"llm": {"model": "test-model"}}
    fake = _FakeClient()
    reply = coach_reply(cfg, _summary(), history=[], user_message="Am I over budget?",
                        client=fake)
    assert reply == "Test coach reply."
    # The grounded context (with real figures) was sent to the model.
    assert "CUSTOMER FINANCIAL CONTEXT" in fake.captured[0]["content"]
    assert fake.captured[-1]["content"] == "Am I over budget?"


def test_coach_reply_off_domain_question_carries_refusal_instruction():
    """No live API call, so we can't assert the model actually refuses — this
    verifies the plumbing: an off-domain question still reaches the client with
    the scope/refusal rule intact in the system prompt, not stripped or bypassed."""
    cfg = {"llm": {"model": "test-model"}}
    fake = _FakeClient()
    reply = coach_reply(cfg, _summary(), history=[],
                        user_message="What's the capital of France?", client=fake)
    assert reply == "Test coach reply."
    assert "politely decline unrelated requests" in fake.captured[0]["content"]
    assert fake.captured[-1]["content"] == "What's the capital of France?"


class _AuthFailureClient:
    """Simulates the API call that would happen with a missing/invalid API key
    (e.g. an AuthenticationError) — coach_reply() itself has no try/except, so
    the client raising is what a missing key looks like from its perspective."""
    def __init__(self):
        create = self._create
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _create(self, model, messages, **kwargs):
        raise Exception("Incorrect API key provided")


def test_missing_api_key_falls_back_for_categorization_and_chat(tmp_path):
    """Simulates a missing LLM_API_KEY end-to-end, same as config.py produces
    when LLM_API_KEY isn't set (cfg["llm"]["api_key"] is None):
    (1) categorize_mcc_codes() must skip the LLM call entirely and fall back to
        the deterministic keyword rule, not error.
    (2) coach_reply() has no built-in fallback (confirmed: it propagates the
        client's failure) — the friendly message is produced by the try/except
        in app/pages/2_💬_Chat_Coach.py around the coach_reply() call. This
        mirrors that exact pattern to confirm it turns a raised exception into
        the friendly string instead of crashing the page.
    """
    # --- (1) Categorization fallback ---
    mcc = {"5812": "Eating Places and Restaurants", "5411": "Grocery Stores, Supermarkets"}
    cfg = {
        "llm": {"api_key": None, "model": "test-model", "base_url": None},
        "buckets_file": tmp_path / "buckets.json",
    }
    mapping = categorize_mcc_codes(mcc, cfg, use_cache=False, use_llm=True)
    assert mapping == fallback_mapping(mcc)  # no API call attempted; keyword rule used

    # --- (2) Chat coach friendly fallback (page-level try/except, mirrored here) ---
    try:
        coach_reply(cfg, _summary(), history=[], user_message="Am I over budget?",
                    client=_AuthFailureClient())
        reply = None
    except Exception as e:  # keep the UI alive if the API hiccups
        reply = f"Sorry — I couldn't reach the coach service right now ({type(e).__name__})."
    assert reply == "Sorry — I couldn't reach the coach service right now (Exception)."
