"""
Rationale generation (decision D007a, amended by D006a).

`build_rationale` is a DETERMINISTIC template over real, already-computed
values: the item's score breakdown and any cited design principles. This is
the only rationale path that exists right now.

`maybe_phrase_with_llm` is a documented hook, not a built feature: if (and
only if) FEEDBACK_LLM_PROVIDER/FEEDBACK_LLM_API_KEY are set in the
environment, a future implementation may call an LLM to phrase the same
facts more naturally. Since neither is set by default (see .env.example),
this function is currently a pure no-op that returns the template
unchanged — there is no hidden LLM call, no network request, and nothing
here should be described as "AI-enhanced" until an actual provider is wired
in. The hard boundary from D007a always holds regardless: whatever this
function is given to phrase, it may never change the underlying numbers,
select a different item, or alter a price.
"""
from __future__ import annotations

import os

from ai.recommendation.rag import RetrievedPrinciple


def build_rationale(
    *,
    item_name: str,
    style_match: float,
    color_match: float,
    budget_fit: float,
    space_fit: float,
    price: float,
    category_budget: float,
    currency: str,
    preferred_style: str,
    principles: list[RetrievedPrinciple],
) -> str:
    clauses = []

    if style_match >= 0.9:
        clauses.append(f"matches your {preferred_style} preference")
    elif style_match >= 0.5:
        clauses.append(f"compatible with the room's existing style, blending toward {preferred_style}")

    if color_match >= 0.9:
        clauses.append("matches your color preference")
    elif color_match >= 0.65:
        clauses.append("a neutral tone that fits most palettes")

    if price <= category_budget:
        clauses.append(f"within budget ({currency} {price:,.0f} of {currency} {category_budget:,.0f} allocated)")
    else:
        over = price - category_budget
        clauses.append(
            f"closest fit for this category — {currency} {over:,.0f} over the {currency} {category_budget:,.0f} allocated"
        )

    if space_fit >= 0.8:
        clauses.append("fits comfortably in the available space")
    elif space_fit < 0.5:
        clauses.append("large relative to the available space — may feel tight")

    rationale = f"Recommended {item_name}: " + "; ".join(clauses) + "."

    if principles:
        cited = "; ".join(f"{p.title} ({p.code})" for p in principles)
        rationale += f" Relevant design principles: {cited}."

    return rationale


def maybe_phrase_with_llm(template_text: str) -> str:
    """See module docstring — currently always a no-op."""
    provider = os.environ.get("FEEDBACK_LLM_PROVIDER", "").strip()
    api_key = os.environ.get("FEEDBACK_LLM_API_KEY", "").strip()
    if not provider or not api_key:
        return template_text
    # No provider is wired up yet — when one is, it must only be permitted to
    # restyle `template_text`'s wording, never introduce new facts, prices,
    # or item choices (D007a hard boundary).
    return template_text
