
import pytest

from app.services.embedding_service import (
    EMBEDDING_DIMENSIONS,
    EmbeddingService,
)


class FakeEmbeddingModel:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))

        for _ in texts:
            yield [0.25] * EMBEDDING_DIMENSIONS


def test_embed_text_returns_expected_vector():
    model = FakeEmbeddingModel()
    service = EmbeddingService(model=model)

    vector = service.embed_text("Photosynthesis in plants")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert all(value == 0.25 for value in vector)
    assert model.calls == [["Photosynthesis in plants"]]


def test_embed_texts_embeds_multiple_chunks_in_one_call():
    model = FakeEmbeddingModel()
    service = EmbeddingService(model=model)

    vectors = service.embed_texts(
        [
            "Gradient descent updates weights.",
            "Neural networks contain layers.",
        ]
    )

    assert len(vectors) == 2
    assert all(
        len(vector) == EMBEDDING_DIMENSIONS
        for vector in vectors
    )
    assert model.calls == [[
        "Gradient descent updates weights.",
        "Neural networks contain layers.",
    ]]


def test_embed_text_rejects_empty_text():
    service = EmbeddingService(model=FakeEmbeddingModel())

    with pytest.raises(ValueError, match="empty text"):
        service.embed_text("   ")


def test_embed_texts_returns_empty_list_for_empty_input():
    service = EmbeddingService(model=FakeEmbeddingModel())

    assert service.embed_texts([]) == []


def test_embed_texts_rejects_blank_items():
    service = EmbeddingService(model=FakeEmbeddingModel())

    with pytest.raises(ValueError, match="empty text"):
        service.embed_texts(["valid text", "  "])


def test_embed_texts_rejects_wrong_vector_dimensions():
    class IncorrectModel:
        def embed(self, texts):
            for _ in texts:
                yield [0.1, 0.2]

    service = EmbeddingService(model=IncorrectModel())

    with pytest.raises(ValueError, match="unexpected vector size"):
        service.embed_text("Test text")


def test_embed_texts_rejects_non_finite_values():
    class InvalidModel:
        def embed(self, texts):
            for _ in texts:
                yield [float("nan")] * EMBEDDING_DIMENSIONS

    service = EmbeddingService(model=InvalidModel())

    with pytest.raises(ValueError, match="non-finite"):
        service.embed_text("Test text")
