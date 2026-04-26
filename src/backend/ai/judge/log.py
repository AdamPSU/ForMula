"""Discardable per-/filter-call metrics + log.txt for the tournament.

Two responsibilities:

  1. `TournamentMetrics` dataclass — per-/filter-call summary an operator
     reads to spot regressions: total LLM calls, failure breakdown, score
     distribution, top-bucket dispersion (the saturation indicator),
     latency p50/p99, top-10.

  2. Append the metrics block to `log.txt` in this directory.

Per-LLM-call detail is gated behind the `JUDGE_DEBUG=1` env var (kept
the same env var name so existing tooling continues to work).
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from uuid import UUID

_LOG_PATH = Path(__file__).resolve().parent / "log.txt"


@dataclass
class _CallRecord:
    success: bool
    error_type: str | None
    duration_ms: float
    stage_index: int
    tournament_seed: int


@dataclass
class TournamentMetrics:
    """Aggregated stats for one /filter call's tournament rerank stage."""

    timestamp: str
    profile_summary: str

    # Volume
    n_products_in: int
    R: int
    n_total_calls: int
    n_baseline_calls: int      # CALLS_PER_TOURNAMENT * R — what we'd expect on a clean run

    # Failure breakdown
    n_validation_failures: int
    n_network_failures: int
    n_other_failures: int
    n_fallbacks: int           # selection rounds that hit the deterministic fallback
    fallback_reasons: list[str]

    # Quality signal
    score_distribution: dict[str, float]   # min/p25/median/p75/max/mean of overall_score
    top_bucket_dispersion: int             # distinct integer scores in top-10

    # Performance
    wall_clock_ms: float
    per_call_p50_ms: float
    per_call_p99_ms: float

    # Top-of-leaderboard sanity
    top_10: list[tuple[UUID, int, float]]   # (product_id, points, overall_score)


