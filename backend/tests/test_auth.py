import os
from datetime import timedelta
from app.config import get_settings
from app.services.auth_service import create_access_token


def register(client, email="student@example.com", password="StrongPass123!"):
    return client.post("/api/auth/register", json={"name": "Test Student", "email": email, "password": password})


def test_registration_normalizes_email_and_never_exposes_hash(client):
    test_client, database = client
    response = register(test_client, "STUDENT@EXAMPLE.COM")
    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert "password_hash" not in response.json()
    assert database.users.documents[0]["password_hash"] != "StrongPass123!"


def test_registration_duplicate_and_invalid_input_are_rejected(client):
    test_client, _ = client
    assert register(test_client).status_code == 201
    assert register(test_client).status_code == 409
    assert register(test_client, "not-an-email").status_code == 422
    assert test_client.post("/api/auth/register", json={"email": "a@example.com", "password": "StrongPass123!"}).status_code == 422


def test_login_and_current_user(client):
    test_client, _ = client
    register(test_client)
    login = test_client.post("/api/auth/login", json={"email": "STUDENT@example.com", "password": "StrongPass123!"})
    assert login.status_code == 200
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert "password_hash" not in payload
    response = test_client.get("/api/users/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"
    assert "password_hash" not in response.json()


def test_invalid_login_and_missing_fields_fail_safely(client):
    test_client, _ = client
    register(test_client)
    assert test_client.post("/api/auth/login", json={"email": "student@example.com", "password": "wrong"}).status_code == 401
    assert test_client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong"}).status_code == 401
    assert test_client.post("/api/auth/login", json={"email": "student@example.com"}).status_code == 422


def test_protected_route_rejects_missing_invalid_and_expired_tokens(client):
    test_client, database = client
    response = test_client.get("/api/users/me")
    assert response.status_code == 401
    assert test_client.get("/api/users/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    registration = register(test_client)
    user_id = registration.json()["id"]
    expired = create_access_token(user_id, get_settings(), expires_delta=timedelta(seconds=-1))
    assert test_client.get("/api/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    # Identity is only derived from the JWT subject; arbitrary request data is ignored.
    assert len(database.users.documents) == 1
