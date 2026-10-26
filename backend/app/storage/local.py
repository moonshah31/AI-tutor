
import asyncio
from pathlib import Path
from typing import BinaryIO

from app.storage.base import FileStorage


class LocalFileStorage(FileStorage):
    """Stores uploaded files on the local application filesystem."""

    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()
        self._base_path.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def save(
        self,
        *,
        file: BinaryIO,
        storage_reference: str,
    ) -> None:
        destination = self._safe_path(storage_reference)
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        def write_file() -> None:
            with destination.open("wb") as output:
                while chunk := file.read(1024 * 1024):
                    output.write(chunk)

        await asyncio.to_thread(write_file)

    async def read(
        self,
        *,
        storage_reference: str,
    ) -> bytes:
        path = self._safe_path(storage_reference)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(
        self,
        *,
        storage_reference: str,
    ) -> None:
        path = self._safe_path(storage_reference)

        if path.exists():
            await asyncio.to_thread(path.unlink)

    async def exists(
        self,
        *,
        storage_reference: str,
    ) -> bool:
        path = self._safe_path(storage_reference)
        return await asyncio.to_thread(path.is_file)

    def _safe_path(
        self,
        storage_reference: str,
    ) -> Path:
        candidate = (
            self._base_path / storage_reference
        ).resolve()

        if (
            candidate != self._base_path
            and self._base_path not in candidate.parents
        ):
            raise ValueError("Invalid storage reference")

        return candidate
