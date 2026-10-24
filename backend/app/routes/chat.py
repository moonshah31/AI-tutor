import logging
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.document_retrieval_service import (
    DocumentRetrievalService,
)
from app.config import Settings, get_settings
from app.database import get_database
from app.dependencies import get_current_user
from app.providers.base import AIProviderError
from app.providers.gemini import GeminiProvider
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationMessage,
    TutorRequest,
)
from app.services.conversation_service import ConversationService
from app.services.tutor_service import TutorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tutor"])


def get_tutor_service(
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[
        AsyncIOMotorDatabase,
        Depends(get_database),
    ],
) -> TutorService:
    provider = GeminiProvider(settings)
    retrieval_service = DocumentRetrievalService(database)

    return TutorService(
        provider,
        retrieval_service=retrieval_service,
    )


def get_conversation_service(
    database: Annotated[
        AsyncIOMotorDatabase,
        Depends(get_database),
    ],
) -> ConversationService:
    return ConversationService(database)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    tutor_service: Annotated[
        TutorService,
        Depends(get_tutor_service),
    ],
    conversation_service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> ChatResponse:
    user_id: ObjectId = current_user["_id"]

    try:
        # MongoDB is the authoritative source of conversation history.
        conversation = await conversation_service.get_for_user(
            user_id=user_id,
            conversation_id=payload.conversation_id,
        )

        # Give the tutor the existing conversation context.
        context = [
            ConversationMessage(
                role=message.role,
                content=message.content,
            )
            for message in conversation.messages[-10:]
        ]

        tutor_request = TutorRequest(
            message=payload.message,
            messages=context,
        )

        # Generate the response BEFORE persisting the new turn.
        # This prevents failed provider requests from leaving
        # orphaned user messages in the conversation.
        response = await tutor_service.reply(
            current_user=current_user,
            request=tutor_request,
        )

        # Only persist the turn after the AI provider succeeds.
        await conversation_service.add_message(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="user",
            content=payload.message,
        )

        await conversation_service.add_message(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="assistant",
            content=response.response,
        )

        return response

    except AIProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The tutor is temporarily unavailable. "
                "Please try again shortly."
            ),
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Unexpected tutor service failure: %s",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The tutor could not complete that request. "
                "Please try again."
            ),
        ) from error