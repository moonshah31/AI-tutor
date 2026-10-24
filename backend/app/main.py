from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import database_manager
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.chat import router as chat_router
from app.routes.conversation import router as conversations_router
from app.routes.document import router as document_router


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    database_manager.connect(settings)
    await database_manager.ensure_indexes()
    yield
    database_manager.disconnect()


app = FastAPI(
    title="AI Tutor API",
    version="0.1.0",
    description="Backend API for the AI Tutor application.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(document_router)