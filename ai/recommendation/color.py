"""
Simple, explainable color-compatibility scoring — deliberately not a
learned model. A user's stated color preferences are free-text strings
(e.g. "warm neutrals", "sage green"); catalog item colors are also
free-text (e.g. "light gray", "mustard yellow"). Matching is keyword-based:
exact/substring overlap scores highest, a fixed set of "universally
compatible" neutrals gets partial credit even with no direct overlap, and
anything else gets a low baseline rather than zero (a color that doesn't
match the stated preference isn't necessarily ugly in the room).
"""
from __future__ import annotations

NEUTRAL_KEYWORDS = {
    "white", "off-white", "cream", "beige", "gray", "grey", "black",
    "natural wood", "walnut", "oak", "taupe", "ivory",
}

EXACT_MATCH_SCORE = 1.0
NEUTRAL_FALLBACK_SCORE = 0.7
NO_MATCH_BASELINE = 0.35


def _tokenize(text: str) -> set[str]:
    return set(text.lower().replace("-", " ").split())


def color_match_score(preferred_colors: list[str], item_color: str) -> float:
    if not preferred_colors:
        return NEUTRAL_FALLBACK_SCORE  # no stated preference — treat neutrally

    item_tokens = _tokenize(item_color)
    for preferred in preferred_colors:
        preferred_tokens = _tokenize(preferred)
        if item_tokens & preferred_tokens:
            return EXACT_MATCH_SCORE

    if item_tokens & NEUTRAL_KEYWORDS:
        return NEUTRAL_FALLBACK_SCORE

    return NO_MATCH_BASELINE
