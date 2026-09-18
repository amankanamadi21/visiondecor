"""
Recommendation scoring engine (decisions D006a, D007a, D019).

`generate_recommendation` is the single entry point: given a RoomModel, the
detected/existing style, the user's preferences, and a total budget, it
returns one recommended catalog item per needed category, each with a full
`score_breakdown` (so nothing here is a black box) and a rationale string
that cites real, retrieved design principles where relevant.

Scoring weights below (style/color/budget/space) are a recommendation-engine
implementation default — unlike the LAYOUT scoring weights (D021), the brief
does not require these be separately approved (brief PART 25's "small
implementation decisions" carve-out), but they are named constants, not
buried magic numbers, so they're easy to revisit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.recommendation.color import color_match_score
from ai.recommendation.needs import allocate_budget, categorize_existing
from ai.recommendation.rag import retrieve_principles
from ai.recommendation.rationale import build_rationale
from ai.room_analysis.room_model import RoomModel
from backend.models.catalog import FurnitureCatalogItem

STYLE_WEIGHT = 0.35
COLOR_WEIGHT = 0.20
BUDGET_WEIGHT = 0.25
SPACE_WEIGHT = 0.20
assert abs((STYLE_WEIGHT + COLOR_WEIGHT + BUDGET_WEIGHT + SPACE_WEIGHT) - 1.0) < 1e-9

MAX_ITEM_SHARE_OF_FREE_AREA = 0.30  # a single new item shouldn't dominate the free floor space
DEFAULT_FREE_SPACE_RATIO = 0.6  # used only when RoomModel.free_space_ratio is unset


@dataclass
class ScoredItem:
    catalog_item: FurnitureCatalogItem
    category: str
    score_breakdown: dict
    total_score: float
    rationale: str
    category_budget: float
    action: str = "add"  # "add" | "keep" | "replace" — "keep" only via forced_keep_ids (D024), "replace"
    # only when the room's overall detected style doesn't match preferred_style (see generate_recommendation)
    replaces_labels: list[str] = field(default_factory=list)  # existing labels this item replaces, if action=="replace"


@dataclass
class RecommendationResult:
    items: list[ScoredItem]
    total_cost: float
    budget: float
    within_budget: bool
    palette: dict
    # Existing furniture labels that a "replace" item is meant to replace —
    # the pipeline uses this to drop the old item from the room model before
    # layout/visualization, so the replacement doesn't just get added
    # alongside it (see generate_recommendation).
    replaced_existing_labels: list[str] = field(default_factory=list)


def _style_match_score(item_styles: list[str], preferred_style: str, detected_style: str) -> float:
    if preferred_style in item_styles:
        return 1.0
    if detected_style in item_styles:
        return 0.6
    return 0.2


def _budget_fit_score(price: float, category_budget: float) -> float:
    if category_budget <= 0:
        return 0.5  # no meaningful budget signal — neutral score, not zero
    if price <= category_budget:
        return 1.0
    overage_ratio = (price - category_budget) / category_budget
    return max(0.0, 1.0 - overage_ratio)


def _space_fit_score(item_area_cm2: float, free_area_cm2: float) -> float:
    if free_area_cm2 <= 0:
        return 0.3
    threshold = MAX_ITEM_SHARE_OF_FREE_AREA * free_area_cm2
    if item_area_cm2 <= threshold:
        return 1.0
    overage_ratio = (item_area_cm2 - threshold) / threshold
    return max(0.2, 1.0 - overage_ratio)


def _retrieve_category_principles(db: Session, room: RoomModel, category: str, preferred_style: str):
    """Retrieved ONCE per category, not per candidate. Each retrieval runs a
    real embedding pass (CPU, ~50-200ms), and the query is essentially the
    same for every candidate in a category — doing it per-candidate cost
    ~20-30 redundant embeddings per generation, which dominated the whole
    request (measured: a first generation took ~32s before this change)."""
    query_text = f"{room.room_type} {category} {preferred_style}"
    return retrieve_principles(db, query_text, room_type=room.room_type, style=preferred_style, top_k=2)


def _score_candidate(
    db: Session,
    candidate: FurnitureCatalogItem,
    *,
    category: str,
    category_budget: float,
    room: RoomModel,
    preferred_style: str,
    detected_style: str,
    preferred_colors: list[str],
    free_area_cm2: float,
    currency: str,
    principles: list,
    action: str = "add",
    replacing_labels: list[str] | None = None,
) -> ScoredItem:
    style_match = _style_match_score(candidate.style_tags, preferred_style, detected_style)
    color_match = color_match_score(preferred_colors, candidate.color)
    budget_fit = _budget_fit_score(float(candidate.price), category_budget)
    item_area_cm2 = candidate.width_cm * candidate.depth_cm
    space_fit = _space_fit_score(item_area_cm2, free_area_cm2)

    total_score = (
        STYLE_WEIGHT * style_match + COLOR_WEIGHT * color_match
        + BUDGET_WEIGHT * budget_fit + SPACE_WEIGHT * space_fit
    )

    rationale = build_rationale(
        item_name=candidate.name, style_match=style_match, color_match=color_match,
        budget_fit=budget_fit, space_fit=space_fit, price=float(candidate.price),
        category_budget=category_budget, currency=currency, preferred_style=preferred_style,
        principles=principles,
    )
    if action == "keep":
        rationale = "Kept per your feedback. " + rationale
    elif action == "replace":
        # No per-item style/color data exists for existing (detected) furniture —
        # only a room-level detected style — so this is a room-level mismatch
        # signal, not a claim about the specific existing piece's own style.
        existing = ", ".join(replacing_labels or []) or "your existing item"
        rationale = (
            f"Your current {existing} doesn't match your preferred {preferred_style} style "
            f"(the room was detected as {detected_style} overall). " + rationale
        )

    return ScoredItem(
        catalog_item=candidate, category=category,
        score_breakdown={
            "style_match": round(style_match, 3), "color_match": round(color_match, 3),
            "budget_fit": round(budget_fit, 3), "space_fit": round(space_fit, 3),
            "principle_citations": [p.code for p in principles],
        },
        total_score=total_score, rationale=rationale, category_budget=category_budget, action=action,
        replaces_labels=list(replacing_labels or []) if action == "replace" else [],
    )


def generate_recommendation(
    db: Session,
    *,
    room: RoomModel,
    detected_style: str,
    preferred_style: str,
    preferred_colors: list[str],
    budget: float,
    currency: str = "INR",
    excluded_catalog_ids: list[int] | None = None,
    forced_keep_ids: list[int] | None = None,
    drop_lowest_priority_categories: int = 0,
) -> RecommendationResult:
    """`excluded_catalog_ids`/`forced_keep_ids`/`drop_lowest_priority_categories`
    exist for the D024 feedback loop (backend/services/pipeline_stages.py
    reads the latest Feedback row and passes these through) — a fresh,
    first-time call simply omits them."""
    excluded_catalog_ids = set(excluded_catalog_ids or [])
    forced_keep_ids = list(forced_keep_ids or [])

    existing_labels = [f.label for f in room.existing_furniture]
    covered = categorize_existing(room.room_type, existing_labels)
    needed = [category for category, matches in covered.items() if not matches]
    if drop_lowest_priority_categories > 0:
        needed = needed[: max(0, len(needed) - drop_lowest_priority_categories)]

    # No per-item style/color data exists for existing (detected) furniture —
    # only a room-level detected style — so a covered category is only
    # flagged for a possible replacement when the room's overall detected
    # style doesn't match what the user actually wants. User-confirmed items
    # (the one path where a user deliberately placed a real piece — see
    # RoomModel.FurnitureItem.user_confirmed) are never replace-eligible:
    # confirming its geometry is a deliberate act of keeping it, not
    # something a coarse room-level style signal should override.
    confirmed_labels = {f.label for f in room.existing_furniture if f.user_confirmed}
    style_mismatch = bool(preferred_style) and preferred_style != detected_style
    mismatched = {
        c: matches for c, matches in covered.items()
        if matches and style_mismatch and c not in needed and not any(label in confirmed_labels for label in matches)
    }

    categories = needed + list(mismatched.keys())
    category_budgets = allocate_budget(budget, categories)

    free_area_cm2 = room.area_cm2 * (room.free_space_ratio if room.free_space_ratio is not None else DEFAULT_FREE_SPACE_RATIO)

    scored_items: list[ScoredItem] = []
    replaced_existing_labels: list[str] = []
    for category in categories:
        category_budget = category_budgets[category]
        candidates = db.execute(
            select(FurnitureCatalogItem)
            .where(FurnitureCatalogItem.category == category)
            .where(FurnitureCatalogItem.id.notin_(excluded_catalog_ids) if excluded_catalog_ids else True)
        ).scalars().all()
        if not candidates:
            continue

        action = "replace" if category in mismatched else "add"
        principles = _retrieve_category_principles(db, room, category, preferred_style)
        best: ScoredItem | None = None
        for candidate in candidates:
            scored = _score_candidate(
                db, candidate, category=category, category_budget=category_budget, room=room,
                preferred_style=preferred_style, detected_style=detected_style,
                preferred_colors=preferred_colors, free_area_cm2=free_area_cm2, currency=currency,
                principles=principles, action=action, replacing_labels=mismatched.get(category),
            )
            if best is None or scored.total_score > best.total_score:
                best = scored
        if best is not None:
            scored_items.append(best)
            if action == "replace":
                replaced_existing_labels.extend(mismatched[category])

    # D024 feedback loop: honor explicit "keep" requests even if the item
    # wouldn't have won its category on score alone, or belongs to a
    # category not otherwise being recommended this iteration.
    for keep_id in forced_keep_ids:
        kept_candidate = db.get(FurnitureCatalogItem, keep_id)
        if kept_candidate is None:
            continue
        category_budget = category_budgets.get(kept_candidate.category, budget * 0.1)
        principles = _retrieve_category_principles(db, room, kept_candidate.category, preferred_style)
        kept_scored = _score_candidate(
            db, kept_candidate, category=kept_candidate.category, category_budget=category_budget,
            room=room, preferred_style=preferred_style, detected_style=detected_style,
            preferred_colors=preferred_colors, free_area_cm2=free_area_cm2, currency=currency,
            principles=principles, action="keep",
        )
        existing_same_category = next((i for i in scored_items if i.category == kept_candidate.category), None)
        if existing_same_category is not None:
            scored_items.remove(existing_same_category)
            if existing_same_category.action == "replace":
                for label in mismatched.get(kept_candidate.category, []):
                    if label in replaced_existing_labels:
                        replaced_existing_labels.remove(label)
        scored_items.append(kept_scored)

    total_cost = sum(float(i.catalog_item.price) for i in scored_items)
    palette = {
        "preferred_colors": preferred_colors,
        "chosen_item_colors": [i.catalog_item.color for i in scored_items],
    }

    return RecommendationResult(
        items=scored_items,
        total_cost=total_cost,
        budget=budget,
        within_budget=total_cost <= budget,
        palette=palette,
        replaced_existing_labels=replaced_existing_labels,
    )
