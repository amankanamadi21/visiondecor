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
FONT_SIZE_CM = 14  # sized in room-coordinate units so it scales with the viewBox


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

    # Openings (door/window) drawn as a thick colored segment on the boundary
    for opening in room.openings:
        x0, y0, x1, y1 = _opening_segment(room, opening)
        color = DOOR_COLOR if opening.kind == "door" else WINDOW_COLOR
        parts.append(
            f'<line x1="{ox + x0:.1f}" y1="{oy + y0:.1f}" x2="{ox + x1:.1f}" y2="{oy + y1:.1f}" '
            f'stroke="{color}" stroke-width="8" stroke-linecap="round"/>'
        )

    # Furniture — sorted so existing pieces draw first, then new ones on top
    for item in sorted(placed_items, key=lambda i: i.is_existing, reverse=True):
        w, d = _item_footprint(item)
        x0, y0 = item.x_cm - w / 2, item.y_cm - d / 2
        fill, stroke = (EXISTING_FILL, EXISTING_STROKE) if item.is_existing else (NEW_FILL, NEW_STROKE)
        parts.append(
            f'<rect x="{ox + x0:.1f}" y="{oy + y0:.1f}" width="{w:.1f}" height="{d:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2" rx="4"/>'
        )
        label = _escape(item.label)
        parts.append(
            f'<text x="{ox + item.x_cm:.1f}" y="{oy + item.y_cm:.1f}" text-anchor="middle" '
            f'dominant-baseline="middle" font-size="{FONT_SIZE_CM}" fill="{TEXT_COLOR}">{label}</text>'
        )

    # Legend
    legend_y = oy + room.length_cm + margin * 0.5
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
