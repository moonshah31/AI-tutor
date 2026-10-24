from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.config import Settings, get_settings
from app.database import get_database
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import RegisterRequest, UserResponse
from app.services.auth_service import create_access_token, new_user_document, normalize_email, user_response, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterRequest, database: Annotated[AsyncIOMotorDatabase, Depends(get_database)]) -> UserResponse:
    document = new_user_document(payload.name, payload.email, payload.password)
    try:
        result = await database.users.insert_one(document)
    except DuplicateKeyError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from error
    return UserResponse(id=str(result.inserted_id), name=document["name"], email=document["email"])


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    database: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await database.users.find_one({"email": normalize_email(payload.email)})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(str(user["_id"]), settings), user=user_response(user))
