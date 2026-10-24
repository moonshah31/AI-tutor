from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.database import database_manager
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Check API and database availability")
async def health_check() -> HealthResponse | JSONResponse:
    if not await database_manager.is_healthy():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="degraded", database="unavailable").model_dump(),
        )
    return HealthResponse(status="ok", database="connected")
