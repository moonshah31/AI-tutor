
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.document import DocumentDocument
from app.schemas.document import DocumentResponse
from app.storage.base import FileStorage


class DocumentService:
    """Handles document metadata, storage, and ownership rules."""

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        storage: FileStorage,
    ) -> None:
        self._database = database
        self._storage = storage

    async def create(
        self,
        *,
        user_id: ObjectId,
        file,
        original_filename: str,
        content_type: str,
        file_extension: str,
        file_size: int,
    ) -> DocumentResponse:
        """Store the uploaded file and persist its metadata."""

        storage_reference = self._build_storage_reference(
            user_id=user_id,
            file_extension=file_extension,
        )

        await self._storage.save(
            file=file,
            storage_reference=storage_reference,
        )

        try:
            return await self.create_metadata(
                user_id=user_id,
                original_filename=original_filename,
                content_type=content_type,
                file_extension=file_extension,
                file_size=file_size,
                storage_reference=storage_reference,
            )
        except Exception:
            try:
                await self._storage.delete(
                    storage_reference=storage_reference,
                )
            except Exception:
                # Preserve the original database error while logging
                # a possible orphaned-file cleanup failure.
                import logging

                logging.getLogger(__name__).exception(
                    "Failed to clean up file after metadata creation failed"
                )
            raise

    async def create_metadata(
        self,
        *,
        user_id: ObjectId,
        original_filename: str,
        content_type: str,
        file_extension: str,
        file_size: int,
        storage_reference: str,
    ) -> DocumentResponse:
        now = datetime.now(UTC)

        document = {
            "user_id": user_id,
            "original_filename": original_filename,
            "stored_filename": Path(storage_reference).name,
            "content_type": content_type,
            "file_extension": file_extension,
            "file_size": file_size,
            "storage_reference": storage_reference,
            "status": "uploaded",
            "processing_error": None,
            "sections": [],
            "created_at": now,
            "updated_at": now,
        }

        result = await self._database.documents.insert_one(document)

        saved_document: DocumentDocument = {
            "_id": result.inserted_id,
            **document,
        }

        return self._to_response(saved_document)

    async def list_for_user(
        self,
        *,
        user_id: ObjectId,
    ) -> list[DocumentResponse]:
        cursor = (
            self._database.documents
            .find(
                {
                    "user_id": user_id,
                    "status": {"$ne": "deleting"},
                },
                {
                    "original_filename": 1,
                    "content_type": 1,
                    "file_extension": 1,
                    "file_size": 1,
                    "status": 1,
                    "processing_error": 1,
                    "created_at": 1,
                    "updated_at": 1,
                },
            )
            .sort("updated_at", -1)
        )

        documents: list[DocumentResponse] = []

        async for document in cursor:
            documents.append(self._to_response(document))

        return documents

    async def get_for_user(
        self,
        *,
        user_id: ObjectId,
        document_id: str,
    ) -> DocumentResponse:
        document = await self._find_owned_document(
            user_id=user_id,
            document_id=document_id,
        )

        if document.get("status") == "deleting":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return self._to_response(document)

    async def delete(
        self,
        *,
        user_id: ObjectId,
        document_id: str,
    ) -> None:
        document = await self._find_owned_document(
            user_id=user_id,
            document_id=document_id,
        )

        stored_id = document["_id"]

        # Persist the deletion state first. If cleanup fails, metadata
        # remains available so the same operation can be retried.
        result = await self._database.documents.update_one(
            {
                "_id": stored_id,
                "user_id": user_id,
            },
            {
                "$set": {
                    "status": "deleting",
                    "updated_at": datetime.now(UTC),
                }
            },
        )

        if result.matched_count != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        # Delete all batches, not just the active one.
        await self._database.document_chunks.delete_many(
            {
                "document_id": stored_id,
                "user_id": user_id,
            }
        )

        # A missing file is acceptable for retryable cleanup.
        await self._storage.delete(
            storage_reference=document["storage_reference"],
        )

        # Remove metadata last so failed storage cleanup is recoverable.
        await self._database.documents.delete_one(
            {
                "_id": stored_id,
                "user_id": user_id,
                "status": "deleting",
            }
        )

    async def _find_owned_document(
        self,
        *,
        user_id: ObjectId,
        document_id: str,
    ) -> DocumentDocument:
        if not ObjectId.is_valid(document_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        document = await self._database.documents.find_one(
            {
                "_id": ObjectId(document_id),
                "user_id": user_id,
            }
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return document

    @staticmethod
    def _build_storage_reference(
        *,
        user_id: ObjectId,
        file_extension: str,
    ) -> str:
        """Build a server-controlled path, never using the original filename."""

        generated_filename = f"{uuid4().hex}{file_extension}"
        return f"{user_id}/{generated_filename}"

    @staticmethod
    def _to_response(
        document: DocumentDocument,
    ) -> DocumentResponse:
        return DocumentResponse(
            id=str(document["_id"]),
            original_filename=document["original_filename"],
            content_type=document["content_type"],
            file_extension=document["file_extension"],
            file_size=document["file_size"],
            status=document["status"],
            processing_error=document.get("processing_error"),
            section_count=len(document.get("sections", [])),
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )
