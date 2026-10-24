from typing import Literal

from pydantic import BaseModel, Field, field_validator


MAX_MESSAGE_LENGTH = 4_000
MAX_CONTEXT_MESSAGES = 10


class ConversationMessage(BaseModel):
    """A bounded, in-memory message supplied by the active browser session."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def content_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content cannot be blank")
        return value



class ChatRequest(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Conversation ID cannot be blank")

        return value

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be blank")

        return value

class TutorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    messages: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_CONTEXT_MESSAGES,
    )
    
class ChatResponse(BaseModel):
    response: str
    provider: str = "gemini"
