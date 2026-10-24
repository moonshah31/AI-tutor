from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    ConversationUpdate,
)
from app.services.conversation_service import ConversationService


router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
)


def get_conversation_service(
    database: Annotated[
        AsyncIOMotorDatabase,
        Depends(get_database),
    ],
) -> ConversationService:
    return ConversationService(database)


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> ConversationResponse:
    return await service.create(
        user_id=current_user["_id"],
        payload=payload,
    )


@router.get(
    "",
    response_model=list[ConversationSummary],
)
async def list_conversations(
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> list[ConversationSummary]:
    return await service.list_for_user(
        user_id=current_user["_id"],
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> ConversationResponse:
    return await service.get_for_user(
        user_id=current_user["_id"],
        conversation_id=conversation_id,
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> ConversationResponse:
    return await service.update_title(
        user_id=current_user["_id"],
        conversation_id=conversation_id,
        payload=payload,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service),
    ],
) -> Response:
    await service.delete(
        user_id=current_user["_id"],
        conversation_id=conversation_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)