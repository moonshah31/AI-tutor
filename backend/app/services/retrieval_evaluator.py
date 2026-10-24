
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.retrieval_metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    """A question and the IDs of chunks known to be relevant."""

    question: str
    relevant_chunk_ids: frozenset[str]


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    """Aggregate retrieval metrics for one configuration."""

    question_count: int
    recall_at_5: float
    precision_at_5: float
    mean_reciprocal_rank: float


def make_chunk_id(result: Mapping[str, Any]) -> str:
    """Create a stable evaluation ID from a retrieval result."""
    return f"{result['document_id']}:{result['chunk_number']}"


def evaluate_rankings(
    cases: Sequence[RetrievalEvaluationCase],
    rankings: Sequence[Sequence[str]],
    *,
    k: int = 5,
) -> RetrievalEvaluationResult:
    """Calculate macro-averaged metrics across evaluation questions."""
    if not cases:
        raise ValueError("At least one evaluation case is required")

    if len(cases) != len(rankings):
        raise ValueError("Each evaluation case must have one ranking")

    if k < 1:
        raise ValueError("k must be a positive integer")

    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []

    for case, ranking in zip(cases, rankings, strict=True):
        if not case.relevant_chunk_ids:
            raise ValueError(
                "Every evaluation case must have relevant chunk IDs"
            )

        recalls.append(
            recall_at_k(
                ranking,
                case.relevant_chunk_ids,
                k=k,
            )
        )
        precisions.append(
            precision_at_k(
                ranking,
                case.relevant_chunk_ids,
                k=k,
            )
        )
        reciprocal_ranks.append(
            reciprocal_rank(
                ranking,
                case.relevant_chunk_ids,
            )
        )

    count = len(cases)

    return RetrievalEvaluationResult(
        question_count=count,
        recall_at_5=sum(recalls) / count,
        precision_at_5=sum(precisions) / count,
        mean_reciprocal_rank=sum(reciprocal_ranks) / count,
    )


async def evaluate_retriever(
    retriever: Any,
    *,
    user_id: Any,
    cases: Sequence[RetrievalEvaluationCase],
    k: int = 5,
) -> RetrievalEvaluationResult:
    """Run retrieval for every question and evaluate the rankings."""
    rankings: list[list[str]] = []

    for case in cases:
        results = await retriever.search(
            user_id=user_id,
            query=case.question,
            limit=k,
        )
        rankings.append([make_chunk_id(item) for item in results])

    return evaluate_rankings(cases, rankings, k=k)
