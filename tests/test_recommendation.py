"""
Recommendation engine tests (decisions D006a, D007a, D019).

Uses the real database (real catalog + real design_principles with real
embeddings) rather than mocks — the whole point of D006a's RAG mechanism is
that citations resolve to genuine stored rows, which a mock would hide a
bug in.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ai.recommendation.scoring import generate_recommendation
from ai.room_analysis.fixtures import FIXTURES
from ai.room_analysis.room_model import FurnitureItem, RoomModel
from backend.db import get_engine
from backend.models.principle import DesignPrinciple


def _db(app):
    from backend.db import get_engine as _get_engine

    return Session(_get_engine())


def test_recommendation_stays_within_budget_when_catalog_allows_it(app):
    fixture = FIXTURES["bedroom_small_scandinavian"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Scandinavian", preferred_colors=["white", "natural wood"], budget=100000,
        )
    assert result.total_cost <= result.budget
    assert result.within_budget is True


def test_every_recommended_item_has_full_score_breakdown(app):
    fixture = FIXTURES["living_room_modern_cluttered"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Contemporary", preferred_colors=["charcoal"], budget=80000,
        )
    assert len(result.items) > 0
    for item in result.items:
        for key in ("style_match", "color_match", "budget_fit", "space_fit"):
            assert key in item.score_breakdown
            assert 0.0 <= item.score_breakdown[key] <= 1.0


def test_rationale_citations_resolve_to_real_principle_rows(app):
    fixture = FIXTURES["study_room_industrial"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Industrial", preferred_colors=["black metal"], budget=40000,
        )
        cited_codes = {code for item in result.items for code in item.score_breakdown["principle_citations"]}
        assert cited_codes, "expected at least one principle to be cited across all recommended items"
        real_codes = {p.code for p in db.query(DesignPrinciple).filter(DesignPrinciple.code.in_(cited_codes)).all()}
        assert cited_codes == real_codes, "every cited code must resolve to a real design_principles row"


def test_existing_furniture_suppresses_matching_category_need(app):
    # bedroom_small_scandinavian already has an "Old Wardrobe" -> cabinet
    # category should NOT appear among recommended categories.
    fixture = FIXTURES["bedroom_small_scandinavian"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Scandinavian", preferred_colors=["white"], budget=100000,
        )
    categories = {item.category for item in result.items}
    assert "cabinet" not in categories


def test_style_mismatch_flags_existing_category_for_replacement(app):
    # bedroom_small_scandinavian's "Old Wardrobe" already covers "cabinet",
    # so a matching preferred_style (see the suppression test above) skips
    # it entirely. Asking for a style the room *doesn't* currently have
    # (2026-09-18 feature) should instead flag it as a real "replace"
    # suggestion, not silently leave the mismatched item alone.
    fixture = FIXTURES["bedroom_small_scandinavian"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Industrial", preferred_colors=["black metal"], budget=100000,
        )
    cabinet_items = [i for i in result.items if i.category == "cabinet"]
    assert len(cabinet_items) == 1
    assert cabinet_items[0].action == "replace"
    assert "Old Wardrobe" in cabinet_items[0].replaces_labels
    assert "Old Wardrobe" in result.replaced_existing_labels
    assert "Old Wardrobe" in cabinet_items[0].rationale


def test_matching_style_never_flags_a_replacement(app):
    # Companion to the mismatch test above: when preferred_style already
    # matches what's detected, no category should ever come back as
    # "replace" — this is the "only if necessary" guarantee.
    fixture = FIXTURES["bedroom_small_scandinavian"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style=fixture.style.predicted_style, preferred_colors=["white"], budget=100000,
        )
    assert all(item.action != "replace" for item in result.items)
    assert result.replaced_existing_labels == []


def test_user_confirmed_existing_item_is_never_flagged_for_replacement(app):
    # A user-confirmed item (the one path where someone deliberately placed
    # a real piece via the "confirm geometry" flow) is a deliberate keep,
    # not something a coarse room-level style mismatch should override —
    # unlike a fixture's given/known furniture, which IS replace-eligible
    # (see test_style_mismatch_flags_existing_category_for_replacement).
    room = RoomModel(
        room_type="bedroom", width_cm=400, length_cm=500,
        existing_furniture=[
            FurnitureItem(
                label="Old Wardrobe", width_cm=100, depth_cm=55, height_cm=180,
                category="cabinet", user_confirmed=True,
            )
        ],
    )
    with _db(app) as db:
        result = generate_recommendation(
            db, room=room, detected_style="Traditional",
            preferred_style="Industrial", preferred_colors=["black metal"], budget=100000,
        )
    assert all(item.category != "cabinet" for item in result.items)
    assert result.replaced_existing_labels == []


def test_zero_budget_still_returns_a_closest_fit_flagged_over(app):
    fixture = FIXTURES["office_contemporary_empty"]
    with _db(app) as db:
        result = generate_recommendation(
            db, room=fixture.room, detected_style=fixture.style.predicted_style,
            preferred_style="Contemporary", preferred_colors=["white"], budget=1.0,
        )
    assert len(result.items) > 0  # still recommends something per category, per D019
    assert result.within_budget is False
    assert any("over" in item.rationale.lower() for item in result.items)
