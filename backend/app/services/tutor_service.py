
from typing import Any

from bson import ObjectId

from app.prompts.tutor import build_tutor_prompt
from app.providers.base import AIProvider
from app.schemas.chat import ChatResponse, TutorRequest
from app.services.document_retrieval_service import (
    DocumentRetrievalService,
)


class TutorService:
    """Orchestrates tutoring and optional document retrieval."""

    def __init__(
        self,
        provider: AIProvider,
        retrieval_service: DocumentRetrievalService | None = None,
    ) -> None:
        self._provider = provider
        self._retrieval_service = retrieval_service

    async def reply(
        self,
        *,
        current_user: dict[str, Any],
        request: TutorRequest,
    ) -> ChatResponse:
        retrieved_chunks: list[dict[str, Any]] = []

        if self._retrieval_service is not None:
            user_id = current_user.get("_id")

            if not isinstance(user_id, ObjectId):
                raise ValueError(
                    "An authenticated user ID is required for retrieval."
                )

            retrieved_chunks = await self._retrieval_service.search(
                user_id=user_id,
                query=request.message,
                limit=5,
            )

        prompt = build_tutor_prompt(
            student_name=current_user.get("name", "Student"),
            message=request.message,
            context=request.messages,
            retrieved_chunks=retrieved_chunks,
        )

        response = await self._provider.generate_response(prompt)

        return ChatResponse(
            response=response.strip(),
            provider=self._provider.name,
        )
