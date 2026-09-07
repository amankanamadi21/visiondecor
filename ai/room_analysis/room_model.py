"""
Shared 2D room representation (cm units, room-local coordinates) used by the
recommendation engine, the layout optimiser, and (for now) the fixture
generator (decision D018). This is the "spatial model" the report's PART 8
asks for — a room is width_cm × length_cm; each furniture item has a
position, footprint, and rotation restricted to {0, 90, 180, 270} (D020).

Coordinate system: origin (0,0) at the room's bottom-left corner as viewed
in plan; x runs along `width_cm` (0..width_cm), y runs along `length_cm`
(0..length_cm). Item (x_cm, y_cm) is the footprint's CENTER, not its corner.

Provenance note (D018 guardrail): nothing in this module cares whether a
RoomModel came from a real detected room or a labeled fixture — that
distinction is tracked upstream (RoomAnalysis.model_versions /
DetectedObject.source in the DB), never inside the geometry itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VALID_ROTATIONS = (0, 90, 180, 270)
WALLS = ("north", "south", "east", "west")  # north/south run along x; east/west along y


@dataclass
class Opening:
    """A door or window on one of the room's four boundary walls."""

    kind: str  # "door" | "window"
    wall: str  # one of WALLS
    position_cm: float  # distance along the wall from its start corner
    width_cm: float

    def __post_init__(self):
        if self.kind not in ("door", "window"):
            raise ValueError(f"Opening.kind must be 'door' or 'window', got {self.kind!r}")
        if self.wall not in WALLS:
            raise ValueError(f"Opening.wall must be one of {WALLS}, got {self.wall!r}")


@dataclass
class FurnitureItem:
    label: str
    width_cm: float
    depth_cm: float
    height_cm: float
    x_cm: float = 0.0
    y_cm: float = 0.0
    rotation_deg: int = 0
    is_existing: bool = False
    catalog_item_id: int | None = None
    # Catalog category (e.g. "sofa", "table") — used by the layout scorer's
    # functionality-adjacency rules (ai/layout_optimization/scoring.py).
    # None for existing/fixture furniture whose category wasn't classified.
    category: str | None = None

    def __post_init__(self):
        if self.rotation_deg not in VALID_ROTATIONS:
            raise ValueError(f"rotation_deg must be one of {VALID_ROTATIONS}, got {self.rotation_deg}")

    @property
    def footprint_wh(self) -> tuple[float, float]:
        """(width, depth) as actually oriented in the room — swapped at 90/270°."""
        if self.rotation_deg in (90, 270):
            return self.depth_cm, self.width_cm
        return self.width_cm, self.depth_cm

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Axis-aligned (x0, y0, x1, y1) footprint in room coordinates."""
        w, d = self.footprint_wh
        return (self.x_cm - w / 2, self.y_cm - d / 2, self.x_cm + w / 2, self.y_cm + d / 2)

    @property
    def area_cm2(self) -> float:
        w, d = self.footprint_wh
        return w * d


@dataclass
class RoomModel:
    room_type: str
    width_cm: float
    length_cm: float
    openings: list[Opening] = field(default_factory=list)
    existing_furniture: list[FurnitureItem] = field(default_factory=list)
    # Only meaningful when it comes from a real analysis (segmentation-derived
    # floor mask); fixtures may leave this None rather than fabricate a value.
    free_space_ratio: float | None = None

    @property
    def area_cm2(self) -> float:
        return self.width_cm * self.length_cm

    @property
    def door(self) -> Opening | None:
        return next((o for o in self.openings if o.kind == "door"), None)

    def door_center_cm(self) -> tuple[float, float]:
        """Room-coordinate (x, y) of the door's midpoint, used as the
        reference point for accessibility/movement-flow scoring. Falls back
        to the room's geometric center if no door is defined (should not
        happen for a real or fixture room, but must not crash if it does)."""
        d = self.door
        if d is None:
            return self.width_cm / 2, self.length_cm / 2
        if d.wall == "south":
            return d.position_cm + d.width_cm / 2, 0.0
        if d.wall == "north":
            return d.position_cm + d.width_cm / 2, self.length_cm
        if d.wall == "west":
            return 0.0, d.position_cm + d.width_cm / 2
        return self.width_cm, d.position_cm + d.width_cm / 2  # "east"

    def opening_bounds(self, opening: Opening, into_room_cm: float) -> tuple[float, float, float, float]:
        """Axis-aligned bounds of the clearance zone an opening projects
        `into_room_cm` into the room — used for door-swing / window-blocking
        hard constraints (CL-07 / CL-08)."""
        if opening.wall in ("south", "north"):
            x0, x1 = opening.position_cm, opening.position_cm + opening.width_cm
            if opening.wall == "south":
                return x0, 0.0, x1, into_room_cm
            return x0, self.length_cm - into_room_cm, x1, self.length_cm
        y0, y1 = opening.position_cm, opening.position_cm + opening.width_cm
        if opening.wall == "west":
            return 0.0, y0, into_room_cm, y1
        return self.width_cm - into_room_cm, y0, self.width_cm, y1