@dataclass
class _RunAccumulator:
    """Mutable run-state used by tournament.py to record per-call events."""

    profile_summary: str
    n_products_in: int
    R: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    calls: list[_CallRecord] = field(default_factory=list)
    fallbacks: list[tuple[int, int, str]] = field(default_factory=list)  # (stage, seed, reason)

    def record_call(
        self,
        *,
        success: bool,
        error_type: str | None,
        duration_ms: float,
        stage_index: int,
        tournament_seed: int,
    ) -> None:
        self.calls.append(_CallRecord(
            success=success, error_type=error_type, duration_ms=duration_ms,
            stage_index=stage_index, tournament_seed=tournament_seed,
        ))

    def record_fallback(
        self, *, stage_index: int, tournament_seed: int, reason: str,
    ) -> None:
        self.fallbacks.append((stage_index, tournament_seed, reason))

    def finalize(
        self,
        *,
        wall_clock_ms: float,
        score_by_id: dict[UUID, float],
        points_by_id: dict[UUID, int],
        ranked_top_10: list[UUID],
    ) -> TournamentMetrics:
        # Failure breakdown.
        n_validation = sum(
            1 for c in self.calls if not c.success and c.error_type == "Validation"
        )
        n_network = sum(
            1 for c in self.calls if not c.success and c.error_type == "Network"
        )
        n_other = sum(
            1 for c in self.calls
            if not c.success and c.error_type not in ("Validation", "Network")
        )

        # Score distribution over all products.
        scores = sorted(score_by_id.values())
        if scores:
            score_distribution = {
                "min": scores[0],
                "p25": scores[len(scores) // 4],
                "median": median(scores),
                "p75": scores[(3 * len(scores)) // 4],
                "max": scores[-1],
                "mean": mean(scores),
            }
        else:
            score_distribution = {
                "min": 0.0, "p25": 0.0, "median": 0.0,
                "p75": 0.0, "max": 0.0, "mean": 0.0,
            }

        # Top-bucket dispersion: distinct integer point-totals in the top-10.
        # ≥ 6 is healthy (vs the v2 binary judge's value of 1 in the
        # screenshot scenario).
        top10_points = [points_by_id[pid] for pid in ranked_top_10[:10]]
        top_bucket_dispersion = len(set(top10_points))

        # Latency.
        durations = sorted(c.duration_ms for c in self.calls)
        per_call_p50 = median(durations) if durations else 0.0
        per_call_p99 = (
            durations[max(0, int(0.99 * len(durations)) - 1)] if durations else 0.0
        )

        n_total = len(self.calls)
        # Baseline = perfectly-clean call count (no retries).
        from ai.judge.tournament import CALLS_PER_TOURNAMENT
        n_baseline = CALLS_PER_TOURNAMENT * self.R

        return TournamentMetrics(
            timestamp=self.timestamp,
            profile_summary=self.profile_summary,
            n_products_in=self.n_products_in,
            R=self.R,
            n_total_calls=n_total,
            n_baseline_calls=n_baseline,
            n_validation_failures=n_validation,
            n_network_failures=n_network,
            n_other_failures=n_other,
            n_fallbacks=len(self.fallbacks),
            fallback_reasons=[r for _, _, r in self.fallbacks],
            score_distribution=score_distribution,
            top_bucket_dispersion=top_bucket_dispersion,
            wall_clock_ms=wall_clock_ms,
            per_call_p50_ms=per_call_p50,
            per_call_p99_ms=per_call_p99,
            top_10=[
                (pid, points_by_id[pid], score_by_id[pid])
                for pid in ranked_top_10[:10]
            ],
        )


def write_metrics(metrics: TournamentMetrics) -> None:
    """Append one block of aggregate metrics to log.txt."""
    overhead_pct = (
        (metrics.n_total_calls / metrics.n_baseline_calls - 1.0) * 100.0
        if metrics.n_baseline_calls else 0.0
    )
    sd = metrics.score_distribution
    lines: list[str] = [
        f"--- {metrics.timestamp} ---",
        f"profile: {metrics.profile_summary}",
        (
            f"products_in: {metrics.n_products_in}  "
            f"R: {metrics.R}  "
            f"calls: {metrics.n_total_calls} "
            f"(baseline {metrics.n_baseline_calls}, overhead {overhead_pct:+.1f}%)"
        ),
        (
            f"failures: validation={metrics.n_validation_failures} "
            f"network={metrics.n_network_failures} "
            f"other={metrics.n_other_failures} "
            f"fallbacks={metrics.n_fallbacks}"
        ),
        (
            f"score_dist: min={sd['min']:.3f} p25={sd['p25']:.3f} "
            f"median={sd['median']:.3f} p75={sd['p75']:.3f} max={sd['max']:.3f} "
            f"mean={sd['mean']:.3f}"
        ),
        f"top_bucket_dispersion: {metrics.top_bucket_dispersion} (≥6 healthy)",
        (
            f"latency: wall={metrics.wall_clock_ms:.0f}ms  "
            f"per_call p50={metrics.per_call_p50_ms:.0f}ms "
            f"p99={metrics.per_call_p99_ms:.0f}ms"
        ),
    ]

    if metrics.fallback_reasons:
        # Group identical reasons so log.txt stays readable.
        by_reason: dict[str, int] = defaultdict(int)
        for r in metrics.fallback_reasons:
            by_reason[r] += 1
        lines.append("fallbacks:")
        for reason, count in sorted(by_reason.items(), key=lambda kv: -kv[1]):
            lines.append(f"  ({count}x) {reason[:200]}")

    lines.append("top_10:")
    for pid, points, score in metrics.top_10:
        lines.append(f"  {pid}  pts={points:>3}  score={score:.3f}")
    lines.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def debug_enabled() -> bool:
    return os.environ.get("JUDGE_DEBUG", "") == "1"


def write_call_debug(
    *,
    tournament_seed: int,
    stage_index: int,
    system: str,
    user: str,
    raw_response: str,
    error: str | None,
) -> None:
    """Per-call detail log; only writes when JUDGE_DEBUG=1."""
    if not debug_enabled():
        return
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    block = [
        f"=== {ts} seed={tournament_seed} stage={stage_index} ===",
        "system:",
        system,
        "user:",
        user,
        "response:",
        raw_response,
    ]
    if error:
        block.append(f"error: {error}")
    block.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")
