from datetime import datetime
from typing import Literal, TypedDict

from bson import ObjectId


class MessageDocument(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationDocument(TypedDict):
    _id: ObjectId
    user_id: ObjectId
    title: str
    messages: list[MessageDocument]
    created_at: datetime
    updated_at: datetime