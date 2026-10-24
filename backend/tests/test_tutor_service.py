
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.schemas.chat import ChatResponse, TutorRequest
from app.services.tutor_service import TutorService


@pytest.fixture
def current_user():
    return {
        "_id": ObjectId(),
        "name": "Test Student",
    }


@pytest.fixture
def tutor_request():
    return TutorRequest(
        message="Explain photosynthesis",
        messages=[],
    )


@pytest.fixture
def retrieved_chunks():
    return [
        {
            "document_id": str(ObjectId()),
            "chunk_number": 1,
            "section_number": 1,
            "location_label": "Page 2",
            "text": "Photosynthesis converts light energy into chemical energy.",
            "score": 1.25,
        }
    ]


@pytest.mark.asyncio
async def test_reply_retrieves_course_material_and_builds_response(
    current_user,
    tutor_request,
    retrieved_chunks,
):
    provider = MagicMock()
    provider.name = "test-provider"
    provider.generate_response = AsyncMock(
        return_value="Photosynthesis converts light energy into chemical energy."
    )

    retrieval_service = MagicMock()
    retrieval_service.search = AsyncMock(return_value=retrieved_chunks)

    service = TutorService(
        provider,
        retrieval_service=retrieval_service,
    )

    response = await service.reply(
        current_user=current_user,
        request=tutor_request,
    )

    retrieval_service.search.assert_awaited_once_with(
        user_id=current_user["_id"],
        query=tutor_request.message,
        limit=5,
    )

    provider.generate_response.assert_awaited_once()

    prompt = provider.generate_response.await_args.args[0]
    assert "Photosynthesis converts light energy into chemical energy." in prompt
    assert "Test Student" in prompt
    assert tutor_request.message in prompt

    assert isinstance(response, ChatResponse)
    assert response.response == (
        "Photosynthesis converts light energy into chemical energy."
    )
    assert response.provider == "test-provider"


@pytest.mark.asyncio
async def test_reply_works_without_retrieval_service(
    current_user,
    tutor_request,
):
    provider = MagicMock()
    provider.name = "test-provider"
    provider.generate_response = AsyncMock(
        return_value="Here is an explanation."
    )

    service = TutorService(provider)

    response = await service.reply(
        current_user=current_user,
        request=tutor_request,
    )

    provider.generate_response.assert_awaited_once()
    prompt = provider.generate_response.await_args.args[0]

    assert tutor_request.message in prompt
    assert "No relevant excerpts were retrieved" in prompt
    assert response.response == "Here is an explanation."


@pytest.mark.asyncio
async def test_reply_rejects_missing_user_id_when_retrieval_enabled(
    tutor_request,
):
    provider = MagicMock()
    provider.name = "test-provider"
    provider.generate_response = AsyncMock()

    retrieval_service = MagicMock()
    retrieval_service.search = AsyncMock()

    service = TutorService(
        provider,
        retrieval_service=retrieval_service,
    )

    with pytest.raises(
        ValueError,
        match="An authenticated user ID is required",
    ):
        await service.reply(
            current_user={"name": "Test Student"},
            request=tutor_request,
        )

    retrieval_service.search.assert_not_awaited()
    provider.generate_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_reply_uses_empty_results_when_no_documents_match(
    current_user,
    tutor_request,
):
    provider = MagicMock()
    provider.name = "test-provider"
    provider.generate_response = AsyncMock(
        return_value="I couldn't find this in your uploaded material."
    )

    retrieval_service = MagicMock()
    retrieval_service.search = AsyncMock(return_value=[])

    service = TutorService(
        provider,
        retrieval_service=retrieval_service,
    )

    response = await service.reply(
        current_user=current_user,
        request=tutor_request,
    )

    prompt = provider.generate_response.await_args.args[0]

    assert "No relevant excerpts were retrieved" in prompt
    assert response.response == (
        "I couldn't find this in your uploaded material."
    )
