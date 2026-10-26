import io

from app.main import app
from app.routes.document import get_document_service
from app.services.document_service import DocumentService
from app.storage.base import FileStorage

from test_auth import register

from app.routes.document import (
    get_document_processing_service,
    get_document_service,
)
import pytest

@pytest.fixture(autouse=True)
def override_document_processing_service():
    app.dependency_overrides[
        get_document_processing_service
    ] = FakeDocumentProcessingService

    yield

    app.dependency_overrides.pop(
        get_document_processing_service,
        None,
    )
class FakeStorage(FileStorage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.fail_on_save = False
        self.fail_on_delete = False
        self.deleted_references: list[str] = []

    async def read(self, *, storage_reference: str) -> bytes:
        if storage_reference not in self.files:
            raise FileNotFoundError(storage_reference)
        return self.files[storage_reference]

    async def save(
        self,
        *,
        file,
        storage_reference: str,
    ) -> None:
        if self.fail_on_save:
            raise RuntimeError("storage failure")

        self.files[storage_reference] = file.read()

    async def delete(
        self,
        *,
        storage_reference: str,
    ) -> None:
        self.deleted_references.append(storage_reference)

        if self.fail_on_delete:
            raise RuntimeError("storage deletion failure")

        self.files.pop(storage_reference, None)

    async def exists(
        self,
        *,
        storage_reference: str,
    ) -> bool:
        return storage_reference in self.files

class FakeDocumentProcessingService:
    """Keep document-management tests independent of PDF extraction."""

    async def process(
        self,
        *,
        user_id,
        document_id: str,
    ) -> None:
        return None


def auth_header(test_client, email="student@example.com"):
    if email == "student@example.com":
        register(test_client)

        password = "StrongPass123!"
        name = "Test Student"
    else:
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Second Student",
                "email": email,
                "password": "StrongPass123!",
            },
        )
        password = "StrongPass123!"
        name = "Second Student"

    login = test_client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login.json()['access_token']}"
        )
    }


def test_upload_valid_pdf(client):
    test_client, _ = client

    headers = auth_header(test_client)

    response = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "lecture.pdf",
                io.BytesIO(b"%PDF-1.4 fake pdf content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    document = response.json()

    assert document["original_filename"] == "lecture.pdf"
    assert document["content_type"] == "application/pdf"
    assert document["file_extension"] == ".pdf"
    assert document["file_size"] == len(b"%PDF-1.4 fake pdf content")
    assert document["status"] == "uploaded"
    assert document["processing_error"] is None


def test_upload_rejects_unsupported_extension(client):
    test_client, _ = client

    headers = auth_header(test_client)

    response = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "malware.exe",
                io.BytesIO(b"not a document"),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported document type"


def test_upload_rejects_mismatched_content_type(client):
    test_client, _ = client

    headers = auth_header(test_client)

    response = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "lecture.pdf",
                io.BytesIO(b"%PDF-1.4 fake pdf content"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "File content type does not match the selected document type"
    )


def test_upload_requires_authentication(client):
    test_client, _ = client

    response = test_client.post(
        "/api/documents",
        files={
            "file": (
                "lecture.pdf",
                io.BytesIO(b"%PDF-1.4 fake pdf content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 401


def test_list_documents_returns_only_current_users_documents(client):
    test_client, _ = client

    first_headers = auth_header(test_client)

    first_upload = test_client.post(
        "/api/documents",
        headers=first_headers,
        files={
            "file": (
                "first.pdf",
                io.BytesIO(b"first document"),
                "application/pdf",
            )
        },
    )

    assert first_upload.status_code == 201

    second_headers = auth_header(
        test_client,
        email="second@example.com",
    )

    second_upload = test_client.post(
        "/api/documents",
        headers=second_headers,
        files={
            "file": (
                "second.pdf",
                io.BytesIO(b"second document"),
                "application/pdf",
            )
        },
    )

    assert second_upload.status_code == 201

    response = test_client.get(
        "/api/documents",
        headers=first_headers,
    )

    assert response.status_code == 200

    documents = response.json()

    assert len(documents) == 1
    assert documents[0]["original_filename"] == "first.pdf"


def test_delete_own_document(client):
    test_client, _ = client

    headers = auth_header(test_client)

    upload = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "lecture.pdf",
                io.BytesIO(b"lecture content"),
                "application/pdf",
            )
        },
    )

    document_id = upload.json()["id"]

    response = test_client.delete(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 204

    documents = test_client.get(
        "/api/documents",
        headers=headers,
    )

    assert documents.status_code == 200
    assert documents.json() == []


def test_user_cannot_delete_another_users_document(client):
    test_client, _ = client

    first_headers = auth_header(test_client)

    upload = test_client.post(
        "/api/documents",
        headers=first_headers,
        files={
            "file": (
                "private.pdf",
                io.BytesIO(b"private content"),
                "application/pdf",
            )
        },
    )

    document_id = upload.json()["id"]

    second_headers = auth_header(
        test_client,
        email="second@example.com",
    )

    response = test_client.delete(
        f"/api/documents/{document_id}",
        headers=second_headers,
    )

    assert response.status_code == 404

    # Original owner still has the document.
    documents = test_client.get(
        "/api/documents",
        headers=first_headers,
    )

    assert documents.status_code == 200
    assert len(documents.json()) == 1


def test_upload_rejects_file_larger_than_configured_limit(client, monkeypatch):
    test_client, _ = client

    headers = auth_header(test_client)

    from app.config import get_settings

    settings = get_settings()

    monkeypatch.setattr(
        settings,
        "max_document_size_mb",
        1,
    )

    oversized_content = b"x" * (1024 * 1024 + 1)

    response = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "large.txt",
                io.BytesIO(oversized_content),
                "text/plain",
            )
        },
    )

    assert response.status_code == 413
    assert "maximum allowed size" in response.json()["detail"]


