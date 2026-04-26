"""Tournament reranker — public surface.

Replaces the v2 decomposed-binary judge. The package keeps the same
import path so call sites don't move; internals are now a TourRank-style
multi-round selection cascade (Chen et al., WWW 2025).

    from ai.judge import score_many, ProductJudgment, TournamentMetrics
"""

from ai.judge.log import TournamentMetrics
from ai.judge.models import ProductJudgment
from ai.judge.service import score_many

__all__ = ["score_many", "ProductJudgment", "TournamentMetrics"]
