"""
Coarse occupancy grid + BFS reachability (decision D020/D021 support).

A single grid computation over the room's floor serves three purposes at
once: (1) the hard "every piece of furniture must be reachable from the
door" constraint, (2) the soft `accessibility` term (how easily, not just
whether), and (3) the soft `movement_flow` term (what fraction of the free
floor is actually connected to the door, capturing fragmentation from a
poor layout). This is a deliberately simple, explainable approach — a full
navmesh/continuous path-planner is not warranted at this problem scale
(one room, 5-15 objects).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from ai.room_analysis.room_model import FurnitureItem, RoomModel

RESOLUTION_CM = 10.0


@dataclass
class GridResult:
    resolution_cm: float
    cols: int
    rows: int
    occupied: set[tuple[int, int]]
    reachable: set[tuple[int, int]]  # cells reachable from the door via free cells

    @property
    def total_cells(self) -> int:
        return self.cols * self.rows

    @property
    def free_cells(self) -> set[tuple[int, int]]:
        all_cells = {(x, y) for x in range(self.cols) for y in range(self.rows)}
        return all_cells - self.occupied


def _rect_to_cells(x0: float, y0: float, x1: float, y1: float, resolution_cm: float) -> list[tuple[int, int]]:
    gx0, gy0 = int(x0 // resolution_cm), int(y0 // resolution_cm)
    gx1, gy1 = int(math.ceil(x1 / resolution_cm)), int(math.ceil(y1 / resolution_cm))
    return [(x, y) for x in range(gx0, gx1) for y in range(gy0, gy1)]


def _point_to_cell(x: float, y: float, resolution_cm: float) -> tuple[int, int]:
    return int(x // resolution_cm), int(y // resolution_cm)


def build_grid(room: RoomModel, movable_items: list[FurnitureItem], resolution_cm: float = RESOLUTION_CM) -> GridResult:
    cols = max(1, math.ceil(room.width_cm / resolution_cm))
    rows = max(1, math.ceil(room.length_cm / resolution_cm))

    occupied: set[tuple[int, int]] = set()
    for item in [*room.existing_furniture, *movable_items]:
        x0, y0, x1, y1 = item.bounds
        for cell in _rect_to_cells(max(x0, 0), max(y0, 0), min(x1, room.width_cm), min(y1, room.length_cm), resolution_cm):
            gx, gy = cell
            if 0 <= gx < cols and 0 <= gy < rows:
                occupied.add(cell)

    door_x, door_y = room.door_center_cm()
    door_cell = _point_to_cell(
        min(max(door_x, 0), room.width_cm - 1e-6),
        min(max(door_y, 0), room.length_cm - 1e-6),
        resolution_cm,
    )

    reachable: set[tuple[int, int]] = set()
    if door_cell not in occupied:
        queue = deque([door_cell])
        reachable.add(door_cell)
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in occupied and (nx, ny) not in reachable:
                    reachable.add((nx, ny))
                    queue.append((nx, ny))

    return GridResult(resolution_cm=resolution_cm, cols=cols, rows=rows, occupied=occupied, reachable=reachable)


def item_border_cells(item: FurnitureItem, grid: GridResult, room: RoomModel) -> list[tuple[int, int]]:
    """Cells immediately surrounding (not inside) an item's footprint —
    used to test whether the item can actually be walked up to."""
    x0, y0, x1, y1 = item.bounds
    margin = grid.resolution_cm
    footprint_cells = set(
        _rect_to_cells(max(x0, 0), max(y0, 0), min(x1, room.width_cm), min(y1, room.length_cm), grid.resolution_cm)
    )
    border_cells = set(
        _rect_to_cells(
            max(x0 - margin, 0), max(y0 - margin, 0),
            min(x1 + margin, room.width_cm), min(y1 + margin, room.length_cm),
            grid.resolution_cm,
        )
    )
    border_cells -= footprint_cells
    return [c for c in border_cells if 0 <= c[0] < grid.cols and 0 <= c[1] < grid.rows]


def item_is_reachable(item: FurnitureItem, grid: GridResult, room: RoomModel) -> bool:
    return any(cell in grid.reachable for cell in item_border_cells(item, grid, room))


def bfs_distance_to_reachable(item: FurnitureItem, grid: GridResult, room: RoomModel) -> int | None:
    """Grid-step distance from the door to the nearest reachable border cell
    of `item`; None if unreachable (should already be excluded by the hard
    constraint before this is ever called for scoring)."""
    border = set(item_border_cells(item, grid, room)) & grid.reachable
    if not border:
        return None

    # BFS distances were not retained by build_grid (only the reachable set
    # was) — recompute distances here, bounded to the reachable set, which is
    # small (grid is coarse: a 500cm room is only 50x50 cells at 10cm res).
    door_x, door_y = room.door_center_cm()
    door_cell = _point_to_cell(min(max(door_x, 0), room.width_cm - 1e-6), min(max(door_y, 0), room.length_cm - 1e-6), grid.resolution_cm)
    if door_cell not in grid.reachable:
        return None

    distances = {door_cell: 0}
    queue = deque([door_cell])
    while queue:
        cx, cy = queue.popleft()
        if (cx, cy) in border:
            return distances[(cx, cy)]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (cx + dx, cy + dy)
            if neighbor in grid.reachable and neighbor not in distances:
                distances[neighbor] = distances[(cx, cy)] + 1
                queue.append(neighbor)
    return None
