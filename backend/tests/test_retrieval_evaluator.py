
import pytest

from app.services.retrieval_evaluator import (
    RetrievalEvaluationCase,
    evaluate_rankings,
    make_chunk_id,
)


def test_make_chunk_id_uses_document_and_chunk_number():
    result = {
        "document_id": "document123",
        "chunk_number": 4,
    }

    assert make_chunk_id(result) == "document123:4"


def test_evaluate_rankings_calculates_average_metrics():
    cases = [
        RetrievalEvaluationCase(
            question="Question one",
            relevant_chunk_ids=frozenset({"doc1:1"}),
        ),
        RetrievalEvaluationCase(
            question="Question two",
            relevant_chunk_ids=frozenset({"doc2:2"}),
        ),
    ]
    rankings = [
        ["doc1:1", "doc1:2"],
        ["doc2:3", "doc2:2"],
    ]

    result = evaluate_rankings(cases, rankings, k=2)

    assert result.question_count == 2
    assert result.recall_at_5 == 1.0
    assert result.precision_at_5 == 0.5
    assert result.mean_reciprocal_rank == 0.75


def test_evaluate_rankings_rejects_missing_rankings():
    cases = [
        RetrievalEvaluationCase(
            question="Question one",
            relevant_chunk_ids=frozenset({"doc1:1"}),
        )
    ]

    with pytest.raises(ValueError, match="one ranking"):
        evaluate_rankings(cases, [], k=5)


def test_evaluate_rankings_rejects_empty_cases():
    with pytest.raises(ValueError, match="At least one"):
        evaluate_rankings([], [])


def test_evaluate_rankings_rejects_cases_without_labels():
    cases = [
        RetrievalEvaluationCase(
            question="Question one",
            relevant_chunk_ids=frozenset(),
        )
    ]

    with pytest.raises(ValueError, match="relevant chunk IDs"):
        evaluate_rankings(cases, [[]])


def test_evaluate_rankings_rejects_invalid_k():
    cases = [
        RetrievalEvaluationCase(
            question="Question one",
            relevant_chunk_ids=frozenset({"doc1:1"}),
        )
    ]

    with pytest.raises(ValueError, match="positive integer"):
        evaluate_rankings(cases, [[]], k=0)
