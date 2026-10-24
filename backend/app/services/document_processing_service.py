
import asyncio
import io
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.chunking.text_chunker import TextChunker
from app.extractors.factory import get_extractor
from app.models.document_chunk import DocumentChunk
from app.models.extracted_document import DocumentSection
from app.services.embedding_service import EmbeddingService
from app.storage.base import FileStorage


logger = logging.getLogger(__name__)
class EmbeddingServiceProtocol(Protocol):
    """Interface required by document processing."""

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

class DocumentProcessingService:
    """Extract documents, embed chunks, and safely replace retrieval data."""

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        storage: FileStorage,
        chunker: TextChunker | None = None,
        embedding_service: EmbeddingServiceProtocol | None = None,
    ) -> None:
        self._database = database
        self._storage = storage
        self._chunker = chunker or TextChunker()
        self._embedding_service = (
            embedding_service or EmbeddingService()
        )

    async def process(
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
        previous_status = document.get("status", "uploaded")
        has_active_batch = (
            document.get("active_chunk_batch_id") is not None
        )
        processing_token = ObjectId()

        # Do not process documents being deleted. Claim processing
        # with a conditional update so concurrent requests cannot
        # both start processing the same document.
        if previous_status == "deleting":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is being deleted",
            )

        claim = await self._database.documents.update_one(
            {
                "_id": stored_id,
                "user_id": user_id,
                "status": previous_status,
                "processing_token": document.get("processing_token"),
            },
            {
                "$set": {
                    "processing_token": processing_token,
                    "processing_error": None,
                    "updated_at": datetime.now(UTC),
                    **(
                        {}
                        if has_active_batch
                        else {"status": "processing"}
                    ),
                }
            },
        )

        if claim.matched_count != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is already being processed or deleted",
            )

        expected_status = (
            previous_status if has_active_batch else "processing"
        )

        new_batch_id = ObjectId()
        activated = False

        try:
            file_contents = await self._storage.read(
                storage_reference=document["storage_reference"],
            )

            extractor = get_extractor(document["file_extension"])
            sections: list[DocumentSection] = extractor.extract(
                io.BytesIO(file_contents)
            )
            chunks: list[DocumentChunk] = self._chunker.chunk(sections)

            # Generate embeddings before inserting or activating the
            # batch. A failure leaves the previous active batch untouched.
            chunk_texts = [chunk["text"] for chunk in chunks]

            if chunk_texts:
                embeddings = await asyncio.to_thread(
                    self._embedding_service.embed_texts,
                    chunk_texts,
                )

                if len(embeddings) != len(chunks):
                    raise RuntimeError(
                        "Embedding count does not match chunk count"
                    )

                staged_chunks = [
                    {
                        "document_id": stored_id,
                        "user_id": user_id,
                        "batch_id": new_batch_id,
                        **chunk,
                        "embedding": embedding,
                    }
                    for chunk, embedding in zip(
                        chunks,
                        embeddings,
                        strict=True,
                    )
                ]

                # Stage the complete batch without removing the active one.
                await self._database.document_chunks.insert_many(
                    staged_chunks
                )

            # Activate only if this request still owns the processing
            # claim and the document has not entered deletion.
            await self._set_ready(
                document_id=stored_id,
                user_id=user_id,
                sections=sections,
                batch_id=new_batch_id,
                processing_token=processing_token,
                expected_status=expected_status,
            )
            activated = True

        except Exception:
            if not activated:
                # Only remove the batch created by this processing attempt.
                try:
                    await self._database.document_chunks.delete_many(
                        {
                            "document_id": stored_id,
                            "user_id": user_id,
                            "batch_id": new_batch_id,
                        }
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up staged document chunks"
                    )

                # Do not overwrite a concurrent deletion or another
                # state transition when reporting processing failure.
                try:
                    await self._set_failed(
                        document_id=stored_id,
                        user_id=user_id,
                        processing_token=processing_token,
                        expected_status=expected_status,
                        error=(
                            "Reprocessing failed; the previous version "
                            "remains available"
                            if has_active_batch
                            else "Document processing failed"
                        ),
                        preserve_ready=has_active_batch,
                    )
                except Exception:
                    logger.exception(
                        "Failed to update document processing status"
                    )

            raise

        # The new batch is active. Remove older batches afterward.
        try:
            await self._database.document_chunks.delete_many(
                {
                    "document_id": stored_id,
                    "user_id": user_id,
                    "batch_id": {"$ne": new_batch_id},
                }
            )
        except Exception:
            logger.exception(
                "Document was processed, but old chunk cleanup failed"
            )

    async def _set_ready(
        self,
        *,
        document_id: ObjectId,
        user_id: ObjectId,
        sections: list[DocumentSection],
        batch_id: ObjectId,
        processing_token: ObjectId,
        expected_status: str,
    ) -> None:
        result = await self._database.documents.update_one(
            {
                "_id": document_id,
                "user_id": user_id,
                "status": expected_status,
                "processing_token": processing_token,
            },
            {
                "$set": {
                    "status": "ready",
                    "processing_error": None,
                    "sections": sections,
                    "active_chunk_batch_id": batch_id,
                    "processing_token": None,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

        if result.matched_count != 1:
            raise RuntimeError(
                "Document could not be activated; "
                "it may have been deleted or its processing claim changed"
            )

    async def _set_failed(
        self,
        *,
        document_id: ObjectId,
        user_id: ObjectId,
        processing_token: ObjectId,
        expected_status: str,
        error: str,
        preserve_ready: bool = False,
    ) -> None:
        await self._database.documents.update_one(
            {
                "_id": document_id,
                "user_id": user_id,
                "status": expected_status,
                "processing_token": processing_token,
            },
            {
                "$set": {
                    "status": "ready" if preserve_ready else "failed",
                    "processing_error": error,
                    "processing_token": None,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    async def _find_owned_document(
        self,
        *,
        user_id: ObjectId,
        document_id: str,
    ) -> dict[str, Any]:
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
