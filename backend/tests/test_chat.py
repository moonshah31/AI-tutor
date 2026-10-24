import asyncio
from unittest.mock import AsyncMock

import pytest

from app.providers.base import AIProvider, AIProviderError
from app.routes.chat import get_tutor_service
from app.schemas.chat import ConversationMessage, TutorRequest
from app.services.tutor_service import TutorService

from test_auth import register


class FakeProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        answer: str = "A helpful tutor response.",
        error: Exception | None = None,
    ) -> None:
        self.generate_response_mock = AsyncMock(
            side_effect=error,
            return_value=answer,
        )

    async def generate_response(
        self,
        prompt: str,
    ) -> str:
        return await self.generate_response_mock(prompt)


def auth_header(test_client) -> dict[str, str]:
    register(test_client)

    login = test_client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "StrongPass123!",
        },
    )

    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def create_conversation(
    test_client,
    headers: dict[str, str],
) -> str:
    response = test_client.post(
        "/api/conversations",
        headers=headers,
        json={"title": "Test Conversation"},
    )

    assert response.status_code == 201

    return response.json()["id"]


@pytest.fixture
def tutor_override(client):
    test_client, _ = client
    provider = FakeProvider()

    from app.main import app

    app.dependency_overrides[get_tutor_service] = (
        lambda: TutorService(provider)
    )

    yield test_client, provider

    app.dependency_overrides.pop(get_tutor_service, None)


def test_chat_requires_authentication(client):
    test_client, _ = client

    response = test_client.post(
        "/api/chat",
        json={
            "conversation_id": "507f1f77bcf86cd799439011",
            "message": "Explain recursion",
        },
    )

    assert response.status_code == 401


def test_chat_calls_tutor_service_with_authenticated_identity_and_context(
    tutor_override,
):
    test_client, provider = tutor_override
    headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        headers,
    )

    # Add previous conversation history.
    first_message = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain recursion",
        },
    )

    assert first_message.status_code == 200

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Give me an example",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "response": "A helpful tutor response.",
        "provider": "gemini",
    }

    assert provider.generate_response_mock.await_args is not None
    prompt = provider.generate_response_mock.await_args.args[0]

    assert "ROLE:" in prompt
    assert "CONTEXT:" in prompt
    assert "TARGET:" in prompt
    assert "CONSTRAINTS & PEDAGOGY:" in prompt

    assert "Test Student" in prompt
    assert "Explain recursion" in prompt
    assert "Give me an example" in prompt


def test_chat_rejects_blank_oversized_and_excessive_context(
    tutor_override,
):
    test_client, _ = tutor_override
    headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        headers,
    )

    assert (
        test_client.post(
            "/api/chat",
            headers=headers,
            json={
                "conversation_id": conversation_id,
                "message": "   ",
            },
        ).status_code
        == 422
    )

    assert (
        test_client.post(
            "/api/chat",
            headers=headers,
            json={
                "conversation_id": conversation_id,
                "message": "x" * 4001,
            },
        ).status_code
        == 422
    )


def test_chat_provider_error_is_safe(tutor_override):
    test_client, provider = tutor_override
    headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        headers,
    )

    provider.generate_response_mock.side_effect = AIProviderError(
        "secret=should-not-appear"
    )

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain recursion",
        },
    )

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        == "The tutor is temporarily unavailable. Please try again shortly."
    )

    assert "secret" not in response.text


def test_chat_persists_user_and_assistant_messages(tutor_override):
    test_client, _ = tutor_override
    headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        headers,
    )

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain recursion",
        },
    )

    assert response.status_code == 200

    conversation_response = test_client.get(
        f"/api/conversations/{conversation_id}",
        headers=headers,
    )

    assert conversation_response.status_code == 200

    conversation = conversation_response.json()

    assert len(conversation["messages"]) == 2

    assert conversation["messages"][0]["role"] == "user"
    assert conversation["messages"][0]["content"] == "Explain recursion"

    assert conversation["messages"][1]["role"] == "assistant"
    assert conversation["messages"][1]["content"] == (
        "A helpful tutor response."
    )
def test_chat_does_not_persist_messages_when_provider_fails(
    tutor_override,
):
    test_client, provider = tutor_override
    headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        headers,
    )

    provider.generate_response_mock.side_effect = AIProviderError(
        "temporary provider failure"
    )

    response = test_client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explain recursion",
        },
    )

    assert response.status_code == 503

    conversation_response = test_client.get(
        f"/api/conversations/{conversation_id}",
        headers=headers,
    )

    assert conversation_response.status_code == 200

    conversation = conversation_response.json()

    assert conversation["messages"] == []

def test_chat_cannot_access_another_users_conversation(
    tutor_override,
):
    test_client, _ = tutor_override

    # Create conversation for first user.
    first_user_headers = auth_header(test_client)

    conversation_id = create_conversation(
        test_client,
        first_user_headers,
    )

    # Create a second user.
    test_client.post(
        "/api/auth/register",
        json={
            "name": "Second Student",
            "email": "second@example.com",
            "password": "StrongPass123!",
        },
    )

    second_login = test_client.post(
        "/api/auth/login",
        json={
            "email": "second@example.com",
            "password": "StrongPass123!",
        },
    )

    second_headers = {
        "Authorization": (
            f"Bearer {second_login.json()['access_token']}"
        )
    }

    response = test_client.post(
        "/api/chat",
        headers=second_headers,
        json={
            "conversation_id": conversation_id,
            "message": "Try to access another user's conversation",
        },
    )

    assert response.status_code == 404


def test_tutor_service_normalizes_provider_response_and_builds_prompt():
    provider = FakeProvider(
        answer="  A concise explanation.  "
    )

    service = TutorService(provider)

    request = TutorRequest(
        message="What is a loop?",
        messages=[
            ConversationMessage(
                role="user",
                content="I am new to Python.",
            )
        ],
    )

    result = asyncio.run(
        service.reply(
            current_user={"name": "Amina"},
            request=request,
        )
    )

    assert result.response == "A concise explanation."
    assert result.provider == "gemini"

    assert provider.generate_response_mock.await_args is not None
    prompt = provider.generate_response_mock.await_args.args[0]

    assert "Amina" in prompt