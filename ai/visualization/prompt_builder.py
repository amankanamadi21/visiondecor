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
) -> str:
    """`all_items` — existing + newly placed FurnitureItem/LayoutObject-like
    objects (duck-typed the same way ai.visualization.floorplan is)."""
    new_items = [i for i in all_items if not i.is_existing]
    existing_items = [i for i in all_items if i.is_existing]

    sentences = [
        f"Redecorate this {room.room_type.replace('_', ' ')} in a {style} interior design style, "
        f"keeping the room's real walls, windows, doors, and camera perspective unchanged."
    ]

    if existing_items:
        kept = ", ".join(i.label for i in existing_items)
        sentences.append(f"Keep the existing {kept} in place.")

    for item in new_items:
        article = _article_for(item.label)
        nearest = _nearest_existing_item(item, all_items)
        if nearest is not None:
            other, _dist = nearest
            sentences.append(f"Add {article} {item.label.lower()} near the {other.label.lower()}.")
        else:
            position = _qualitative_position(item, room)
            sentences.append(f"Add {article} {item.label.lower()} {position}.")

    if palette and palette.get("preferred_colors"):
        colors = ", ".join(palette["preferred_colors"])
        sentences.append(f"Favor a color palette of {colors} throughout.")

    sentences.append(
        "Keep the result photorealistic and proportionally accurate to a real room, "
        "not an artistic or abstract illustration."
    )

    return " ".join(sentences)
