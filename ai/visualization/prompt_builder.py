"""
Layout -> natural-language edit instruction translator (decision D023).

Turns the optimiser's actual computed positions into qualitative spatial
language an image-editing model can act on ("a coffee table in front of the
sofa", "a floor lamp in the back-right corner near the window"). This is
built entirely from real LayoutObject/FurnitureItem data — it never
describes a position the optimiser didn't actually choose.

Precision is deliberately qualitative, not numeric: an image model has no
use for "x=132.9cm, y=190.5cm", and per brief PART 9 the floor plan (not
this generated image) remains the authoritative, precise record of the
layout. This prompt only needs to point the model in the right direction.
"""
from __future__ import annotations

import math

from ai.room_analysis.room_model import RoomModel

NEARBY_THRESHOLD_CM = 150.0


def _distance(a, b) -> float:
    return math.hypot(a.x_cm - b.x_cm, a.y_cm - b.y_cm)


def _qualitative_position(item, room: RoomModel) -> str:
    x_ratio = item.x_cm / room.width_cm if room.width_cm else 0.5
    y_ratio = item.y_cm / room.length_cm if room.length_cm else 0.5

    horizontal = "left side" if x_ratio < 0.33 else "right side" if x_ratio > 0.66 else "center"
    vertical = "front" if y_ratio < 0.33 else "back" if y_ratio > 0.66 else "middle"

    if horizontal == "center" and vertical == "middle":
        return "in the center of the room"
    if horizontal == "center":
        return f"toward the {vertical} of the room"
    if vertical == "middle":
        return f"along the {horizontal}"
    return f"in the {vertical} {horizontal.replace(' side', '')} area"


def _nearest_existing_item(item, all_items) -> tuple[object, float] | None:
    """Anchors a new item's description to an EXISTING piece of furniture
    only, never to another newly-placed item — two new items placed near
    each other would otherwise describe each other circularly ('table near
    the rug' / 'rug near the table'), which is redundant and not obviously
    resolvable by an image model anyway."""
    candidates = [
        (other, _distance(item, other)) for other in all_items if other is not item and other.is_existing
    ]
    candidates = [c for c in candidates if c[1] <= NEARBY_THRESHOLD_CM]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[1])


_VOWEL_SOUNDS = ("a", "e", "i", "o", "u")


def _article_for(label: str) -> str:
    return "an" if label[:1].lower() in _VOWEL_SOUNDS else "a"


def build_edit_prompt(
    room: RoomModel,
    all_items: list,
    *,
    style: str,
    palette: dict | None = None,
    replaces_by_catalog_id: dict[int, list[str]] | None = None,
    wall_color: str | None = None,
) -> str:
    """`all_items` — existing + newly placed FurnitureItem/LayoutObject-like
    objects (duck-typed the same way ai.visualization.floorplan is).

    Deliberately does NOT instruct a full-room redecorate — this is meant to
    be the same room, edited, not a fresh room in the target style (see
    PLAN.md, 2026-09-18: a blanket "redecorate this room in {style}" leading
    instruction was exactly why a real user's uploaded photo came back as an
    unrecognizable room). Recommendations already only ever add/replace what
    the recommendation engine (ai/recommendation/scoring.py) actually
    decided was missing or mismatched — kept items are named explicitly so
    an editing-capable provider has no reason to touch them.

    `wall_color` (2026-09-18, decision D024 extension): the ONE other
    explicit, targeted change this function will describe outside of
    furniture — there is no "wall" catalog item, so a wall-color request
    from feedback (ai/services/feedback_service.py) has nowhere else to go.
    When set, the leading "keep everything unchanged" sentence excludes
    wall color specifically, so it doesn't contradict the explicit
    instruction added for it below."""
    new_items = [i for i in all_items if not i.is_existing]
    existing_items = [i for i in all_items if i.is_existing]
    replaces_by_catalog_id = replaces_by_catalog_id or {}

    room_label = room.room_type.replace("_", " ")
    kept_aspects = "walls, windows, doors, floor, wall art, colors" if not wall_color else "windows, doors, floor, wall art, furniture colors"
    sentences = [
        f"This is a real photo of a {room_label}. Keep everything in the photo exactly as it is — "
        f"the same {kept_aspects}, and camera perspective — except for the specific additions below."
    ]
    if wall_color:
        sentences.append(f"Paint the walls {wall_color}, keeping their exact shape, position, and texture.")

    if existing_items:
        kept = ", ".join(i.label for i in existing_items)
        sentences.append(f"Keep the existing {kept} in place, unchanged.")

    for item in new_items:
        article = _article_for(item.label)
        replacing = replaces_by_catalog_id.get(item.catalog_item_id)
        if replacing:
            # A real image edit, not just updated metadata — the old item is
            # still visible in the actual photo pixels, so the model needs
            # to be told explicitly to remove it, or it ends up with both.
            old = ", ".join(replacing)
            sentences.append(f"Replace the existing {old} with {article} {item.label.lower()}, in a {style} style.")
            continue
        nearest = _nearest_existing_item(item, all_items)
        position = f"near the {nearest[0].label.lower()}" if nearest is not None else _qualitative_position(item, room)
        sentences.append(f"Add {article} {item.label.lower()} {position}, in a {style} style.")

    if palette and palette.get("preferred_colors") and new_items:
        colors = ", ".join(palette["preferred_colors"])
        sentences.append(f"The new item(s) should use a color palette of {colors}.")

    sentences.append(
        "Keep the result photorealistic and proportionally accurate to a real room, "
        "not an artistic or abstract illustration."
    )

    return " ".join(sentences)
