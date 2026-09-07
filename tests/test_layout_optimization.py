"""
Layout optimiser correctness tests (decisions D008/D020/D021).

These are property tests, not example tests: for every fixture room, the
optimiser's output must NEVER violate a hard constraint, regardless of how
the soft objective trades off. That property matters more than any single
example, since D020 makes hard-constraint satisfaction a strict guarantee,
not a preference.
"""
from __future__ import annotations

import pytest

from ai.layout_optimization.constraints import check_all_hard_constraints, no_overlap
from ai.layout_optimization.optimizer import (
    LayoutInfeasibleError,
    PlacementSpec,
    optimize_layout,
)
from ai.room_analysis.fixtures import FIXTURES
from ai.room_analysis.room_model import FurnitureItem, Opening, RoomModel

SAMPLE_SPECS = [
    PlacementSpec(label="Test Bed", width_cm=160, depth_cm=200, height_cm=35, category="bed"),
    PlacementSpec(label="Test Lamp", width_cm=30, depth_cm=30, height_cm=165, category="lighting"),
    PlacementSpec(label="Test Decor", width_cm=40, depth_cm=40, height_cm=90, category="decor"),
]


@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
def test_optimizer_result_satisfies_every_hard_constraint(fixture_name):
    fixture = FIXTURES[fixture_name]
    result = optimize_layout(fixture.room, SAMPLE_SPECS, iterations=400)

    assert all(result.constraints_satisfied.values()), result.constraints_satisfied

    # Re-derive independently from the placed items, rather than trusting
    # the optimiser's own self-report, to catch a bug in how it tracks state.
    all_items = [*fixture.room.existing_furniture, *result.placed_items]
    assert no_overlap(all_items)
    for item in result.placed_items:
        x0, y0, x1, y1 = item.bounds
        assert x0 >= -1e-6 and y0 >= -1e-6
        assert x1 <= fixture.room.width_cm + 1e-6
        assert y1 <= fixture.room.length_cm + 1e-6


def test_same_seed_produces_identical_layout():
    fixture = FIXTURES["bedroom_small_scandinavian"]
    result_a = optimize_layout(fixture.room, SAMPLE_SPECS, seed=7, iterations=300)
    result_b = optimize_layout(fixture.room, SAMPLE_SPECS, seed=7, iterations=300)

    positions_a = [(round(i.x_cm, 3), round(i.y_cm, 3), i.rotation_deg) for i in result_a.placed_items]
    positions_b = [(round(i.x_cm, 3), round(i.y_cm, 3), i.rotation_deg) for i in result_b.placed_items]
    assert positions_a == positions_b
    assert result_a.score.total_score == result_b.score.total_score


def test_different_seeds_can_produce_different_layouts():
    fixture = FIXTURES["bedroom_small_scandinavian"]
    result_a = optimize_layout(fixture.room, SAMPLE_SPECS, seed=1, iterations=300)
    result_b = optimize_layout(fixture.room, SAMPLE_SPECS, seed=2, iterations=300)

    positions_a = [(round(i.x_cm, 1), round(i.y_cm, 1)) for i in result_a.placed_items]
    positions_b = [(round(i.x_cm, 1), round(i.y_cm, 1)) for i in result_b.placed_items]
    assert positions_a != positions_b  # not a hard guarantee in principle, but true for these seeds/iterations


def test_optimizer_improves_or_matches_a_deliberately_bad_initial_heuristic():
    """The optimiser's best score must be at least as good as a naive
    'stack everything in one corner' placement — otherwise annealing is not
    doing any useful work at all."""
    fixture = FIXTURES["office_contemporary_empty"]
    result = optimize_layout(fixture.room, SAMPLE_SPECS, iterations=800)

    naive_items = []
    x_cursor = 0.0
    for spec in SAMPLE_SPECS:
        w, d = spec.width_cm, spec.depth_cm
        naive_items.append(FurnitureItem(label=spec.label, width_cm=w, depth_cm=d, height_cm=spec.height_cm,
                                          category=spec.category, x_cm=w / 2 + x_cursor, y_cm=d / 2))
        x_cursor += w
    from ai.layout_optimization.scoring import compute_layout_score

    naive_score = compute_layout_score(fixture.room, naive_items)
    assert result.score.total_score >= naive_score.total_score


def test_layout_infeasible_when_item_cannot_physically_fit():
    tiny_room = RoomModel(
        room_type="other", width_cm=50, length_cm=50,
        openings=[Opening(kind="door", wall="south", position_cm=5, width_cm=20)],
    )
    huge_spec = [PlacementSpec(label="Huge Wardrobe", width_cm=300, depth_cm=300, height_cm=200)]
    with pytest.raises(LayoutInfeasibleError):
        optimize_layout(tiny_room, huge_spec, iterations=50)


def test_empty_specs_returns_only_existing_furniture_layout():
    fixture = FIXTURES["bedroom_small_scandinavian"]
    result = optimize_layout(fixture.room, [], iterations=10)
    assert result.placed_items == []
    assert all(result.constraints_satisfied.values())


def test_rotation_is_always_one_of_the_four_valid_angles():
    fixture = FIXTURES["living_room_modern_cluttered"]
    result = optimize_layout(fixture.room, SAMPLE_SPECS, iterations=500)
    for item in result.placed_items:
        assert item.rotation_deg in (0, 90, 180, 270)
