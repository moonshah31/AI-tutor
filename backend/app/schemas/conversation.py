from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", min_length=1, max_length=100)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationResponse(BaseModel):
    id: str
    title: str
    messages: list[ConversationMessageResponse]
    created_at: datetime
    updated_at: datetime