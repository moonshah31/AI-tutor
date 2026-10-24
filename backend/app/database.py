from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings


class DatabaseManager:
    """Owns MongoDB's application-scoped client and safe connectivity checks."""

    def __init__(self) -> None:
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    def connect(self, settings: Settings) -> None:
        self.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=2_000,
            connectTimeoutMS=2_000,
        )
        self.database = self.client[settings.mongodb_database]

    async def is_healthy(self) -> bool:
        if self.client is None:
            return False
        try:
            await self.client.admin.command("ping")
        except Exception:
            return False
        return True

    def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.database = None

    async def ensure_indexes(self) -> None:
        """Create required indexes idempotently after connecting to MongoDB."""
        if self.database is None:
            return

        await self.database.users.create_index(
            "email",
            unique=True,
            name="unique_user_email",
        )

        await self.database.conversations.create_index(
            [("user_id", 1), ("updated_at", -1)],
            name="conversations_by_user_updated",
        )
        await self.database.documents.create_index(
             [("user_id", 1), ("updated_at", -1)],
             name="documents_by_user_updated",
        )  
           

database_manager = DatabaseManager()


async def get_database() -> AsyncIterator[AsyncIOMotorDatabase]:
    """Dependency placeholder for future protected route services."""
    if database_manager.database is None:
        raise RuntimeError("Database has not been initialized")
    yield database_manager.database
