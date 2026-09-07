#!/usr/bin/env python3
"""
Run the recommendation + layout optimiser on a named fixture and print the
result — a real, inspectable run, not just something asserted by a test.

Usage:
    source .venv/bin/activate
    python -m ai.layout_optimization.cli bedroom_small_scandinavian \
        --preferred-style Scandinavian --colors white,natural wood --budget 60000
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from ai.recommendation.scoring import generate_recommendation
from ai.layout_optimization.optimizer import PlacementSpec, optimize_layout, LayoutInfeasibleError
from ai.room_analysis.fixtures import FIXTURES, get_fixture
from backend.config import get_config
from backend.db import init_engine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=sorted(FIXTURES), help="Fixture room name")
    parser.add_argument("--preferred-style", default=None, help="Defaults to the fixture's detected style")
    parser.add_argument("--colors", default="white", help="Comma-separated preferred colors")
    parser.add_argument("--budget", type=float, default=50000, help="Total budget (INR)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=1500)
    args = parser.parse_args()

    fixture = get_fixture(args.fixture)
    preferred_style = args.preferred_style or fixture.style.predicted_style
    colors = [c.strip() for c in args.colors.split(",")]

    print(f"Room: {args.fixture} — {fixture.description}")
    print(f"Room dims: {fixture.room.width_cm:.0f} x {fixture.room.length_cm:.0f} cm ({fixture.room.room_type})")
    print(
        f"Detected style: {fixture.style.predicted_style} "
        f"({fixture.style.confidence:.0%}), preferred: {preferred_style}"
    )
    print()

    config = get_config()
    engine = init_engine(config.DATABASE_URL)
    with Session(engine) as db:
        rec = generate_recommendation(
            db,
            room=fixture.room,
            detected_style=fixture.style.predicted_style,
            preferred_style=preferred_style,
            preferred_colors=colors,
            budget=args.budget,
        )

        print(f"Recommendations (budget INR {args.budget:,.0f}):")
        for item in rec.items:
            print(f"  [{item.category:10s}] {item.catalog_item.name} — INR {item.catalog_item.price:,.0f}")
            print(f"      {item.rationale}")
        print(f"Total: INR {rec.total_cost:,.0f}  (within budget: {rec.within_budget})")
        print()

        specs = [
            PlacementSpec(
                label=i.catalog_item.name, width_cm=i.catalog_item.width_cm,
                depth_cm=i.catalog_item.depth_cm, height_cm=i.catalog_item.height_cm,
                category=i.category, catalog_item_id=i.catalog_item.id,
            )
            for i in rec.items
        ]

        try:
            result = optimize_layout(fixture.room, specs, seed=args.seed, iterations=args.iterations)
        except LayoutInfeasibleError as exc:
            print(f"LAYOUT INFEASIBLE: {exc}")
            return 1

        print(f"Layout score: {result.score.total_score:.4f}  (algorithm={result.algorithm}, seed={result.seed})")
        print("Score breakdown:")
        for k, v in result.score.breakdown.items():
            print(f"  {k:20s} {v:.4f}")
        print("Constraints satisfied:")
        for k, v in result.constraints_satisfied.items():
            print(f"  {k:20s} {'✓' if v else '✗'}")
        print()
        print("Placed items:")
        for item in result.placed_items:
            print(f"  {item.label:35s} pos=({item.x_cm:6.1f},{item.y_cm:6.1f}) rot={item.rotation_deg:3d}°")

    return 0


if __name__ == "__main__":
    sys.exit(main())
