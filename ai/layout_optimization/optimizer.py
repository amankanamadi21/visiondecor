"""
Simulated Annealing layout optimiser (decision D020).

Fixed random seed by default — same room + same items + same seed always
produces the same layout, matching the report's own "fixed random seed"
reproducibility principle (applied here to the optimiser instead of a
train/test split, since nothing in this pipeline is trained).

Any move a candidate state would require — including the very first,
random initial placement — is checked against every hard constraint in
constraints.py before it is ever scored. A hard-constraint violation is
never merely penalized; the move is rejected outright, regardless of the
current temperature (see PLAN.md D020).
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

from ai.layout_optimization.constraints import (
    all_items_reachable,
    check_all_hard_constraints,
    door_swing_clear,
    no_overlap,
    window_not_blocked,
    within_bounds,
)
from ai.layout_optimization.scoring import LayoutScoreResult, compute_layout_score
from ai.room_analysis.room_model import VALID_ROTATIONS, FurnitureItem, RoomModel

DEFAULT_SEED = 42
DEFAULT_ITERATIONS = 1500
INITIAL_TEMPERATURE = 1.0
COOLING_RATE = 0.995
MAX_INITIAL_PLACEMENT_ATTEMPTS_PER_ITEM = 300
MAX_INITIAL_PLACEMENT_RESTARTS = 50


class LayoutInfeasibleError(Exception):
    """Raised when no starting arrangement satisfying every hard constraint
    could be found — this is the real, honest "layout impossible" failure
    mode named in brief PART 15, not something to paper over with a
    best-effort overlapping layout."""


@dataclass
class PlacementSpec:
    label: str
    width_cm: float
    depth_cm: float
    height_cm: float
    category: str | None = None
    catalog_item_id: int | None = None


@dataclass
class OptimizationResult:
    placed_items: list[FurnitureItem]
    score: LayoutScoreResult
    constraints_satisfied: dict[str, bool]
    iterations_run: int
    seed: int
    algorithm: str = "simulated_annealing"


def candidate_is_feasible(room: RoomModel, item: FurnitureItem, other_placed: list[FurnitureItem]) -> bool:
    all_items = [*room.existing_furniture, *other_placed, item]
    if not no_overlap(all_items):
        return False
    if not within_bounds(item, room):
        return False
    if not door_swing_clear(item, room):
        return False
    if not window_not_blocked(item, room):
        return False
    return True


def _try_random_initial_placement(room: RoomModel, specs: list[PlacementSpec], rng: random.Random) -> list[FurnitureItem] | None:
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
                return None  # item cannot physically fit in this room at all, in any position
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


def _find_initial_placement(room: RoomModel, specs: list[PlacementSpec], rng: random.Random) -> list[FurnitureItem]:
    for _ in range(MAX_INITIAL_PLACEMENT_RESTARTS):
        result = _try_random_initial_placement(room, specs, rng)
        if result is not None:
            return result
    raise LayoutInfeasibleError(
        f"Could not find any arrangement of {len(specs)} item(s) satisfying every hard constraint "
        f"(no overlap, in bounds, door clear, window not blocked, all items reachable) in a "
        f"{room.width_cm:.0f}x{room.length_cm:.0f}cm {room.room_type}. The room may be too small or "
        f"too cluttered with existing furniture for the requested items."
    )


def _propose_move(item: FurnitureItem, room: RoomModel, temperature: float, rng: random.Random) -> FurnitureItem:
    candidate = copy.deepcopy(item)
    if rng.random() < 0.15:
        candidate.rotation_deg = rng.choice(VALID_ROTATIONS)
    # Move size shrinks as temperature cools — coarse exploration early,
    # fine-tuning late. Bounded so it always stays a meaningful fraction of
    # the room even at low temperature (avoids the search stalling).
    jitter_cm = max(15.0, temperature * max(room.width_cm, room.length_cm) * 0.5)
    candidate.x_cm += rng.uniform(-jitter_cm, jitter_cm)
    candidate.y_cm += rng.uniform(-jitter_cm, jitter_cm)
    w, d = candidate.footprint_wh
    candidate.x_cm = min(max(candidate.x_cm, w / 2), room.width_cm - w / 2)
    candidate.y_cm = min(max(candidate.y_cm, d / 2), room.length_cm - d / 2)
    return candidate


def optimize_layout(
    room: RoomModel,
    specs: list[PlacementSpec],
    *,
    seed: int = DEFAULT_SEED,
    iterations: int = DEFAULT_ITERATIONS,
) -> OptimizationResult:
    rng = random.Random(seed)

    state = _find_initial_placement(room, specs, rng)
    current_score = compute_layout_score(room, state)
    best_state = copy.deepcopy(state)
    best_score = current_score

    temperature = INITIAL_TEMPERATURE
    for i in range(iterations):
        if not state:
            break  # nothing to optimise (room needed zero new items)
        idx = rng.randrange(len(state))
        others = state[:idx] + state[idx + 1 :]
        candidate_item = _propose_move(state[idx], room, temperature, rng)

        if candidate_is_feasible(room, candidate_item, others) and all_items_reachable(room, others + [candidate_item]):
            candidate_state = others + [candidate_item]
            candidate_score = compute_layout_score(room, candidate_state)
            delta = candidate_score.total_score - current_score.total_score
            if delta >= 0 or rng.random() < math.exp(delta / max(temperature, 1e-9)):
                state = candidate_state
                current_score = candidate_score
                if current_score.total_score > best_score.total_score:
                    best_state = copy.deepcopy(state)
                    best_score = current_score

        temperature *= COOLING_RATE

    constraints_satisfied = check_all_hard_constraints(room, best_state)
    return OptimizationResult(
        placed_items=best_state,
        score=best_score,
        constraints_satisfied=constraints_satisfied,
        iterations_run=iterations,
        seed=seed,
    )