def test_document_service_rolls_back_file_when_database_insert_fails(
    client,
):
    test_client, fake_database = client

    headers = auth_header(test_client)

    storage = FakeStorage()

    service = DocumentService(
        database=fake_database,
        storage=storage,
    )

    async def failing_insert_one(document):
        raise RuntimeError("database failure")

    fake_database.documents.insert_one = failing_insert_one

    import pytest

    with pytest.raises(RuntimeError, match="database failure"):
        awaitable = service.create(
            user_id=next(iter(fake_database.users.documents))["_id"],
            file=io.BytesIO(b"important document"),
            original_filename="important.pdf",
            content_type="application/pdf",
            file_extension=".pdf",
            file_size=len(b"important document"),
        )

        import asyncio

        asyncio.run(awaitable)

    assert storage.files == {}
    assert len(storage.deleted_references) == 1


def test_document_service_cleans_up_after_save_failure(client):
    test_client, fake_database = client
    auth_header(test_client)
    user_id = next(iter(fake_database.users.documents))["_id"]

    class PartiallyFailingStorage(FakeStorage):
        async def save(self, *, file, storage_reference: str) -> None:
            self.files[storage_reference] = file.read()
            raise RuntimeError("upload failed")

    storage = PartiallyFailingStorage()
    service = DocumentService(
        database=fake_database,
        storage=storage,
    )

    with pytest.raises(RuntimeError, match="upload failed"):
        import asyncio

        asyncio.run(
            service.create(
                user_id=user_id,
                file=io.BytesIO(b"partial upload"),
                original_filename="lecture.pdf",
                content_type="application/pdf",
                file_extension=".pdf",
                file_size=len(b"partial upload"),
            )
        )

    assert storage.files == {}
    assert len(storage.deleted_references) == 1


def test_document_service_does_not_mask_save_error_when_cleanup_fails(client):
    test_client, fake_database = client
    auth_header(test_client)
    user_id = next(iter(fake_database.users.documents))["_id"]

    class PartiallyFailingStorage(FakeStorage):
        async def save(self, *, file, storage_reference: str) -> None:
            self.files[storage_reference] = file.read()
            raise RuntimeError("original upload failure")

    storage = PartiallyFailingStorage()
    storage.fail_on_delete = True
    service = DocumentService(
        database=fake_database,
        storage=storage,
    )

    with pytest.raises(RuntimeError, match="original upload failure"):
        import asyncio

        asyncio.run(
            service.create(
                user_id=user_id,
                file=io.BytesIO(b"partial upload"),
                original_filename="lecture.pdf",
                content_type="application/pdf",
                file_extension=".pdf",
                file_size=len(b"partial upload"),
            )
        )

    assert len(storage.deleted_references) == 1


