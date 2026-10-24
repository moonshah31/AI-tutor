
import asyncio

from bson import ObjectId

from app.services.document_retrieval_service import DocumentRetrievalService


def add_ready_document(
    database,
    *,
    user_id: ObjectId,
    batch_id: ObjectId,
) -> ObjectId:
    """Add a ready document with an active chunk batch to the fake database."""
    document_id = ObjectId()

    database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "status": "ready",
            "active_chunk_batch_id": batch_id,
        }
    )

    return document_id


def add_chunk(
    database,
    *,
    document_id: ObjectId,
    user_id: ObjectId,
    batch_id: ObjectId,
    chunk_number: int,
    text: str,
) -> None:
    database.document_chunks.documents.append(
        {
            "document_id": document_id,
            "user_id": user_id,
            "batch_id": batch_id,
            "chunk_number": chunk_number,
            "section_number": 1,
            "location_label": "Page 1",
            "text": text,
        }
    )


def test_search_returns_relevant_chunks(client):
    _, database = client
    user_id = ObjectId()
    batch_id = ObjectId()

    document_id = add_ready_document(
        database,
        user_id=user_id,
        batch_id=batch_id,
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights to reduce the loss.",
    )
    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=1,
        text="Neural networks contain interconnected layers.",
    )

    service = DocumentRetrievalService(database)

    import asyncio

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="explain gradient descent",
        )
    )

    assert len(results) == 1
    assert results[0]["document_id"] == str(document_id)
    assert results[0]["chunk_number"] == 0
    assert results[0]["score"] == 1.25
    assert "Gradient descent" in results[0]["text"]


def test_search_ignores_chunks_from_old_batches(client):
    _, database = client
    user_id = ObjectId()
    active_batch_id = ObjectId()
    old_batch_id = ObjectId()

    document_id = add_ready_document(
        database,
        user_id=user_id,
        batch_id=active_batch_id,
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=old_batch_id,
        chunk_number=0,
        text="Gradient descent is an outdated version of the document.",
    )
    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=active_batch_id,
        chunk_number=0,
        text="The current lecture explains gradient descent.",
    )

    service = DocumentRetrievalService(database)

    import asyncio

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="gradient descent",
        )
    )

    assert len(results) == 1
    assert results[0]["text"] == (
        "The current lecture explains gradient descent."
    )


def test_search_does_not_return_another_users_chunks(client):
    _, database = client
    current_user_id = ObjectId()
    other_user_id = ObjectId()

    current_batch_id = ObjectId()
    other_batch_id = ObjectId()

    current_document_id = add_ready_document(
        database,
        user_id=current_user_id,
        batch_id=current_batch_id,
    )
    other_document_id = add_ready_document(
        database,
        user_id=other_user_id,
        batch_id=other_batch_id,
    )

    add_chunk(
        database,
        document_id=current_document_id,
        user_id=current_user_id,
        batch_id=current_batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights.",
    )
    add_chunk(
        database,
        document_id=other_document_id,
        user_id=other_user_id,
        batch_id=other_batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights.",
    )

    service = DocumentRetrievalService(database)

    import asyncio

    results = asyncio.run(
        service.search(
            user_id=current_user_id,
            query="gradient descent",
        )
    )

    assert len(results) == 1
    assert results[0]["document_id"] == str(current_document_id)


def test_search_ignores_documents_that_are_not_ready(client):
    _, database = client
    user_id = ObjectId()
    batch_id = ObjectId()
    document_id = ObjectId()

    database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "status": "processing",
            "active_chunk_batch_id": batch_id,
        }
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights.",
    )

    service = DocumentRetrievalService(database)

    import asyncio

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="gradient descent",
        )
    )

    assert results == []



class FakeRetrievalEmbeddingService:
    def __init__(self, vector=None, error=None):
        self.vector = vector or [1.0, 0.0]
        self.error = error
        self.calls = []

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)

        if self.error is not None:
            raise self.error

        return self.vector


def test_search_finds_semantically_related_chunk_without_keyword_overlap(
    client,
):
    _, database = client
    user_id = ObjectId()
    batch_id = ObjectId()

    document_id = add_ready_document(
        database,
        user_id=user_id,
        batch_id=batch_id,
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=0,
        text="A model adjusts its parameters during training.",
    )

    database.document_chunks.documents[-1]["embedding"] = [
        0.9,
        0.1,
    ]

    embeddings = FakeRetrievalEmbeddingService(
        vector=[1.0, 0.0],
    )
    service = DocumentRetrievalService(
        database,
        embedding_service=embeddings,
    )

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="How does gradient descent learn?",
        )
    )

    assert len(results) == 1
    assert results[0]["chunk_number"] == 0
    assert results[0]["score"] > 0
    assert embeddings.calls == [
        "How does gradient descent learn?"
    ]


def test_search_falls_back_to_lexical_when_embedding_fails(client):
    _, database = client
    user_id = ObjectId()
    batch_id = ObjectId()

    document_id = add_ready_document(
        database,
        user_id=user_id,
        batch_id=batch_id,
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights.",
    )

    database.document_chunks.documents[-1]["embedding"] = [
        0.9,
        0.1,
    ]

    service = DocumentRetrievalService(
        database,
        embedding_service=FakeRetrievalEmbeddingService(
            error=RuntimeError("Model unavailable"),
        ),
    )

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="explain gradient descent",
        )
    )

    assert len(results) == 1
    assert results[0]["chunk_number"] == 0
    assert results[0]["score"] == 1.25


def test_search_does_not_call_embeddings_for_legacy_chunks(client):
    _, database = client
    user_id = ObjectId()
    batch_id = ObjectId()

    document_id = add_ready_document(
        database,
        user_id=user_id,
        batch_id=batch_id,
    )

    add_chunk(
        database,
        document_id=document_id,
        user_id=user_id,
        batch_id=batch_id,
        chunk_number=0,
        text="Gradient descent updates model weights.",
    )

    embeddings = FakeRetrievalEmbeddingService()
    service = DocumentRetrievalService(
        database,
        embedding_service=embeddings,
    )

    results = asyncio.run(
        service.search(
            user_id=user_id,
            query="explain gradient descent",
        )
    )

    assert len(results) == 1
    assert results[0]["score"] == 1.25
    assert embeddings.calls == []
