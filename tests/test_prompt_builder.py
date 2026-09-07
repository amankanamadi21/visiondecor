"""
D023 layout->prompt translator tests. The key regression guard is against
circular references (two new items describing each other), which is a real
bug this module used to have.
"""
from __future__ import annotations

import pytest

from ai.layout_optimization.optimizer import PlacementSpec, optimize_layout
from ai.room_analysis.fixtures import FIXTURES
from ai.visualization.prompt_builder import _article_for, build_edit_prompt

# Deliberately modest sizes — must fit comfortably in the smallest fixture
# (study_room_industrial, 260x300cm, already containing an existing desk).
# This test is about the generated prompt text, not optimizer feasibility
# limits (covered separately in test_layout_optimization.py).
SPECS = [
    PlacementSpec(label="Glass Coffee Table", width_cm=70, depth_cm=45, height_cm=40, category="table"),
    PlacementSpec(label="Arc Floor Lamp", width_cm=30, depth_cm=30, height_cm=165, category="lighting"),
    PlacementSpec(label="Small Area Rug", width_cm=90, depth_cm=60, height_cm=1, category="rug"),
]


@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_prompt_mentions_style_and_no_crash(fixture_name):
    fixture = FIXTURES[fixture_name]
    result = optimize_layout(fixture.room, SPECS, iterations=300)
    all_items = [*fixture.room.existing_furniture, *result.placed_items]
    prompt = build_edit_prompt(fixture.room, all_items, style="Modern")
    assert "Modern" in prompt
    assert prompt.endswith(".")


def test_no_circular_new_item_references():
    fixture = FIXTURES["living_room_modern_cluttered"]
    result = optimize_layout(fixture.room, SPECS, iterations=300)
    all_items = [*fixture.room.existing_furniture, *result.placed_items]
    prompt = build_edit_prompt(fixture.room, all_items, style="Contemporary")

    new_labels = {"glass coffee table", "arc floor lamp", "small area rug"}
    for label in new_labels:
        others = new_labels - {label}
        for other in others:
            assert f"{label} near the {other}" not in prompt.lower()


def test_existing_items_are_mentioned_as_kept():
    fixture = FIXTURES["bedroom_small_scandinavian"]
    result = optimize_layout(fixture.room, SPECS[:1], iterations=200)
    all_items = [*fixture.room.existing_furniture, *result.placed_items]
    prompt = build_edit_prompt(fixture.room, all_items, style="Scandinavian")
    assert "Old Wardrobe" in prompt
    assert "keep" in prompt.lower()


def test_palette_included_when_provided():
    fixture = FIXTURES["office_contemporary_empty"]
    result = optimize_layout(fixture.room, SPECS[:1], iterations=200)
    all_items = [*fixture.room.existing_furniture, *result.placed_items]
    prompt = build_edit_prompt(
        fixture.room, all_items, style="Contemporary", palette={"preferred_colors": ["charcoal", "white"]}
    )
    assert "charcoal" in prompt and "white" in prompt


@pytest.mark.parametrize(
    "label,expected",
    [("Arc Floor Lamp", "an"), ("Ottoman", "an"), ("Sofa", "a"), ("TV Console Unit", "a")],
)
def test_article_selection(label, expected):
    assert _article_for(label) == expected
