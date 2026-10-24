
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.routes.chat import get_tutor_service
from app.services.document_retrieval_service import (
    DocumentRetrievalService,
)
from app.services.tutor_service import TutorService


PASSWORD = "StrongPass123!"


def create_student(test_client, fake_database, email, name):
    """Register a student and return their auth header and database ID."""
    registration = test_client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
        },
    )
    assert registration.status_code in (200, 201)

    login = test_client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )
    assert login.status_code == 200

    user = next(
        item
        for item in fake_database.users.documents
        if item["email"] == email
    )

    return (
        {"Authorization": f"Bearer {login.json()['access_token']}"},
        user["_id"],
    )


def create_conversation(test_client, headers):
    response = test_client.post(
        "/api/conversations",
        headers=headers,
        json={"title": "RAG Integration Test"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_document(
    fake_database,
    *,
    user_id,
    status,
    batch_id,
    text,
    document_id=None,
    chunk_number=1,
):
    """Insert a document and its chunk into the fake database."""
    document_id = document_id or ObjectId()

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "filename": "lecture.pdf",
            "status": status,
            "active_chunk_batch_id": batch_id,
        }
    )

    fake_database.document_chunks.documents.append(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "document_id": document_id,
            "batch_id": batch_id,
            "chunk_number": chunk_number,
            "section_number": 1,
            "location_label": "Page 1",
            "text": text,
        }
    )

    return document_id


def make_tutor_override(test_client, fake_database):
    """Use a fake AI provider with the real document retrieval service."""
    provider = MagicMock()
    provider.name = "test-provider"
    provider.generate_response = AsyncMock(
        return_value="Here is your course-based explanation."
    )

    retrieval_service = DocumentRetrievalService(fake_database)
    tutor_service = TutorService(
        provider,
        retrieval_service=retrieval_service,
    )

    from app.main import app

    app.dependency_overrides[get_tutor_service] = (
        lambda: tutor_service
    )

    return provider, tutor_service


def clear_tutor_override():
    from app.main import app

    app.dependency_overrides.pop(get_tutor_service, None)


@pytest.fixture
def rag_client(client):
    test_client, fake_database = client

    try:
        yield test_client, fake_database
    finally:
        clear_tutor_override()


def test_chat_uses_relevant_chunks_from_students_ready_document(
    rag_client,
):
    test_client, fake_database = rag_client

    headers, user_id = create_student(
        test_client,
        fake_database,
        "rag-student@example.com",
        "RAG Student",
    )
    conversation_id = create_conversation(test_client, headers)

    add_document(
        fake_database,
        user_id=user_id,
        status="ready",
        batch_id="active-batch",
        text=(
            "Photosynthesis converts light energy into chemical energy "
            "using chlorophyll in plant cells."
        ),
    )

    provider, _ = make_tutor_override(test_client, fake_database)

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain photosynthesis",
        },
    )

    assert response.status_code == 200
    assert response.json()["response"] == (
        "Here is your course-based explanation."
    )

    provider.generate_response.assert_awaited_once()
    prompt = provider.generate_response.await_args.args[0]

    assert "Photosynthesis converts light energy" in prompt
    assert "UPLOADED COURSE MATERIAL" in prompt
    assert "Explain photosynthesis" in prompt


def test_chat_retrieval_excludes_unready_documents_and_stale_batches(
    rag_client,
):
    test_client, fake_database = rag_client

    headers, user_id = create_student(
        test_client,
        fake_database,
        "rag-status@example.com",
        "Status Student",
    )
    conversation_id = create_conversation(test_client, headers)

    # A ready document with an active batch should be retrieved.
    add_document(
        fake_database,
        user_id=user_id,
        status="ready",
        batch_id="current-batch",
        text="Binary search repeatedly halves a sorted search space.",
        chunk_number=1,
    )

    # A stale batch belonging to the same ready document must be ignored.
    add_document(
        fake_database,
        user_id=user_id,
        status="ready",
        batch_id="old-batch",
        text="STALE_SECRET_CONTENT should never reach the tutor.",
        chunk_number=2,
    )

    # A processing document must not be retrieved.
    add_document(
        fake_database,
        user_id=user_id,
        status="processing",
        batch_id="processing-batch",
        text="PROCESSING_SECRET_CONTENT should never reach the tutor.",
        chunk_number=3,
    )

    # Correct the active batch on the ready document to distinguish it
    # from the deliberately inserted stale chunk.
    ready_document = next(
        document
        for document in fake_database.documents.documents
        if document["user_id"] == user_id
        and document["status"] == "ready"
        and document["active_chunk_batch_id"] == "current-batch"
    )
    ready_document["active_chunk_batch_id"] = "current-batch"

    provider, _ = make_tutor_override(test_client, fake_database)

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain binary search",
        },
    )

    assert response.status_code == 200

    prompt = provider.generate_response.await_args.args[0]

    assert "Binary search repeatedly halves" in prompt
    assert "STALE_SECRET_CONTENT" not in prompt
    assert "PROCESSING_SECRET_CONTENT" not in prompt


def test_chat_never_retrieves_another_students_document(
    rag_client,
):
    test_client, fake_database = rag_client

    first_headers, first_user_id = create_student(
        test_client,
        fake_database,
        "rag-first@example.com",
        "First Student",
    )
    second_headers, second_user_id = create_student(
        test_client,
        fake_database,
        "rag-second@example.com",
        "Second Student",
    )

    assert first_user_id != second_user_id

    add_document(
        fake_database,
        user_id=first_user_id,
        status="ready",
        batch_id="first-batch",
        text=(
            "PRIVATE_FIRST_STUDENT_CONTENT: neural networks use "
            "interconnected computational units."
        ),
    )

    second_conversation_id = create_conversation(
        test_client,
        second_headers,
    )

    provider, _ = make_tutor_override(test_client, fake_database)

    response = test_client.post(
        "/api/chat",
        headers=second_headers,
        json={
            "conversation_id": second_conversation_id,
            "message": "Explain neural networks",
        },
    )

    assert response.status_code == 200

    prompt = provider.generate_response.await_args.args[0]

    assert "PRIVATE_FIRST_STUDENT_CONTENT" not in prompt
    assert "neural networks use interconnected" not in prompt
