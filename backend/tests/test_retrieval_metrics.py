
import pytest

from app.services.retrieval_metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_finds_all_relevant_chunks():
    retrieved = ["chunk_1", "chunk_2", "chunk_3", "chunk_4", "chunk_5"]
    relevant = {"chunk_2", "chunk_4"}

    assert recall_at_k(retrieved, relevant, k=5) == 1.0


def test_recall_at_k_penalizes_missing_relevant_chunks():
    retrieved = ["chunk_1", "chunk_2", "chunk_3"]
    relevant = {"chunk_2", "chunk_4"}

    assert recall_at_k(retrieved, relevant, k=3) == 0.5


def test_precision_at_k_counts_relevant_results():
    retrieved = ["chunk_1", "chunk_2", "chunk_3", "chunk_5", "chunk_4"]
    relevant = {"chunk_2", "chunk_4"}

    assert precision_at_k(retrieved, relevant, k=5) == 0.4


def test_reciprocal_rank_uses_first_relevant_result():
    retrieved = ["chunk_1", "chunk_2", "chunk_3"]
    relevant = {"chunk_2", "chunk_3"}

    assert reciprocal_rank(retrieved, relevant) == 0.5


def test_reciprocal_rank_is_zero_when_no_relevant_result_is_found():
    assert reciprocal_rank(
        ["chunk_1", "chunk_2"],
        {"chunk_3"},
    ) == 0.0


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_metrics_reject_invalid_k(k):
    with pytest.raises(ValueError, match="k must be a positive integer"):
        recall_at_k(["chunk_1"], {"chunk_1"}, k=k)


def test_metrics_reject_empty_relevance_labels():
    with pytest.raises(ValueError, match="relevant_ids must contain"):
        recall_at_k(["chunk_1"], set())

    with pytest.raises(ValueError, match="relevant_ids must contain"):
        precision_at_k(["chunk_1"], set())

    with pytest.raises(ValueError, match="relevant_ids must contain"):
        reciprocal_rank(["chunk_1"], set())
