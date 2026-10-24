
from dataclasses import dataclass
from typing import Any, Sequence

from bson import ObjectId

from app.services.retrieval_evaluator import (
    RetrievalEvaluationCase,
    RetrievalEvaluationResult,
    evaluate_retriever,
)
from app.services.document_retrieval_service import (
    DocumentRetrievalService,
)


@dataclass(frozen=True)
class RetrievalConfiguration:
    threshold: float
    weight: float


@dataclass(frozen=True)
class RetrievalSweepResult:
    configuration: RetrievalConfiguration
    metrics: RetrievalEvaluationResult


async def run_parameter_sweep(
    *,
    database: Any,
    user_id: ObjectId,
    cases: Sequence[RetrievalEvaluationCase],
    thresholds: Sequence[float],
    weights: Sequence[float],
    embedding_service: Any | None = None,
    k: int = 5,
) -> list[RetrievalSweepResult]:
    """Evaluate every threshold/weight combination."""
    if not thresholds:
        raise ValueError("At least one threshold is required")

    if not weights:
        raise ValueError("At least one weight is required")

    sweep_results: list[RetrievalSweepResult] = []

    for threshold in thresholds:
        for weight in weights:
            retriever = DocumentRetrievalService(
                database,
                embedding_service=embedding_service,
                min_semantic_similarity=threshold,
                semantic_score_weight=weight,
            )

            metrics = await evaluate_retriever(
                retriever,
                user_id=user_id,
                cases=cases,
                k=k,
            )

            sweep_results.append(
                RetrievalSweepResult(
                    configuration=RetrievalConfiguration(
                        threshold=threshold,
                        weight=weight,
                    ),
                    metrics=metrics,
                )
            )

    # Prefer higher MRR, then higher recall, then higher precision.
    sweep_results.sort(
        key=lambda item: (
            -item.metrics.mean_reciprocal_rank,
            -item.metrics.recall_at_5,
            -item.metrics.precision_at_5,
        )
    )

    return sweep_results
