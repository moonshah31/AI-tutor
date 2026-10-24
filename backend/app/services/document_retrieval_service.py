
import asyncio
import logging
import math
import re
from typing import Any, Protocol

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.embedding_service import EmbeddingService


logger = logging.getLogger(__name__)


class EmbeddingServiceProtocol(Protocol):
    """Interface required for semantic retrieval."""

    def embed_text(self, text: str) -> list[float]:
        ...


class DocumentRetrievalService:
    """Find relevant chunks using lexical and semantic search."""

    STOP_WORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by",
        "can", "do", "for", "from", "how", "i", "in", "is",
        "it", "me", "my", "of", "on", "or", "please", "show",
        "solve", "explain", "the", "this", "to", "what", "with",
        "you", "your",
    }

    MIN_SEMANTIC_SIMILARITY = 0.35
    SEMANTIC_SCORE_WEIGHT = 0.5

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        embedding_service: EmbeddingServiceProtocol | None = None,
        *,
        min_semantic_similarity: float | None = None,
        semantic_score_weight: float | None = None,
    ) -> None:
        self._database = database
        self._embedding_service = (
            embedding_service or EmbeddingService()
        )

        threshold = (
            self.MIN_SEMANTIC_SIMILARITY
            if min_semantic_similarity is None
            else min_semantic_similarity
        )
        weight = (
            self.SEMANTIC_SCORE_WEIGHT
            if semantic_score_weight is None
            else semantic_score_weight
        )

        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not -1.0 <= threshold <= 1.0
        ):
            raise ValueError(
                "min_semantic_similarity must be between -1 and 1"
            )

        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(weight)
            or weight < 0
        ):
            raise ValueError(
                "semantic_score_weight must be a finite, "
                "non-negative number"
            )

        self._min_semantic_similarity = float(threshold)
        self._semantic_score_weight = float(weight)

    async def search(
        self,
        *,
        user_id: ObjectId,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return relevant chunks ranked by hybrid relevance."""

        if limit < 1:
            raise ValueError("limit must be at least 1")

        query_tokens = self._tokenize_ordered(query)
        query_terms = set(query_tokens)

        if not query_terms:
            return []

        documents = self._database.documents.find(
            {
                "user_id": user_id,
                "status": "ready",
            },
            {
                "active_chunk_batch_id": 1,
            },
        )

        eligible_chunks: list[dict[str, Any]] = []

        async for document in documents:
            active_batch_id = document.get("active_chunk_batch_id")

            if active_batch_id is None:
                continue

            chunks = self._database.document_chunks.find(
                {
                    "user_id": user_id,
                    "document_id": document["_id"],
                    "batch_id": active_batch_id,
                }
            )

            async for chunk in chunks:
                eligible_chunks.append(chunk)

        if not eligible_chunks:
            return []

        has_embeddings = any(
            isinstance(chunk.get("embedding"), list)
            for chunk in eligible_chunks
        )

        query_embedding: list[float] | None = None

        if has_embeddings:
            try:
                query_embedding = await asyncio.to_thread(
                    self._embedding_service.embed_text,
                    query,
                )

                if not self._valid_vector(query_embedding):
                    logger.warning(
                        "Query embedding was invalid; "
                        "falling back to lexical retrieval"
                    )
                    query_embedding = None

            except Exception:
                logger.warning(
                    "Query embedding failed; falling back to "
                    "lexical retrieval",
                    exc_info=True,
                )

        candidates: list[dict[str, Any]] = []

        for chunk in eligible_chunks:
            text = chunk.get("text", "")
            chunk_tokens = self._tokenize_ordered(text)
            chunk_terms = set(chunk_tokens)
            matched_terms = query_terms & chunk_terms

            lexical_score = 0.0

            if matched_terms:
                lexical_score = len(matched_terms) / len(query_terms)

                phrase_length = len(query_tokens)

                if phrase_length <= len(chunk_tokens):
                    for index in range(
                        len(chunk_tokens) - phrase_length + 1
                    ):
                        if (
                            chunk_tokens[
                                index:index + phrase_length
                            ]
                            == query_tokens
                        ):
                            lexical_score += 0.25
                            break

            semantic_similarity: float | None = None
            stored_embedding = chunk.get("embedding")

            if (
                query_embedding is not None
                and isinstance(stored_embedding, list)
                and self._valid_vector(stored_embedding)
            ):
                semantic_similarity = self._cosine_similarity(
                    query_embedding,
                    stored_embedding,
                )

            semantic_match = (
                semantic_similarity is not None
                and semantic_similarity
                >= self._min_semantic_similarity
            )

            if not matched_terms and not semantic_match:
                continue

            score = lexical_score

            if semantic_similarity is not None:
                score += (
                    max(0.0, semantic_similarity)
                    * self._semantic_score_weight
                )

            candidates.append(
                {
                    "document_id": str(chunk["document_id"]),
                    "chunk_number": chunk["chunk_number"],
                    "section_number": chunk["section_number"],
                    "location_label": chunk["location_label"],
                    "text": text,
                    "score": score,
                }
            )

        candidates.sort(
            key=lambda item: (
                -item["score"],
                item["document_id"],
                item["chunk_number"],
            )
        )

        return candidates[:limit]

    @staticmethod
    def _valid_vector(vector: list[float]) -> bool:
        return (
            bool(vector)
            and all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in vector
            )
        )

    @classmethod
    def _cosine_similarity(
        cls,
        first: list[float],
        second: list[float],
    ) -> float | None:
        if (
            not cls._valid_vector(first)
            or not cls._valid_vector(second)
            or len(first) != len(second)
        ):
            return None

        dot_product = sum(
            left * right
            for left, right in zip(first, second, strict=True)
        )
        first_norm = math.sqrt(sum(value * value for value in first))
        second_norm = math.sqrt(sum(value * value for value in second))

        if first_norm == 0 or second_norm == 0:
            return None

        return dot_product / (first_norm * second_norm)

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        return set(cls._tokenize_ordered(text))

    @classmethod
    def _tokenize_ordered(cls, text: str) -> list[str]:
        terms = re.findall(
            r"[a-z0-9][a-z0-9_+#.-]*",
            text.lower(),
        )

        return [
            term
            for term in terms
            if len(term) >= 2 and term not in cls.STOP_WORDS
        ]
