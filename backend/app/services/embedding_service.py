
from functools import lru_cache
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Load the local embedding model once per application process."""
    from fastembed import TextEmbedding

    logger.info("Loading local embedding model: %s", MODEL_NAME)

    return TextEmbedding(model_name=MODEL_NAME)


class EmbeddingService:
    """Generate local text embeddings without calling an external API."""

    def __init__(self, model: Any | None = None) -> None:
        # Allow an injected model for deterministic unit tests.
        self._model = model

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = _load_model()

        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Return a normalized-shape vector for a single text."""
        if not text.strip():
            raise ValueError("Cannot embed empty text.")

        vectors = self.embed_texts([text])
        return vectors[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one model call."""
        if not texts:
            return []

        if any(not text.strip() for text in texts):
            raise ValueError("Cannot embed empty text.")

        model = self._get_model()
        generated = model.embed(texts)

        vectors: list[list[float]] = []

        for vector in generated:
            values = [float(value) for value in vector]

            if len(values) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    "Embedding model returned an unexpected vector size: "
                    f"{len(values)}; expected {EMBEDDING_DIMENSIONS}."
                )

            if not all(math.isfinite(value) for value in values):
                raise ValueError(
                    "Embedding model returned non-finite values."
                )

            vectors.append(values)

        if len(vectors) != len(texts):
            raise ValueError(
                "Embedding model returned an unexpected number of vectors."
            )

        return vectors
