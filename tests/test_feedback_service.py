"""
Feedback text-parsing tests (decision D024). Exercises the rule-based path
directly (no Gemini key needed) since that's the guaranteed-available
default; Gemini is exercised (if at all) only when GEMINI_API_KEY is set —
see test_parse_feedback_falls_back_when_no_key_configured.
"""
from __future__ import annotations

from backend.services.feedback_service import parse_feedback

ITEMS = [
    {"catalog_item": {"id": 1, "name": "Platform Bed Frame (Queen)"}},
    {"catalog_item": {"id": 2, "name": "Paper Lantern Pendant Light"}},
    {"catalog_item": {"id": 3, "name": "Monstera Plant + Ceramic Pot"}},
]


def test_keep_and_remove_in_the_same_sentence():
    deltas = parse_feedback("Keep the bed frame but remove the lantern light", ITEMS, current_budget=60000)
    assert deltas["keep_item_ids"] == [1]
    assert deltas["remove_item_ids"] == [2]


def test_style_shift_detected():
    deltas = parse_feedback("I don't like this style, make it more minimalist", ITEMS, current_budget=60000)
    assert deltas["style_shift"] == "Minimalist"


def test_cheaper_reduces_budget_by_fixed_fraction():
    deltas = parse_feedback("reduce cost please", ITEMS, current_budget=60000)
    assert deltas["budget_delta"] == -9000.0  # 15% of 60000, documented fixed heuristic


def test_pricier_increases_budget():
    deltas = parse_feedback("I want a bigger budget", ITEMS, current_budget=40000)
    assert deltas["budget_delta"] == 6000.0


def test_crowding_shift_less():
    deltas = parse_feedback("make the room less crowded", ITEMS, current_budget=50000)
    assert deltas["crowding_shift"] == "less"


def test_crowding_shift_more():
    deltas = parse_feedback("add more furniture please", ITEMS, current_budget=50000)
    assert deltas["crowding_shift"] == "more"


def test_unrecognized_feedback_returns_empty_deltas_not_a_crash():
    deltas = parse_feedback("I prefer design 2", ITEMS, current_budget=50000)
    assert deltas["keep_item_ids"] == []
    assert deltas["remove_item_ids"] == []
    assert deltas["style_shift"] is None
    assert deltas["budget_delta"] is None


def test_parse_feedback_falls_back_when_no_key_configured():
    # gemini_api_key=None must never raise or hang — falls straight to rules.
    deltas = parse_feedback("remove the plant", ITEMS, current_budget=50000, gemini_api_key=None)
    assert deltas["remove_item_ids"] == [3]


def test_item_name_with_parenthetical_qualifier_still_matches():
    # Regression guard: "(Queen)" must not become the match keyword.
    deltas = parse_feedback("please keep the bed", ITEMS, current_budget=50000)
    assert 1 in deltas["keep_item_ids"]
