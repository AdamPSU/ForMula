"""Cohere Rerank 4 Fast — runtime reranker.

Public surface:
    from ai.rerank.cohere import rerank, ScoredProduct
"""

from ai.rerank.cohere.models import ScoredProduct
from ai.rerank.cohere.service import rerank

__all__ = ["rerank", "ScoredProduct"]
