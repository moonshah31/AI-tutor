from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.conversation import ConversationDocument, MessageDocument
from app.schemas.conversation import (
    ConversationCreate,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationSummary,
    ConversationUpdate,
)


class ConversationService:
    """Handles conversation persistence and ownership enforcement."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._database = database

    async def create(
        self,
        *,
        user_id: ObjectId,
        payload: ConversationCreate,
    ) -> ConversationResponse:
        now = datetime.now(UTC)

        document = {
            "user_id": user_id,
            "title": payload.title.strip(),
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

        result = await self._database.conversations.insert_one(document)

        saved_document: ConversationDocument = {
            "_id": result.inserted_id,
            "user_id": user_id,
            "title": document["title"],
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

        return self._to_response(saved_document)

    async def list_for_user(
        self,
        *,
        user_id: ObjectId,
    ) -> list[ConversationSummary]:
        cursor = (
            self._database.conversations
            .find(
                {"user_id": user_id},
                {
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "messages": 1,
                },
            )
            .sort("updated_at", -1)
        )

        conversations: list[ConversationSummary] = []

        async for document in cursor:
            conversations.append(
                ConversationSummary(
                    id=str(document["_id"]),
                    title=document["title"],
                    created_at=document["created_at"],
                    updated_at=document["updated_at"],
                    message_count=len(document.get("messages", [])),
                )
            )

        return conversations

    async def get_for_user(
        self,
        *,
        user_id: ObjectId,
        conversation_id: str,
    ) -> ConversationResponse:
        conversation = await self._find_owned_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        return self._to_response(conversation)

    async def update_title(
        self,
        *,
        user_id: ObjectId,
        conversation_id: str,
        payload: ConversationUpdate,
    ) -> ConversationResponse:
        conversation = await self._find_owned_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        updated_at = datetime.now(UTC)
        new_title = payload.title.strip()

        await self._database.conversations.update_one(
            {
                "_id": conversation["_id"],
                "user_id": user_id,
            },
            {
                "$set": {
                    "title": new_title,
                    "updated_at": updated_at,
                }
            },
        )

        conversation["title"] = new_title
        conversation["updated_at"] = updated_at

        return self._to_response(conversation)

    async def delete(
        self,
        *,
        user_id: ObjectId,
        conversation_id: str,
    ) -> None:
        conversation = await self._find_owned_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        await self._database.conversations.delete_one(
            {
                "_id": conversation["_id"],
                "user_id": user_id,
            }
        )

    async def add_message(
        self,
        *,
        user_id: ObjectId,
        conversation_id: str,
        role: Literal["user", "assistant"],
        content: str,
    ) -> ConversationDocument:
        """Append a message to an owned conversation."""

        conversation = await self._find_owned_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        message: MessageDocument = {
            "role": role,
            "content": content,
            "created_at": datetime.now(UTC),
        }

        updated_at = datetime.now(UTC)

        await self._database.conversations.update_one(
            {
                "_id": conversation["_id"],
                "user_id": user_id,
            },
            {
                "$push": {
                    "messages": message,
                },
                "$set": {
                    "updated_at": updated_at,
                },
            },
        )

        # Create a properly typed message list instead of relying
        # on Pylance's inference from the MongoDB document.
        messages: list[MessageDocument] = list(conversation.get("messages", []))
        messages.append(message)

        conversation["messages"] = messages
        conversation["updated_at"] = updated_at

        return conversation

    async def _find_owned_conversation(
        self,
        *,
        user_id: ObjectId,
        conversation_id: str,
    ) -> ConversationDocument:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        conversation = await self._database.conversations.find_one(
            {
                "_id": ObjectId(conversation_id),
                "user_id": user_id,
            }
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return conversation

    @staticmethod
    def _to_response(
        document: ConversationDocument,
    ) -> ConversationResponse:
        messages = [
            ConversationMessageResponse(
                role=message["role"],
                content=message["content"],
                created_at=message["created_at"],
            )
            for message in document.get("messages", [])
        ]

        return ConversationResponse(
            id=str(document["_id"]),
            title=document["title"],
            messages=messages,
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )