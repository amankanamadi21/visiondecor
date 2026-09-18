"""
Deterministic, always-available floor-plan renderer (decisions D001/D003).

This is not a fallback bolted on for when the generative image API is
unavailable — it is the one visualization the report requires that is
guaranteed instant, free, and fully reproducible from the optimiser's own
output. Per brief PART 9, the layout is the source of truth; this renders
that source of truth directly, with nothing left to a generative model's
interpretation.

Produces plain SVG text (no new dependency — Pillow is already required
elsewhere, but SVG text generation needs no image library at all, and SVG
scales cleanly in a browser at any size).

Accepts anything duck-typing the needed attributes (x_cm, y_cm, width_cm,
depth_cm, rotation_deg, label, is_existing) — this is true of both
ai.room_analysis.room_model.FurnitureItem (in-memory optimiser output) and
backend.models.layout.LayoutObject (a loaded DB row), so the exact same
renderer serves both a fresh optimisation result and a previously-saved one.
"""
from __future__ import annotations

from ai.room_analysis.room_model import RoomModel

EXISTING_FILL = "#d8cfc0"
EXISTING_STROKE = "#8a7d64"
NEW_FILL = "#cfe3d8"
NEW_STROKE = "#4c8067"
DOOR_COLOR = "#b5794a"
WINDOW_COLOR = "#5b8fb0"
ROOM_STROKE = "#2a2622"
TEXT_COLOR = "#2a2622"
GRID_COLOR = "#eee6d8"
DIMENSION_COLOR = "#746c63"
FONT_SIZE_CM = 14  # sized in room-coordinate units so it scales with the viewBox
GRID_STEP_CM = 50  # a real-world scale reference, not decorative

# Per-category fill/stroke for NEW (recommended) items — falls back to
# NEW_FILL/NEW_STROKE when an item's category is unknown (a LayoutObject
# loaded from the DB has no category column; see _render_floorplan_for_session,
# which resolves it via one catalog join before calling this renderer).
CATEGORY_COLORS: dict[str, tuple[str, str]] = {
    "sofa": ("#d9c2a8", "#8a6a45"),
    "bed": ("#e0b8b0", "#a06a5c"),
    "chair": ("#c9d9c2", "#5f7a52"),
    "table": ("#c2d6e0", "#4d7189"),
    "cabinet": ("#d3c7e0", "#6f5490"),
    "shelf": ("#e0d6b8", "#8a7434"),
    "lighting": ("#f0e2a8", "#a68f2e"),
    "rug": ("#cfe3d8", "#4c8067"),
    "curtain": ("#e0c2d6", "#8a4d70"),
    "decor": ("#c2e0d9", "#4d8a74"),
}


def _item_footprint(item) -> tuple[float, float]:
    if item.rotation_deg in (90, 270):
        return item.depth_cm, item.width_cm
    return item.width_cm, item.depth_cm


def _opening_segment(room: RoomModel, opening) -> tuple[float, float, float, float]:
    if opening.wall == "south":
        return opening.position_cm, 0.0, opening.position_cm + opening.width_cm, 0.0
    if opening.wall == "north":
        return opening.position_cm, room.length_cm, opening.position_cm + opening.width_cm, room.length_cm
    if opening.wall == "west":
        return 0.0, opening.position_cm, 0.0, opening.position_cm + opening.width_cm
    return room.width_cm, opening.position_cm, room.width_cm, opening.position_cm + opening.width_cm  # "east"


def _door_swing_arc(room: RoomModel, opening, ox: float, oy: float) -> str | None:
    """A quarter-circle arc showing the door's swing area — the same
    DOOR_SWING_CLEARANCE_CM geometry the layout optimiser's hard constraint
    already reasons about (ai/layout_optimization/constraints.py), drawn so
    a person can actually see why furniture keeps clear of that corner,
    not just a flat line implying the door doesn't open into the room.
    Illustrative, not exact — which side the door is hinged on isn't part
    of the data model, so this always draws the swing curving in from the
    segment's start corner, an approximation, not a measured fact."""
    if opening.kind != "door":
        return None
    x0, y0, _x1, _y1 = _opening_segment(room, opening)
    radius = opening.width_cm
    inward = {"south": (0, 1), "north": (0, -1), "west": (1, 0), "east": (-1, 0)}[opening.wall]
    hinge_x, hinge_y = ox + x0, oy + y0
    arc_end_x = hinge_x + inward[0] * radius
    arc_end_y = hinge_y + inward[1] * radius
    sweep = 1 if opening.wall in ("south", "west") else 0
    return (
        f'<path d="M {hinge_x:.1f} {hinge_y:.1f} A {radius:.1f} {radius:.1f} 0 0 {sweep} '
        f'{arc_end_x:.1f} {arc_end_y:.1f}" fill="none" stroke="{DOOR_COLOR}" '
        f'stroke-width="1.5" stroke-dasharray="6,4" opacity="0.6"/>'
    )


