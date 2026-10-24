from datetime import datetime
from typing import TypedDict


class UserDocument(TypedDict):
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
