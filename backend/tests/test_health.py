from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.database import database_manager
from app.main import app


def test_health_returns_connected_status_when_database_is_available(monkeypatch):
    monkeypatch.setattr(database_manager, "is_healthy", AsyncMock(return_value=True))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_returns_safe_degraded_status_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(database_manager, "is_healthy", AsyncMock(return_value=False))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
