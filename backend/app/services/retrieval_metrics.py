
from collections.abc import Collection, Sequence


def _validate_k(k: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")


def _validate_relevant_ids(relevant_ids: Collection[str]) -> None:
    if not relevant_ids:
        raise ValueError("relevant_ids must contain at least one item")


def recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Collection[str],
    k: int = 5,
) -> float:
    """Return the proportion of known relevant items found in the top k."""
    _validate_k(k)
    _validate_relevant_ids(relevant_ids)

    retrieved_top_k = set(retrieved_ids[:k])
    found = retrieved_top_k.intersection(relevant_ids)

    return len(found) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Collection[str],
    k: int = 5,
) -> float:
    """Return the proportion of the top k positions that are relevant."""
    _validate_k(k)
    _validate_relevant_ids(relevant_ids)

    retrieved_top_k = retrieved_ids[:k]
    relevant_count = sum(
        item_id in relevant_ids for item_id in retrieved_top_k
    )

    return relevant_count / k


def reciprocal_rank(
    retrieved_ids: Sequence[str],
    relevant_ids: Collection[str],
) -> float:
    """Return the reciprocal rank of the first relevant result."""
    _validate_relevant_ids(relevant_ids)

    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / rank

    return 0.0
