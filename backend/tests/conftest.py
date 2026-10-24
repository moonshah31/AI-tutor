
"""Shared backend test setup for routes that require the application lifespan."""

import os
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-that-is-long-enough-for-tests-only",
)

from app.database import database_manager
from app.main import app


class FakeUsers:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def create_index(self, *_args, **_kwargs) -> str:
        return "unique_user_email"

    async def insert_one(self, document: dict):
        if any(
            item["email"] == document["email"]
            for item in self.documents
        ):
            from pymongo.errors import DuplicateKeyError

            raise DuplicateKeyError("duplicate")

        stored = {"_id": ObjectId(), **document}
        self.documents.append(stored)

        return type(
            "InsertResult",
            (),
            {"inserted_id": stored["_id"]},
        )()

    async def find_one(self, query: dict):
        for document in self.documents:
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                return document

        return None


class FakeConversations:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def insert_one(self, document: dict):
        stored = {"_id": ObjectId(), **document}
        self.documents.append(stored)

        return type(
            "InsertResult",
            (),
            {"inserted_id": stored["_id"]},
        )()

    async def find_one(self, query: dict):
        for document in self.documents:
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                return document

        return None

    async def update_one(self, query: dict, update: dict):
        for document in self.documents:
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                if "$set" in update:
                    document.update(update["$set"])

                if "$push" in update:
                    push = update["$push"]
                    each = push.get("$each", [])
                    document.setdefault("messages", []).extend(each)

                return type(
                    "UpdateResult",
                    (),
                    {"modified_count": 1},
                )()

        return type(
            "UpdateResult",
            (),
            {"modified_count": 0},
        )()

    async def delete_one(self, query: dict):
        for index, document in enumerate(self.documents):
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                self.documents.pop(index)

                return type(
                    "DeleteResult",
                    (),
                    {"deleted_count": 1},
                )()

        return type(
            "DeleteResult",
            (),
            {"deleted_count": 0},
        )()


class FakeDocuments:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def create_index(self, *_args, **_kwargs) -> str:
        return "documents_by_user_updated"

    async def insert_one(self, document: dict):
        stored = {"_id": ObjectId(), **document}
        self.documents.append(stored)

        return type(
            "InsertResult",
            (),
            {"inserted_id": stored["_id"]},
        )()

    async def find_one(self, query: dict):
        for document in self.documents:
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                return document

        return None

    

       
    def find(
        self,
        query: dict,
        projection: dict | None = None,
    ):
        return FakeDocumentCursor(
            self.documents,
            query,
            projection,
        )

    async def delete_one(self, query: dict):
        for index, document in enumerate(self.documents):
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                self.documents.pop(index)

                return type(
                    "DeleteResult",
                    (),
                    {"deleted_count": 1},
                )()

        return type(
            "DeleteResult",
            (),
            {"deleted_count": 0},
        )()

    async def update_one(
        self,
        query: dict,
        update: dict,
    ):
        for document in self.documents:
            if all(
                document.get(key) == value
                for key, value in query.items()
            ):
                if "$set" in update:
                    document.update(update["$set"])

                return type(
                    "UpdateResult",
                    (),
                    {
                        "matched_count": 1,
                        "modified_count": 1,
                    },
                )()

        return type(
            "UpdateResult",
            (),
            {
                "matched_count": 0,
                "modified_count": 0,
            },
        )()


class FakeDocumentCursor:
    def __init__(
        self,
        documents: list[dict],
        query: dict,
        projection: dict | None,
    ) -> None:
        def matches(document: dict) -> bool:
            for key, expected in query.items():
                actual = document.get(key)

                if isinstance(expected, dict):
                    if "$ne" in expected:
                        # MongoDB $ne matches missing fields too.
                        if actual == expected["$ne"]:
                            return False
                    else:
                        raise NotImplementedError(
                            f"Unsupported query operator: {expected}"
                        )
                elif actual != expected:
                    return False

            return True

        self._documents = [
            document
            for document in documents
            if matches(document)
        ]
        self._projection = projection

    def sort(self, field: str, direction: int):
        self._documents.sort(
            key=lambda document: document[field],
            reverse=direction < 0,
        )
        return self

    def __aiter__(self):
        return self._iterator()

    async def _iterator(self):
        for document in self._documents:
            if self._projection is None:
                yield document
                continue

            projected = {
                key: document[key]
                for key, value in self._projection.items()
                if value and key in document
            }

            projected["_id"] = document["_id"]

            yield projected


class FakeDocumentChunks:
    """In-memory replacement for MongoDB's document_chunks collection."""

    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def insert_many(self, documents: list[dict]):
        stored_documents = [
            dict(document)
            for document in documents
        ]
        self.documents.extend(stored_documents)

        return type(
            "InsertManyResult",
            (),
            {
                "inserted_ids": [
                    document.get("_id")
                    for document in stored_documents
                ]
            },
        )()

    async def delete_many(self, query: dict):
        def matches(document: dict) -> bool:
            for key, expected in query.items():
                actual = document.get(key)

                if isinstance(expected, dict) and "$ne" in expected:
                    if actual == expected["$ne"]:
                        return False
                elif actual != expected:
                    return False

            return True

        matching = [
            document
            for document in self.documents
            if matches(document)
        ]

        self.documents = [
            document
            for document in self.documents
            if not matches(document)
        ]

        return type(
            "DeleteResult",
            (),
            {"deleted_count": len(matching)},
        )()

    
    def find(self, query: dict):
        matching = [
            document
            for document in self.documents
            if all(
                document.get(key) == value
                for key, value in query.items()
            )
        ]
        return FakeDocumentChunkCursor(matching)



    
class FakeDocumentChunkCursor:
    """Async cursor for chunk retrieval tests."""

    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents

    def __aiter__(self):
        return self._iterator()

    async def _iterator(self):
        for document in self._documents:
            yield document


class FakeDatabase:
    def __init__(self) -> None:
        self.users = FakeUsers()
        self.conversations = FakeConversations()
        self.documents = FakeDocuments()
        self.document_chunks = FakeDocumentChunks()


@pytest.fixture
def client(monkeypatch):
    """Run protected-route tests against an isolated in-memory database."""

    fake_database = FakeDatabase()

    monkeypatch.setattr(
        database_manager,
        "connect",
        lambda _settings: setattr(
            database_manager,
            "database",
            fake_database,
        ),
    )
    monkeypatch.setattr(
        database_manager,
        "disconnect",
        lambda: setattr(database_manager, "database", None),
    )
    monkeypatch.setattr(
        database_manager,
        "ensure_indexes",
        AsyncMock(),
    )

    with TestClient(app) as test_client:
        yield test_client, fake_database
