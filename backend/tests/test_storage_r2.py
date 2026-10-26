import asyncio
import io
import threading
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from bson import ObjectId

from app.config import Settings
from app.services.document_service import DocumentService
from app.storage import factory
from app.storage.local import LocalFileStorage
from app.storage.r2 import R2FileStorage


def storage_reference(extension: str = ".pdf") -> str:
    return f"{ObjectId()}/{uuid4().hex}{extension}"


class FakeProviderError(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_upload = False
        self.head_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.upload_calls: list[tuple[str, str]] = []
        self.delete_calls: list[tuple[str, str]] = []

    def upload_fileobj(self, file, bucket: str, key: str) -> None:
        self.upload_calls.append((bucket, key))
        self.objects[(bucket, key)] = file.read()
        if self.fail_upload:
            raise RuntimeError("upload failed")

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        if self.head_error:
            raise self.head_error
        if (Bucket, Key) not in self.objects:
            raise FakeProviderError("NoSuchKey")
        return {}

    def delete_object(self, *, Bucket: str, Key: str) -> dict:
        self.delete_calls.append((Bucket, Key))
        if self.delete_error:
            raise self.delete_error
        self.objects.pop((Bucket, Key), None)
        return {}


def make_storage(client: FakeS3Client) -> R2FileStorage:
    return R2FileStorage(
        endpoint_url="https://example.r2.cloudflarestorage.com",
        bucket="private-documents",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
        client=client,
    )


def test_r2_storage_saves_reads_checks_and_retries_delete() -> None:
    client = FakeS3Client()
    storage = make_storage(client)
    reference = storage_reference(".txt")

    asyncio.run(
        storage.save(
            file=io.BytesIO(b"lecture notes"),
            storage_reference=reference,
        )
    )

    assert client.upload_calls == [("private-documents", reference)]
    assert asyncio.run(storage.exists(storage_reference=reference)) is True
    assert asyncio.run(storage.read(storage_reference=reference)) == b"lecture notes"

    asyncio.run(storage.delete(storage_reference=reference))
    asyncio.run(storage.delete(storage_reference=reference))

    assert client.delete_calls == [
        ("private-documents", reference),
        ("private-documents", reference),
    ]
    assert asyncio.run(storage.exists(storage_reference=reference)) is False


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "/etc/passwd",
        "../notes.pdf",
        "507f1f77bcf86cd799439011/../notes.pdf",
        "507f1f77bcf86cd799439011\\notes.pdf",
        "507f1f77bcf86cd799439011/lecture.pdf",
        f"{ObjectId()}/{uuid4().hex}.exe",
    ],
)
def test_r2_storage_rejects_unsafe_or_unexpected_references(
    reference: str,
) -> None:
    storage = make_storage(FakeS3Client())

    with pytest.raises(ValueError, match="Invalid document storage reference"):
        asyncio.run(storage.exists(storage_reference=reference))


def test_r2_exists_returns_false_only_for_missing_object() -> None:
    client = FakeS3Client()
    storage = make_storage(client)
    reference = storage_reference()

    client.head_error = FakeProviderError("NoSuchKey")
    assert asyncio.run(storage.exists(storage_reference=reference)) is False

    client.head_error = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )
    assert asyncio.run(storage.exists(storage_reference=reference)) is False

    client.head_error = RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(storage.exists(storage_reference=reference))


def test_r2_delete_propagates_provider_errors() -> None:
    client = FakeS3Client()
    client.delete_error = RuntimeError("provider unavailable")
    storage = make_storage(client)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(storage.delete(storage_reference=storage_reference()))


def test_r2_cancelled_upload_waits_then_removes_completed_object() -> None:
    client = FakeS3Client()
    upload_started = threading.Event()
    finish_upload = threading.Event()
    original_upload = client.upload_fileobj

    def blocked_upload(file, bucket: str, key: str) -> None:
        upload_started.set()
        finish_upload.wait()
        original_upload(file, bucket, key)

    client.upload_fileobj = blocked_upload
    storage = make_storage(client)
    reference = storage_reference()

    async def run_cancelled_upload() -> None:
        upload_task = asyncio.create_task(
            storage.save(
                file=io.BytesIO(b"lecture content"),
                storage_reference=reference,
            )
        )
        started = await asyncio.to_thread(upload_started.wait, 5)
        assert started, "upload worker did not start"

        upload_task.cancel()
        # The cancellation wake-up is queued before this callback, so the
        # worker remains blocked until save() has entered its cancellation path.
        asyncio.get_running_loop().call_soon(finish_upload.set)

        with pytest.raises(asyncio.CancelledError):
            await upload_task

    try:
        asyncio.run(run_cancelled_upload())
    finally:
        finish_upload.set()

    assert ("private-documents", reference) not in client.objects
    assert client.delete_calls == [("private-documents", reference)]


def test_document_service_removes_partial_r2_object_after_save_failure(client) -> None:
    _, fake_database = client
    s3_client = FakeS3Client()
    s3_client.fail_upload = True
    storage = make_storage(s3_client)
    service = DocumentService(database=fake_database, storage=storage)

    with pytest.raises(RuntimeError, match="upload failed"):
        asyncio.run(
            service.create(
                user_id=ObjectId(),
                file=io.BytesIO(b"partial upload"),
                original_filename="lecture.pdf",
                content_type="application/pdf",
                file_extension=".pdf",
                file_size=len(b"partial upload"),
            )
        )

    assert s3_client.objects == {}


def test_storage_factory_defaults_to_local(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        mongodb_uri="mongodb://localhost",
        jwt_secret_key="test-secret-that-is-long-enough-for-tests-only",
        document_storage_path=str(tmp_path),
    )

    storage = factory.create_file_storage(settings)

    assert settings.document_storage_backend == "local"
    assert isinstance(storage, LocalFileStorage)


def test_storage_factory_requires_r2_configuration() -> None:
    settings = Settings(
        _env_file=None,
        mongodb_uri="mongodb://localhost",
        jwt_secret_key="test-secret-that-is-long-enough-for-tests-only",
        document_storage_backend="r2",
    )

    with pytest.raises(ValueError, match="R2 storage requires"):
        factory.create_file_storage(settings)


def test_storage_factory_selects_configured_r2(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        mongodb_uri="mongodb://localhost",
        jwt_secret_key="test-secret-that-is-long-enough-for-tests-only",
        document_storage_backend="r2",
        r2_endpoint_url="https://example.r2.cloudflarestorage.com",
        r2_bucket="private-documents",
        r2_access_key_id="test-access-key",
        r2_secret_access_key="test-secret-key",
    )
    constructed: dict = {}

    class R2StorageStub:
        def __init__(self, **kwargs) -> None:
            constructed.update(kwargs)

    monkeypatch.setattr(factory, "R2FileStorage", R2StorageStub)

    storage = factory.create_file_storage(settings)

    assert isinstance(storage, R2StorageStub)
    assert constructed == {
        "endpoint_url": settings.r2_endpoint_url,
        "bucket": settings.r2_bucket,
        "access_key_id": settings.r2_access_key_id,
        "secret_access_key": settings.r2_secret_access_key,
    }
