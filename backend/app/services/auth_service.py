from datetime import UTC, datetime, timedelta

import jwt
from bson import ObjectId
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.config import Settings
from app.models.user import UserDocument
from app.schemas.user import UserResponse

password_hash = PasswordHash.recommended()
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: str, settings: Settings, expires_delta: timedelta | None = None) -> str:
    expires_at = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    return jwt.encode({"sub": user_id, "exp": expires_at}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    try:
        subject = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]).get("sub")
        if not subject or not ObjectId.is_valid(subject):
            raise credentials_exception
        return str(subject)
    except InvalidTokenError as error:
        raise credentials_exception from error


def user_response(user: dict) -> UserResponse:
    return UserResponse(id=str(user["_id"]), name=user["name"], email=user["email"])


def new_user_document(name: str, email: str, password: str) -> UserDocument:
    now = datetime.now(UTC)
    return UserDocument(name=name.strip(), email=normalize_email(email), password_hash=hash_password(password), created_at=now, updated_at=now)
