from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.services.auth_service import user_response

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserResponse:
    return user_response(current_user)
