#!/usr/bin/env python3
"""
Recommendation compliance study (decision D025). Runs the real
recommendation engine (ai.recommendation.scoring) against many synthetic
preference combinations — every fixture room x every FR-3 style x several
budget levels — and reports budget-compliance rate, mean style-match score,
and space-fit rate (PLAN.md Section K's third recommendation metric — added
2026-09-08; the underlying score_breakdown['space_fit'] value already
existed per-item, it just wasn't aggregated across a study before). Uses the
real database (real catalog, real design_principles), not mocks, so the
numbers reflect the actual seeded catalog's coverage.

Usage:
    source .venv/bin/activate
    python -m evaluation.run_recommendation_study
"""
from __future__ import annotations

import statistics

from sqlalchemy.orm import Session

from ai.recommendation.scoring import generate_recommendation
from ai.room_analysis.fixtures import FIXTURES
from backend.config import get_config
from backend.db import init_engine

STYLES = ["Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian"]
BUDGET_LEVELS = [20000, 40000, 60000, 80000, 120000]
COLOR_PREFERENCES = [["white"], ["charcoal", "black"], ["natural wood"], []]


def run_study():
    config = get_config()
    engine = init_engine(config.DATABASE_URL)

    total_runs = 0
    within_budget_count = 0
    style_match_scores: list[float] = []
    space_fit_scores: list[float] = []
    per_style_within_budget: dict[str, list[bool]] = {s: [] for s in STYLES}
    per_fixture_space_fit: dict[str, list[float]] = {name: [] for name in FIXTURES}

    with Session(engine) as db:
        for fixture_name, fixture in FIXTURES.items():
            for style in STYLES:
                for budget in BUDGET_LEVELS:
                    colors = COLOR_PREFERENCES[total_runs % len(COLOR_PREFERENCES)]
                    result = generate_recommendation(
                        db, room=fixture.room, detected_style=fixture.style.predicted_style,
                        preferred_style=style, preferred_colors=colors, budget=budget,
                    )
                    total_runs += 1
                    if result.within_budget:
                        within_budget_count += 1
                    per_style_within_budget[style].append(result.within_budget)
                    for item in result.items:
                        style_match_scores.append(item.score_breakdown["style_match"])
                        space_fit_scores.append(item.score_breakdown["space_fit"])
                        per_fixture_space_fit[fixture_name].append(item.score_breakdown["space_fit"])

    # A space_fit of 1.0 means the item comfortably fits under
    # MAX_ITEM_SHARE_OF_FREE_AREA (ai/recommendation/scoring.py); anything
    # lower means the optimizer accepted a space trade-off to satisfy other
    # preferences. "Space-fit rate" = fraction of recommended items that hit
    # that comfortable-fit ceiling, alongside the mean score for granularity.
    return {
        "total_runs": total_runs,
        "budget_compliance_rate": within_budget_count / total_runs,
        "mean_style_match": statistics.mean(style_match_scores) if style_match_scores else None,
        "mean_space_fit": statistics.mean(space_fit_scores) if space_fit_scores else None,
        "space_fit_rate": (
            sum(1 for s in space_fit_scores if s >= 1.0) / len(space_fit_scores) if space_fit_scores else None
        ),
        "per_style_budget_compliance": {
            s: sum(v) / len(v) for s, v in per_style_within_budget.items()
        },
        "per_fixture_mean_space_fit": {
            name: statistics.mean(v) for name, v in per_fixture_space_fit.items() if v
        },
    }


def print_report(report: dict) -> None:
    print(f"Recommendation compliance study — {report['total_runs']} synthetic preference combinations")
    print("=" * 80)
    print(f"Overall budget compliance rate: {report['budget_compliance_rate']:.1%}")
    print(f"Mean style-match score (across all recommended items): {report['mean_style_match']:.4f}")
    print(f"Space-fit rate (items at the comfortable-fit ceiling, score == 1.0): {report['space_fit_rate']:.1%}")
    print(f"Mean space-fit score (across all recommended items): {report['mean_space_fit']:.4f}")
    print()
    print("Budget compliance by preferred style:")
    for style, rate in report["per_style_budget_compliance"].items():
        print(f"  {style:15s} {rate:.1%}")
    print()
    print("Mean space-fit by fixture room:")
    for fixture_name, mean_fit in report["per_fixture_mean_space_fit"].items():
        print(f"  {fixture_name:15s} {mean_fit:.4f}")


if __name__ == "__main__":
    print_report(run_study())
