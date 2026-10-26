
from abc import ABC, abstractmethod
from typing import BinaryIO


class FileStorage(ABC):
    """Abstract interface for application file storage."""

    @abstractmethod
    async def save(
        self,
        *,
        file: BinaryIO,
        storage_reference: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def read(
        self,
        *,
        storage_reference: str,
    ) -> bytes:
        """Read a stored file's contents."""
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        *,
        storage_reference: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def exists(
        self,
        *,
        storage_reference: str,
    ) -> bool:
        raise NotImplementedError
