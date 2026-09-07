"""
Baseline layout algorithms (decision D025) — for comparison against the
Simulated Annealing optimiser only. These are NOT part of the shipped
product; they exist to give the layout evaluation study something honest
to compare against, using the exact same hard-constraint checks as the
real optimiser (ai.layout_optimization.constraints) so the comparison is
apples-to-apples, not a strawman.
"""
from __future__ import annotations

import random

from ai.layout_optimization.constraints import all_items_reachable, check_all_hard_constraints
from ai.layout_optimization.optimizer import MAX_INITIAL_PLACEMENT_ATTEMPTS_PER_ITEM, PlacementSpec, candidate_is_feasible
from ai.layout_optimization.scoring import compute_layout_score
from ai.room_analysis.room_model import VALID_ROTATIONS, FurnitureItem, RoomModel


def random_baseline(room: RoomModel, specs: list[PlacementSpec], seed: int) -> list[FurnitureItem] | None:
    """One random-but-feasible placement, with NO subsequent optimisation —
    this is the SA optimiser's own initial-placement step, in isolation,
    which makes it a fair 'search vs. no search' baseline."""
    rng = random.Random(seed)
    placed: list[FurnitureItem] = []
    for spec in specs:
        found = False
        for _ in range(MAX_INITIAL_PLACEMENT_ATTEMPTS_PER_ITEM):
            rotation = rng.choice(VALID_ROTATIONS)
            item = FurnitureItem(
                label=spec.label, width_cm=spec.width_cm, depth_cm=spec.depth_cm, height_cm=spec.height_cm,
                category=spec.category, catalog_item_id=spec.catalog_item_id, rotation_deg=rotation,
            )
            w, d = item.footprint_wh
            if w > room.width_cm or d > room.length_cm:
                return None
            item.x_cm = rng.uniform(w / 2, room.width_cm - w / 2)
            item.y_cm = rng.uniform(d / 2, room.length_cm - d / 2)
            if candidate_is_feasible(room, item, placed):
                placed.append(item)
                found = True
                break
        if not found:
            return None
    if not all_items_reachable(room, placed):
        return None
    return placed


def greedy_first_fit_baseline(
    room: RoomModel, specs: list[PlacementSpec], grid_resolution_cm: float = 20.0
) -> list[FurnitureItem] | None:
    """Deterministic: scans a coarse grid in raster order and places each
    item (in the given order) at the first feasible position/rotation
    found — no backtracking, no search, no randomness. A classic greedy
    heuristic, and a meaningfully different failure mode than random search
    (it can paint itself into a corner early and fail on a later item)."""
    placed: list[FurnitureItem] = []
    for spec in specs:
        found = False
        y = 0.0
        while y <= room.length_cm and not found:
            x = 0.0
            while x <= room.width_cm and not found:
                for rotation in VALID_ROTATIONS:
                    item = FurnitureItem(
                        label=spec.label, width_cm=spec.width_cm, depth_cm=spec.depth_cm,
                        height_cm=spec.height_cm, category=spec.category,
                        catalog_item_id=spec.catalog_item_id, rotation_deg=rotation,
                    )
                    w, d = item.footprint_wh
                    item.x_cm, item.y_cm = x + w / 2, y + d / 2
                    if item.x_cm + w / 2 > room.width_cm or item.y_cm + d / 2 > room.length_cm:
                        continue
                    if candidate_is_feasible(room, item, placed):
                        placed.append(item)
                        found = True
                        break
                x += grid_resolution_cm
            y += grid_resolution_cm
        if not found:
            return None
    if not all_items_reachable(room, placed):
        return None
    return placed
