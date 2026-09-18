"""
Which furniture categories a room type typically needs, and how a total
budget is allocated across the categories actually needed for a given room
(decision D019: single total budget, allocated internally).

These allocation shares are an implementation detail of the recommendation
engine (not a report-mandated architectural decision), so they are not
gated behind a formal approval round — see brief PART 25's "small
implementation decisions" carve-out. They are, however, explicit and
documented here rather than buried, so they're easy to revisit.
"""
from __future__ import annotations

# Categories a room type is expected to have furnished, roughly in priority
# order (used only for documentation/ordering, not for scoring).
ROOM_TYPE_CATEGORIES: dict[str, list[str]] = {
    "living_room": ["sofa", "table", "lighting", "rug", "decor"],
    "bedroom": ["bed", "cabinet", "lighting", "decor"],
    "office": ["table", "chair", "lighting", "shelf"],
    "study_room": ["table", "chair", "shelf", "lighting"],
    "other": ["chair", "table", "decor"],
}

# Relative budget share per category — normalized over just the categories
# actually needed for a given room before being multiplied by the total
# budget. Big-ticket furniture gets the largest share; decor/lighting the
# smallest. Chosen to be directionally reasonable, not empirically tuned.
CATEGORY_BUDGET_SHARE: dict[str, float] = {
    "sofa": 0.35,
    "bed": 0.35,
    "table": 0.15,
    "chair": 0.12,
    "cabinet": 0.15,
    "shelf": 0.10,
    "lighting": 0.08,
    "rug": 0.08,
    "curtain": 0.06,
    "decor": 0.06,
}


# Category -> keyword mapping for the containment check below. Module-level
# since both categorize_existing() and needed_categories() use it.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "sofa": ["sofa", "couch", "sectional"],
    "bed": ["bed"],
    "table": ["table", "desk"],
    "chair": ["chair", "stool"],
    "cabinet": ["cabinet", "wardrobe", "sideboard", "console", "tv stand"],
    "shelf": ["shelf", "bookshelf", "bookcase"],
    "lighting": ["lamp", "light", "pendant"],
    "rug": ["rug", "carpet"],
    "curtain": ["curtain", "drape"],
    "decor": ["plant", "art", "decor", "mirror"],
}


def categorize_existing(room_type: str, existing_labels: list[str]) -> dict[str, list[str]]:
    """Maps each category this room type expects to the existing labels that
    already cover it (empty list if none). Matching is a simple keyword
    containment check against the existing item's label — good enough for
    the fixture-driven scope of this batch; a real system would classify
    existing items by category explicitly rather than pattern-matching their
    label text."""
    candidates = ROOM_TYPE_CATEGORIES.get(room_type, ROOM_TYPE_CATEGORIES["other"])
    return {
        category: [label for label in existing_labels if any(kw in label.lower() for kw in CATEGORY_KEYWORDS.get(category, [category]))]
        for category in candidates
    }


def needed_categories(room_type: str, existing_labels: list[str], drop_lowest_priority: int = 0) -> list[str]:
    """Categories this room type expects that aren't already covered by an
    existing furniture item.

    `drop_lowest_priority` (decision D024 — "less crowded" feedback):
    ROOM_TYPE_CATEGORIES is already ordered roughly by priority, so dropping
    from the end removes the least essential categories first (e.g. decor,
    rug) rather than the ones a room actually needs (e.g. bed, sofa)."""
    covered = categorize_existing(room_type, existing_labels)
    needed = [category for category, matches in covered.items() if not matches]

    if drop_lowest_priority > 0:
        needed = needed[: max(0, len(needed) - drop_lowest_priority)]

    return needed


def allocate_budget(total_budget: float, categories: list[str]) -> dict[str, float]:
    """Splits `total_budget` across `categories` proportionally to
    CATEGORY_BUDGET_SHARE, renormalized over just the categories present."""
    if not categories:
        return {}
    shares = {c: CATEGORY_BUDGET_SHARE.get(c, 0.10) for c in categories}
    total_share = sum(shares.values())
    return {c: total_budget * (share / total_share) for c, share in shares.items()}