def render_floorplan_svg(room: RoomModel, placed_items: list, *, title: str | None = None) -> str:
    margin = max(room.width_cm, room.length_cm) * 0.08
    view_w = room.width_cm + 2 * margin
    view_h = room.length_cm + 2 * margin + (40 if title else 0)
    title_offset = 40 if title else 0

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w:.1f} {view_h:.1f}" '
        f'font-family="Helvetica, Arial, sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{view_w:.1f}" height="{view_h:.1f}" fill="#faf8f5"/>')

    if title:
        parts.append(
            f'<text x="{view_w / 2:.1f}" y="24" text-anchor="middle" font-size="20" '
            f'fill="{TEXT_COLOR}">{_escape(title)}</text>'
        )

    ox, oy = margin, margin + title_offset  # room-space (0,0) -> SVG space offset

    # Room boundary
    parts.append(
        f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{room.width_cm:.1f}" height="{room.length_cm:.1f}" '
        f'fill="#ffffff" stroke="{ROOM_STROKE}" stroke-width="4"/>'
    )

    # Scale grid, so the room reads as a real measured space, not a diagram
    # at an arbitrary size — every line is exactly GRID_STEP_CM apart.
    x = GRID_STEP_CM
    while x < room.width_cm:
        parts.append(
            f'<line x1="{ox + x:.1f}" y1="{oy:.1f}" x2="{ox + x:.1f}" y2="{oy + room.length_cm:.1f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        x += GRID_STEP_CM
    y = GRID_STEP_CM
    while y < room.length_cm:
        parts.append(
            f'<line x1="{ox:.1f}" y1="{oy + y:.1f}" x2="{ox + room.width_cm:.1f}" y2="{oy + y:.1f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        y += GRID_STEP_CM

    # Room dimensions — the actual measured/estimated size, not just a
    # decorative diagram (brief PART 16's "show real numbers" principle
    # applies here too, not only to the recommendation/layout scores).
    parts.append(
        f'<text x="{ox + room.width_cm / 2:.1f}" y="{oy + room.length_cm + margin * 0.28:.1f}" '
        f'text-anchor="middle" font-size="13" fill="{DIMENSION_COLOR}">{room.width_cm:.0f} cm</text>'
    )
    parts.append(
        f'<text x="{ox - margin * 0.28:.1f}" y="{oy + room.length_cm / 2:.1f}" text-anchor="middle" '
        f'font-size="13" fill="{DIMENSION_COLOR}" transform="rotate(-90 {ox - margin * 0.28:.1f} '
        f'{oy + room.length_cm / 2:.1f})">{room.length_cm:.0f} cm</text>'
    )

    # Openings (door/window) drawn as a thick colored segment on the boundary
    for opening in room.openings:
        x0, y0, x1, y1 = _opening_segment(room, opening)
        color = DOOR_COLOR if opening.kind == "door" else WINDOW_COLOR
        parts.append(
            f'<line x1="{ox + x0:.1f}" y1="{oy + y0:.1f}" x2="{ox + x1:.1f}" y2="{oy + y1:.1f}" '
            f'stroke="{color}" stroke-width="8" stroke-linecap="round"/>'
        )
        arc = _door_swing_arc(room, opening, ox, oy)
        if arc:
            parts.append(arc)

    # Furniture — sorted so existing pieces draw first, then new ones on top
    for item in sorted(placed_items, key=lambda i: i.is_existing, reverse=True):
        w, d = _item_footprint(item)
        x0, y0 = item.x_cm - w / 2, item.y_cm - d / 2
        if item.is_existing:
            fill, stroke = EXISTING_FILL, EXISTING_STROKE
        else:
            fill, stroke = CATEGORY_COLORS.get(getattr(item, "category", None) or "", (NEW_FILL, NEW_STROKE))
        parts.append(
            f'<rect x="{ox + x0:.1f}" y="{oy + y0:.1f}" width="{w:.1f}" height="{d:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2" rx="4"/>'
        )
        label = _escape(item.label)
        has_room_for_size = w >= 40 and d >= 25
        label_y = oy + item.y_cm - (5 if has_room_for_size else 0)
        parts.append(
            f'<text x="{ox + item.x_cm:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            f'dominant-baseline="middle" font-size="{FONT_SIZE_CM}" fill="{TEXT_COLOR}">{label}</text>'
        )
        if has_room_for_size:
            parts.append(
                f'<text x="{ox + item.x_cm:.1f}" y="{label_y + FONT_SIZE_CM * 0.85:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="{FONT_SIZE_CM * 0.7:.1f}" fill="{DIMENSION_COLOR}">'
                f"{w:.0f}×{d:.0f} cm</text>"
            )

    # Legend
    legend_y = oy + room.length_cm + margin * 0.7
    parts.append(_legend_swatch(ox, legend_y, EXISTING_FILL, EXISTING_STROKE, "Existing / kept"))
    parts.append(_legend_swatch(ox + room.width_cm * 0.35, legend_y, NEW_FILL, NEW_STROKE, "Recommended (new)"))

    parts.append("</svg>")
    return "".join(parts)


def _legend_swatch(x: float, y: float, fill: str, stroke: str, label: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="18" height="18" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{x + 24:.1f}" y="{y + 14:.1f}" font-size="14" fill="{TEXT_COLOR}">{_escape(label)}</text>'
    )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
