"""
Floor-plan SVG renderer tests (ai/visualization/floorplan.py). Structural
checks only — this asserts the SVG contains the elements it's supposed to,
not exact pixel positions, since the rendering is meant to be a readable
diagram, not a pixel-perfect spec.
"""
from __future__ import annotations

from ai.room_analysis.room_model import FurnitureItem, Opening, RoomModel
from ai.visualization.floorplan import render_floorplan_svg


def _room(**overrides) -> RoomModel:
    defaults = dict(room_type="bedroom", width_cm=400, length_cm=300)
    defaults.update(overrides)
    return RoomModel(**defaults)


def test_dimension_labels_show_real_room_size():
    room = _room(width_cm=420, length_cm=310)
    svg = render_floorplan_svg(room, [])
    assert "420 cm" in svg
    assert "310 cm" in svg


def test_grid_lines_present_for_a_room_bigger_than_one_grid_step():
    room = _room(width_cm=400, length_cm=300)  # > GRID_STEP_CM (50)
    svg = render_floorplan_svg(room, [])
    # At least one vertical and one horizontal grid line should be drawn.
    assert svg.count("<line") >= 2


def test_category_color_applied_to_a_new_item_with_a_known_category():
    room = _room()
    sofa = FurnitureItem(
        label="Test Sofa", width_cm=200, depth_cm=90, height_cm=80,
        x_cm=200, y_cm=150, is_existing=False, category="sofa",
    )
    svg = render_floorplan_svg(room, [sofa])
    from ai.visualization.floorplan import CATEGORY_COLORS

    fill, stroke = CATEGORY_COLORS["sofa"]
    assert fill in svg and stroke in svg


def test_unknown_category_falls_back_to_plain_new_color():
    room = _room()
    item = FurnitureItem(
        label="Mystery Item", width_cm=100, depth_cm=50, height_cm=50,
        x_cm=200, y_cm=150, is_existing=False, category=None,
    )
    from ai.visualization.floorplan import NEW_FILL, NEW_STROKE

    svg = render_floorplan_svg(room, [item])
    assert NEW_FILL in svg and NEW_STROKE in svg


def test_large_item_shows_a_size_label_small_item_does_not():
    room = _room()
    big = FurnitureItem(label="Big Bed", width_cm=180, depth_cm=200, height_cm=50, x_cm=200, y_cm=150, is_existing=False)
    small = FurnitureItem(label="Tiny Lamp", width_cm=20, depth_cm=20, height_cm=150, x_cm=350, y_cm=250, is_existing=False)
    svg = render_floorplan_svg(room, [big, small])
    assert "180×200 cm" in svg
    assert "20×20 cm" not in svg


def test_door_gets_a_swing_arc_window_does_not():
    room = _room(
        openings=[
            Opening(kind="door", wall="south", position_cm=50, width_cm=80),
            Opening(kind="window", wall="north", position_cm=50, width_cm=100),
        ]
    )
    svg = render_floorplan_svg(room, [])
    assert svg.count("<path") == 1  # exactly the door's swing arc, none for the window


def test_existing_item_keeps_existing_color_regardless_of_category():
    room = _room()
    item = FurnitureItem(
        label="Old Sofa", width_cm=200, depth_cm=90, height_cm=80,
        x_cm=200, y_cm=150, is_existing=True, category="sofa",
    )
    from ai.visualization.floorplan import EXISTING_FILL, CATEGORY_COLORS

    svg = render_floorplan_svg(room, [item])
    assert EXISTING_FILL in svg
    sofa_fill, _ = CATEGORY_COLORS["sofa"]
    assert sofa_fill not in svg  # category color must not leak onto existing items


def test_no_crash_with_empty_room_and_no_items():
    room = _room()
    svg = render_floorplan_svg(room, [])
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
