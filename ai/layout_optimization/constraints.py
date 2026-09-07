"""
Hard constraints for the layout optimiser (decision D020). A candidate
placement violating ANY of these is rejected outright by the optimiser —
never weighed against the soft objective, never "mostly satisfied". Overlap
in particular is never a matter of degree (see PLAN.md D020).
"""
from __future__ import annotations

from ai.layout_optimization.grid import build_grid, item_is_reachable
from ai.room_analysis.room_model import FurnitureItem, RoomModel

DOOR_SWING_CLEARANCE_CM = 90.0  # CL-07: keep the door's swing arc clear
WINDOW_CLEARANCE_HEIGHT_FRACTION = 0.5  # CL-08: don't block > half a window's height
TALL_ITEM_THRESHOLD_CM = 100.0  # CL-08 applies to furniture "over 1m" tall


def _rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def no_overlap(items: list[FurnitureItem]) -> bool:
    bounds = [item.bounds for item in items]
    for i in range(len(bounds)):
        for j in range(i + 1, len(bounds)):
            if _rects_overlap(bounds[i], bounds[j]):
                return False
    return True


def within_bounds(item: FurnitureItem, room: RoomModel) -> bool:
    x0, y0, x1, y1 = item.bounds
    return x0 >= -1e-6 and y0 >= -1e-6 and x1 <= room.width_cm + 1e-6 and y1 <= room.length_cm + 1e-6


def door_swing_clear(item: FurnitureItem, room: RoomModel) -> bool:
    door = room.door
    if door is None:
        return True
    clearance_bounds = room.opening_bounds(door, DOOR_SWING_CLEARANCE_CM)
    return not _rects_overlap(item.bounds, clearance_bounds)


def window_not_blocked(item: FurnitureItem, room: RoomModel) -> bool:
    if item.height_cm <= TALL_ITEM_THRESHOLD_CM:
        return True  # CL-08 only concerns tall furniture
    for opening in room.openings:
        if opening.kind != "window":
            continue
        blocking_depth = room.width_cm if opening.wall in ("north", "south") else room.length_cm
        clearance_bounds = room.opening_bounds(opening, blocking_depth * WINDOW_CLEARANCE_HEIGHT_FRACTION)
        if _rects_overlap(item.bounds, clearance_bounds):
            return False
    return True


def all_items_reachable(room: RoomModel, movable_items: list[FurnitureItem]) -> bool:
    grid = build_grid(room, movable_items)
    for item in [*room.existing_furniture, *movable_items]:
        if not item_is_reachable(item, grid, room):
            return False
    return True


def check_all_hard_constraints(room: RoomModel, movable_items: list[FurnitureItem]) -> dict[str, bool]:
    """Returns the full pass/fail map — this is exactly what gets stored in
    `layouts.constraints_satisfied` so the UI can show each constraint
    distinctly (brief PART 16), not collapse them into one boolean."""
    all_items = [*room.existing_furniture, *movable_items]

    overlap_ok = no_overlap(all_items)
    bounds_ok = all(within_bounds(item, room) for item in movable_items)
    door_ok = all(door_swing_clear(item, room) for item in movable_items)
    window_ok = all(window_not_blocked(item, room) for item in movable_items)
    reachable_ok = all_items_reachable(room, movable_items) if (overlap_ok and bounds_ok) else False

    return {
        "no_overlap": overlap_ok,
        "within_bounds": bounds_ok,
        "door_clear": door_ok,
        "window_not_blocked": window_ok,
        "all_items_reachable": reachable_ok,
    }


def is_feasible(room: RoomModel, movable_items: list[FurnitureItem]) -> bool:
    return all(check_all_hard_constraints(room, movable_items).values())
