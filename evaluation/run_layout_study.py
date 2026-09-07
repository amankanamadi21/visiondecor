#!/usr/bin/env python3
"""
Layout-vs-baseline evaluation study (decision D025).

Runs the Simulated Annealing optimiser (ai.layout_optimization.optimizer)
against a random-placement baseline and a greedy/first-fit baseline
(evaluation.layout_baselines) across all four room fixtures, several times
each with different seeds, and reports mean layout score, hard-constraint
feasibility rate, and space utilization per method.

This produces REAL, measured numbers from code that already exists and is
already tested — nothing here is projected or estimated. Run it and use its
actual printed output in the report; do not paraphrase or round the numbers
by hand.

Usage:
    source .venv/bin/activate
    python -m evaluation.run_layout_study
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from ai.layout_optimization.optimizer import PlacementSpec, optimize_layout
from ai.layout_optimization.scoring import compute_layout_score
from ai.room_analysis.fixtures import FIXTURES
from evaluation.layout_baselines import greedy_first_fit_baseline, random_baseline

TRIALS_PER_FIXTURE = 8
SA_ITERATIONS = 1200

SPECS = [
    PlacementSpec(label="Coffee Table", width_cm=70, depth_cm=45, height_cm=40, category="table"),
    PlacementSpec(label="Floor Lamp", width_cm=30, depth_cm=30, height_cm=165, category="lighting"),
    PlacementSpec(label="Small Rug", width_cm=90, depth_cm=60, height_cm=1, category="rug"),
]


@dataclass
class MethodStats:
    feasible_count: int
    total_trials: int
    scores: list[float]
    space_utilizations: list[float]

    @property
    def feasibility_rate(self) -> float:
        return self.feasible_count / self.total_trials if self.total_trials else 0.0

    @property
    def mean_score(self) -> float | None:
        return statistics.mean(self.scores) if self.scores else None

    @property
    def mean_space_utilization(self) -> float | None:
        return statistics.mean(self.space_utilizations) if self.space_utilizations else None


def _record(stats: MethodStats, room, placed_items) -> None:
    stats.total_trials += 1
    if placed_items is None:
        return
    stats.feasible_count += 1
    result = compute_layout_score(room, placed_items)
    stats.scores.append(result.total_score)
    stats.space_utilizations.append(result.breakdown["space_utilization"])


def run_study() -> dict[str, dict[str, MethodStats]]:
    results: dict[str, dict[str, MethodStats]] = {}

    for fixture_name, fixture in sorted(FIXTURES.items()):
        room = fixture.room
        sa_stats = MethodStats(0, 0, [], [])
        random_stats = MethodStats(0, 0, [], [])
        greedy_stats = MethodStats(0, 0, [], [])

        for trial in range(TRIALS_PER_FIXTURE):
            seed = trial * 17 + 1

            try:
                sa_result = optimize_layout(room, SPECS, seed=seed, iterations=SA_ITERATIONS)
                _record(sa_stats, room, sa_result.placed_items)
            except Exception:
                _record(sa_stats, room, None)

            _record(random_stats, room, random_baseline(room, SPECS, seed=seed))

        # Greedy first-fit is fully deterministic (no seed) — one run fully
        # determines its result, so it's recorded TRIALS_PER_FIXTURE times
        # only to keep the reported feasibility-rate denominators comparable
        # across methods, not because repeating it changes the outcome.
        greedy_placed = greedy_first_fit_baseline(room, SPECS)
        for _ in range(TRIALS_PER_FIXTURE):
            _record(greedy_stats, room, greedy_placed)

        results[fixture_name] = {"simulated_annealing": sa_stats, "random": random_stats, "greedy_first_fit": greedy_stats}

    return results


def print_report(results: dict[str, dict[str, MethodStats]]) -> None:
    print(f"Layout-vs-baseline study — {TRIALS_PER_FIXTURE} trials/fixture, SA iterations={SA_ITERATIONS}")
    print("=" * 100)
    for fixture_name, methods in results.items():
        print(f"\n{fixture_name}")
        print(f"{'method':22s} {'feasibility':>12s} {'mean score':>12s} {'mean space util':>16s}")
        for method_name, stats in methods.items():
            score_str = f"{stats.mean_score:.4f}" if stats.mean_score is not None else "n/a"
            space_str = f"{stats.mean_space_utilization:.4f}" if stats.mean_space_utilization is not None else "n/a"
            print(f"{method_name:22s} {stats.feasibility_rate:>11.0%} {score_str:>12s} {space_str:>16s}")

    print("\n" + "=" * 100)
    print("Aggregate across all fixtures:")
    for method_name in ("simulated_annealing", "random", "greedy_first_fit"):
        all_scores = [s for methods in results.values() for s in methods[method_name].scores]
        all_feasible = sum(methods[method_name].feasible_count for methods in results.values())
        all_total = sum(methods[method_name].total_trials for methods in results.values())
        mean_score = statistics.mean(all_scores) if all_scores else None
        print(
            f"  {method_name:22s} feasibility={all_feasible}/{all_total} "
            f"({all_feasible/all_total:.0%})  mean_score={mean_score:.4f}" if mean_score is not None
            else f"  {method_name:22s} feasibility={all_feasible}/{all_total}  mean_score=n/a"
        )


if __name__ == "__main__":
    print_report(run_study())
