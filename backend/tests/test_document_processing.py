
import asyncio
import io

import pytest
from bson import ObjectId

from app.services.document_processing_service import (
    DocumentProcessingService,
)
from app.storage.local import LocalFileStorage

from app.services.embedding_service import EMBEDDING_DIMENSIONS


class FakeEmbeddingService:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [0.1] * EMBEDDING_DIMENSIONS
            for _ in texts
        ]


def test_document_processing_extracts_text(client, tmp_path):
    _, fake_database = client

    user_id = ObjectId()
    document_id = ObjectId()

    fake_database.users.documents.append(
        {
            "_id": user_id,
            "name": "Test Student",
            "email": "student@example.com",
            "password_hash": "test",
        }
    )

    storage = LocalFileStorage(str(tmp_path))
    storage_reference = f"{user_id}/lecture.txt"

    asyncio.run(
        storage.save(
            file=io.BytesIO(
                b"Introduction to algorithms\n\n"
                b"Algorithms are step-by-step procedures."
            ),
            storage_reference=storage_reference,
        )
    )

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "original_filename": "lecture.txt",
            "stored_filename": "lecture.txt",
            "content_type": "text/plain",
            "file_extension": ".txt",
            "file_size": 72,
            "storage_reference": storage_reference,
            "status": "uploaded",
            "processing_error": None,
            "sections": [],
        }
    )

    service = DocumentProcessingService(
        
        database=fake_database,
        storage=storage,
        embedding_service=FakeEmbeddingService(),
    )

    asyncio.run(
        service.process(
            user_id=user_id,
            document_id=str(document_id),
        )
    )

    document = fake_database.documents.documents[0]
    chunks = fake_database.document_chunks.documents

    assert document["status"] == "ready"
    assert document["processing_error"] is None
    assert len(document["sections"]) == 1
    assert (
        "Introduction to algorithms"
        in document["sections"][0]["text"]
    )

    assert len(chunks) >= 1
    assert all(
        chunk["document_id"] == document_id
        for chunk in chunks
    )
    assert all(
        chunk["user_id"] == user_id
        for chunk in chunks
    )
    assert all(chunk["text"].strip() for chunk in chunks)
    assert any(
        "Introduction to algorithms" in chunk["text"]
        for chunk in chunks
    )

    assert document["active_chunk_batch_id"] is not None
    assert all(
        chunk["batch_id"] == document["active_chunk_batch_id"]
        for chunk in chunks
    )
    assert all(
    len(chunk["embedding"]) == EMBEDDING_DIMENSIONS
    for chunk in chunks
)

def test_document_processing_marks_failed_document(
    client,
    tmp_path,
):
    _, fake_database = client

    user_id = ObjectId()
    document_id = ObjectId()

    storage = LocalFileStorage(str(tmp_path))

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "original_filename": "broken.pdf",
            "stored_filename": "broken.pdf",
            "content_type": "application/pdf",
            "file_extension": ".pdf",
            "file_size": 10,
            "storage_reference": f"{user_id}/missing.pdf",
            "status": "uploaded",
            "processing_error": None,
            "sections": [],
        }
    )

    service = DocumentProcessingService(
        database=fake_database,
        storage=storage,
        embedding_service=FakeEmbeddingService(),
    )

    with pytest.raises(FileNotFoundError):
        asyncio.run(
            service.process(
                user_id=user_id,
                document_id=str(document_id),
            )
        )

    document = fake_database.documents.documents[0]

    assert document["status"] == "failed"
    assert (
        document["processing_error"]
        == "Document processing failed"
    )
    assert fake_database.document_chunks.documents == []


def test_failed_reprocessing_preserves_active_chunks(
    client,
    tmp_path,
):
    _, fake_database = client

    user_id = ObjectId()
    document_id = ObjectId()

    storage = LocalFileStorage(str(tmp_path))
    storage_reference = f"{user_id}/lecture.txt"

    asyncio.run(
        storage.save(
            file=io.BytesIO(
                b"Introduction to algorithms\n\n"
                b"Algorithms are step-by-step procedures."
            ),
            storage_reference=storage_reference,
        )
    )

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "original_filename": "lecture.txt",
            "stored_filename": "lecture.txt",
            "content_type": "text/plain",
            "file_extension": ".txt",
            "file_size": 72,
            "storage_reference": storage_reference,
            "status": "uploaded",
            "processing_error": None,
            "sections": [],
        }
    )

    service = DocumentProcessingService(
        database=fake_database,
        storage=storage,
        embedding_service=FakeEmbeddingService(),
    )

    # First processing attempt succeeds.
    asyncio.run(
        service.process(
            user_id=user_id,
            document_id=str(document_id),
        )
    )

    document = fake_database.documents.documents[0]
    original_batch_id = document["active_chunk_batch_id"]
    original_chunks = [
        dict(chunk)
        for chunk in fake_database.document_chunks.documents
    ]

    assert document["status"] == "ready"
    assert original_batch_id is not None
    assert original_chunks

    # Simulate the original file becoming unavailable before retry.
    asyncio.run(
        storage.delete(storage_reference=storage_reference)
    )

    # Reprocessing fails, but the previous batch must remain usable.
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            service.process(
                user_id=user_id,
                document_id=str(document_id),
            )
        )

    document = fake_database.documents.documents[0]
    remaining_chunks = fake_database.document_chunks.documents

    assert document["status"] == "ready"
    assert document["active_chunk_batch_id"] == original_batch_id
    assert (
        document["processing_error"]
        == "Reprocessing failed; the previous version remains available"
    )

    assert remaining_chunks == original_chunks
    assert all(
        chunk["batch_id"] == original_batch_id
        for chunk in remaining_chunks
    )
 