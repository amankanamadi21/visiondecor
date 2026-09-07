"""
Retrieval over the design_principles knowledge base (decision D006a).

`retrieve_principles` is the ONLY way anything in this codebase reads
design_principles for use in a rationale. It never invents a principle —
every result is a real row, returned with its `code` so the caller can cite
it, and with a similarity score so a caller can decide a threshold below
which a "principle" is too weak to be worth citing.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.recommendation.embeddings import embed_text
from backend.models.principle import DesignPrinciple

# Below this cosine similarity, a "match" is not worth citing — better to
# show no citation than a tenuous one (brief PART 16: explainability must be
# honest, not decorative).
DEFAULT_MIN_SIMILARITY = 0.25


@dataclass
class RetrievedPrinciple:
    code: str
    category: str
    title: str
    body: str
    similarity: float


def retrieve_principles(
    db: Session,
    query_text: str,
    *,
    room_type: str | None = None,
    style: str | None = None,
    top_k: int = 3,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[RetrievedPrinciple]:
    query_vector = embed_text(query_text).tolist()

    # cosine_distance = 1 - cosine_similarity for normalized vectors.
    distance_col = DesignPrinciple.embedding.cosine_distance(query_vector)
    stmt = select(DesignPrinciple, distance_col.label("distance")).order_by(distance_col)

    # Overfetch, then apply the room_type/style applicability filter in
    # Python — these are small JSONB list columns, not worth a SQL-side
    # containment query for a ~40-row table.
    stmt = stmt.limit(max(top_k * 5, 20))

    results: list[RetrievedPrinciple] = []
    for principle, distance in db.execute(stmt):
        similarity = 1.0 - float(distance)
        if similarity < min_similarity:
            continue
        if principle.applies_to_room_types and room_type not in principle.applies_to_room_types:
            continue
        if principle.applies_to_styles and style not in principle.applies_to_styles:
            continue
        results.append(
            RetrievedPrinciple(
                code=principle.code,
                category=principle.category.value,
                title=principle.title,
                body=principle.body,
                similarity=similarity,
            )
        )
        if len(results) >= top_k:
            break

    return results
