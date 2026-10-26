import asyncio
import re
from typing import Any, BinaryIO

from app.constants.document import ALLOWED_DOCUMENT_EXTENSIONS
from app.storage.base import FileStorage


_REFERENCE_PATTERN = re.compile(
    r"(?P<user_id>[0-9a-f]{24})/(?P<filename>[0-9a-f]{32}\.[a-z0-9]+)"
)
_MISSING_OBJECT_CODES = {"404", "NoSuchKey", "NotFound"}


class R2FileStorage(FileStorage):
    """Private object storage backed by Cloudflare R2's S3-compatible API."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        client: Any | None = None,
    ) -> None:
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name="auto",
            )

        self._client = client
        self._bucket = bucket

    async def save(
        self,
        *,
        file: BinaryIO,
        storage_reference: str,
    ) -> None:
        key = self._validate_reference(storage_reference)
        upload = asyncio.create_task(
            asyncio.to_thread(
                self._client.upload_fileobj,
                file,
                self._bucket,
                key,
            )
        )
        try:
            await asyncio.shield(upload)
        except asyncio.CancelledError:
            # Cancelling to_thread's await does not stop the SDK worker. Wait
            # for it to settle before deleting, or a late upload could recreate
            # the object after cleanup.
            while not upload.done():
                try:
                    await asyncio.shield(upload)
                except asyncio.CancelledError:
                    # A repeated cancellation must not let cleanup race the
                    # still-running SDK worker either.
                    continue
                except BaseException:
                    break

            cleanup = asyncio.create_task(
                asyncio.to_thread(
                    self._client.delete_object,
                    Bucket=self._bucket,
                    Key=key,
                )
            )
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
                except BaseException:
                    break
            raise

    async def read(
        self,
        *,
        storage_reference: str,
    ) -> bytes:
        key = self._validate_reference(storage_reference)

        def read_object() -> bytes:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()

        return await asyncio.to_thread(read_object)

    async def delete(
        self,
        *,
        storage_reference: str,
    ) -> None:
        key = self._validate_reference(storage_reference)
        # S3 DeleteObject is idempotent for a missing key; other errors
        # propagate so document cleanup can be retried.
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=key,
        )

    async def exists(
        self,
        *,
        storage_reference: str,
    ) -> bool:
        key = self._validate_reference(storage_reference)

        try:
            await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
        except Exception as error:
            response = getattr(error, "response", None)
            error_details = (
                response.get("Error", {})
                if isinstance(response, dict)
                else {}
            )
            if error_details.get("Code") in _MISSING_OBJECT_CODES:
                return False
            raise

        return True

    @staticmethod
    def _validate_reference(storage_reference: str) -> str:
        match = _REFERENCE_PATTERN.fullmatch(storage_reference)
        if (
            match is None
            or "." + match.group("filename").rsplit(".", 1)[1]
            not in ALLOWED_DOCUMENT_EXTENSIONS
        ):
            raise ValueError("Invalid document storage reference")

        return storage_reference
