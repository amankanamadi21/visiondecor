"""
Soft layout objective (decisions D020/D021).

LayoutScore = w1·SpaceUtilization + w2·Accessibility + w3·MovementFlow
            + w4·VisualBalance + w5·Functionality

computed ONLY over candidates that already satisfy every hard constraint in
constraints.py — see PLAN.md D020 for why overlap etc. are not soft terms
here. Weights are the "Balanced" profile approved in D021.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ai.layout_optimization.grid import bfs_distance_to_reachable, build_grid
from ai.room_analysis.room_model import FurnitureItem, RoomModel

# D021 — Balanced profile, locked.
WEIGHTS = {
    "space_utilization": 0.25,
    "accessibility": 0.25,
    "movement_flow": 0.20,
    "visual_balance": 0.15,
    "functionality": 0.15,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

IDEAL_SPACE_UTILIZATION_RATIO = 0.35  # "not empty, not cluttered" — an implementation parameter, not a D021 weight

# (category_a, category_b, max_distance_cm, description) — functionality
# adjacency rules. An implementation detail of the `functionality` term,
# not part of the D021-approved weight vector itself.
FUNCTIONALITY_RULES = [
    ("table", "sofa", 120.0, "coffee table near sofa"),
    ("lighting", "sofa", 150.0, "lighting near seating"),
    ("lighting", "bed", 150.0, "lighting near bed"),
    ("cabinet", "bed", 100.0, "nightstand-like storage near bed"),
    ("chair", "table", 80.0, "chair near table/desk"),
]
FUNCTIONALITY_NEUTRAL_SCORE = 0.6  # used when no rule's categories are even present


@dataclass
class LayoutScoreResult:
    total_score: float
    breakdown: dict[str, float]


def _distance(a: FurnitureItem, b: FurnitureItem) -> float:
    return math.hypot(a.x_cm - b.x_cm, a.y_cm - b.y_cm)


def _space_utilization(room: RoomModel, all_items: list[FurnitureItem]) -> float:
    used_ratio = sum(item.area_cm2 for item in all_items) / room.area_cm2
    deviation = abs(used_ratio - IDEAL_SPACE_UTILIZATION_RATIO) / IDEAL_SPACE_UTILIZATION_RATIO
    return max(0.0, 1.0 - deviation)


def _accessibility_and_flow(room: RoomModel, movable_items: list[FurnitureItem]) -> tuple[float, float]:
    grid = build_grid(room, movable_items)
    all_items = [*room.existing_furniture, *movable_items]

    max_distance = grid.cols + grid.rows  # loose upper bound on a reachable BFS path length
    distances = []
    for item in all_items:
        d = bfs_distance_to_reachable(item, grid, room)
        if d is not None:
            distances.append(d)
    if distances:
        accessibility = sum(max(0.0, 1.0 - d / max_distance) for d in distances) / len(distances)
    else:
        accessibility = 0.0

    free_cells = grid.free_cells
    movement_flow = (len(grid.reachable) / len(free_cells)) if free_cells else 0.0

    return accessibility, movement_flow


def _visual_balance(room: RoomModel, all_items: list[FurnitureItem]) -> float:
    if not all_items:
        return 1.0
    total_area = sum(item.area_cm2 for item in all_items)
    if total_area == 0:
        return 1.0
    centroid_x = sum(item.x_cm * item.area_cm2 for item in all_items) / total_area
    centroid_y = sum(item.y_cm * item.area_cm2 for item in all_items) / total_area
    room_center_x, room_center_y = room.width_cm / 2, room.length_cm / 2
    offset = math.hypot(centroid_x - room_center_x, centroid_y - room_center_y)
    max_offset = math.hypot(room.width_cm / 2, room.length_cm / 2)
    return max(0.0, 1.0 - offset / max_offset) if max_offset > 0 else 1.0


def _functionality(all_items: list[FurnitureItem]) -> float:
    by_category: dict[str, list[FurnitureItem]] = {}
    for item in all_items:
        if item.category:
            by_category.setdefault(item.category, []).append(item)

    applicable, satisfied = 0, 0
    for cat_a, cat_b, max_dist, _desc in FUNCTIONALITY_RULES:
        items_a, items_b = by_category.get(cat_a), by_category.get(cat_b)
        if not items_a or not items_b:
            continue
        applicable += 1
        if any(_distance(a, b) <= max_dist for a in items_a for b in items_b):
            satisfied += 1

    if applicable == 0:
        return FUNCTIONALITY_NEUTRAL_SCORE
    return satisfied / applicable


def compute_layout_score(room: RoomModel, movable_items: list[FurnitureItem]) -> LayoutScoreResult:
    all_items = [*room.existing_furniture, *movable_items]

    space_utilization = _space_utilization(room, all_items)
    accessibility, movement_flow = _accessibility_and_flow(room, movable_items)
    visual_balance = _visual_balance(room, all_items)
    functionality = _functionality(all_items)

    breakdown = {
        "space_utilization": round(space_utilization, 4),
        "accessibility": round(accessibility, 4),
        "movement_flow": round(movement_flow, 4),
        "visual_balance": round(visual_balance, 4),
        "functionality": round(functionality, 4),
    }
    total_score = sum(WEIGHTS[k] * v for k, v in breakdown.items())
    return LayoutScoreResult(total_score=round(total_score, 4), breakdown=breakdown)