def test_get_own_document(client):
    test_client, _ = client

    headers = auth_header(test_client)

    upload = test_client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "lecture.pdf",
                io.BytesIO(b"lecture content"),
                "application/pdf",
            )
        },
    )

    assert upload.status_code == 201

    document_id = upload.json()["id"]

    response = test_client.get(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == document_id
    assert response.json()["original_filename"] == "lecture.pdf"
    assert response.json()["status"] == "uploaded"


def test_user_cannot_get_another_users_document(client):
    test_client, _ = client

    first_headers = auth_header(test_client)

    upload = test_client.post(
        "/api/documents",
        headers=first_headers,
        files={
            "file": (
                "private.pdf",
                io.BytesIO(b"private content"),
                "application/pdf",
            )
        },
    )

    document_id = upload.json()["id"]

    second_headers = auth_header(
        test_client,
        email="second@example.com",
    )

    response = test_client.get(
        f"/api/documents/{document_id}",
        headers=second_headers,
    )

    assert response.status_code == 404        

    
import asyncio

import pytest
from bson import ObjectId

from app.services.document_service import DocumentService


def test_document_deletion_removes_metadata_file_and_chunks(client):
    _, fake_database = client

    user_id = ObjectId()
    document_id = ObjectId()
    batch_id = ObjectId()
    storage_reference = f"{user_id}/lecture.pdf"

    storage = FakeStorage()
    storage.files[storage_reference] = b"lecture content"

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "original_filename": "lecture.pdf",
            "stored_filename": "lecture.pdf",
            "content_type": "application/pdf",
            "file_extension": ".pdf",
            "file_size": len(b"lecture content"),
            "storage_reference": storage_reference,
            "status": "ready",
            "processing_error": None,
            "sections": [],
            "active_chunk_batch_id": batch_id,
        }
    )

    fake_database.document_chunks.documents.extend(
        [
            {
                "document_id": document_id,
                "user_id": user_id,
                "batch_id": batch_id,
                "text": "Lecture content",
            },
            {
                "document_id": document_id,
                "user_id": user_id,
                "batch_id": ObjectId(),
                "text": "An older chunk batch",
            },
            {
                "document_id": ObjectId(),
                "user_id": user_id,
                "batch_id": ObjectId(),
                "text": "Another document",
            },
        ]
    )

    service = DocumentService(
        database=fake_database,
        storage=storage,
    )

    asyncio.run(
        service.delete(
            user_id=user_id,
            document_id=str(document_id),
        )
    )

    assert not any(
        document["_id"] == document_id
        for document in fake_database.documents.documents
    )
    assert storage_reference not in storage.files

    # Both active and old batches for this document are removed.
    assert not any(
        chunk["document_id"] == document_id
        and chunk["user_id"] == user_id
        for chunk in fake_database.document_chunks.documents
    )

    # Unrelated documents' chunks remain untouched.
    assert len(fake_database.document_chunks.documents) == 1


def test_document_deletion_can_be_retried_after_storage_failure(client):
    _, fake_database = client

    user_id = ObjectId()
    document_id = ObjectId()
    storage_reference = f"{user_id}/lecture.pdf"

    storage = FakeStorage()
    storage.files[storage_reference] = b"lecture content"
    storage.fail_on_delete = True

    fake_database.documents.documents.append(
        {
            "_id": document_id,
            "user_id": user_id,
            "original_filename": "lecture.pdf",
            "stored_filename": "lecture.pdf",
            "content_type": "application/pdf",
            "file_extension": ".pdf",
            "file_size": len(b"lecture content"),
            "storage_reference": storage_reference,
            "status": "ready",
            "processing_error": None,
            "sections": [],
        }
    )

    fake_database.document_chunks.documents.append(
        {
            "document_id": document_id,
            "user_id": user_id,
            "batch_id": ObjectId(),
            "text": "Lecture content",
        }
    )

    service = DocumentService(
        database=fake_database,
        storage=storage,
    )

    with pytest.raises(
        RuntimeError,
        match="storage deletion failure",
    ):
        asyncio.run(
            service.delete(
                user_id=user_id,
                document_id=str(document_id),
            )
        )

    # Metadata remains so a retry can locate the original file.
    document = next(
        document
        for document in fake_database.documents.documents
        if document["_id"] == document_id
    )
    assert document["status"] == "deleting"

    # The file still exists because the simulated deletion failed.
    assert storage_reference in storage.files

    # The document's chunks have already been removed.
    assert not any(
        chunk["document_id"] == document_id
        and chunk["user_id"] == user_id
        for chunk in fake_database.document_chunks.documents
    )

    # Retry after the storage problem is resolved.
    storage.fail_on_delete = False

    asyncio.run(
        service.delete(
            user_id=user_id,
            document_id=str(document_id),
        )
    )

    assert not any(
        document["_id"] == document_id
        for document in fake_database.documents.documents
    )
    assert storage_reference not in storage.files
