from typing import Annotated

from bson import ObjectId
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.database import get_database
from app.services.auth_service import credentials_exception, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_exception
    user_id = decode_access_token(credentials.credentials, settings)
    user = await database.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    return user
