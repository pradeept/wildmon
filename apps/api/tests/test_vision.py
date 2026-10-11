import json

import httpx
import pytest

from app.ai import vision
from app.core.config import Settings
from app.worker import assess_identification


@pytest.mark.asyncio
async def test_ai_studio_gemma_uses_native_image_endpoint(monkeypatch):
    """The AI Studio key and image must reach the documented Gemma REST endpoint."""
    requests = []
    client_options = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "primary_subject": "flower",
                                            "category": "flowering_plant",
                                            "scientific_name": None,
                                            "common_name": None,
                                            "candidate_rank": "category",
                                            "traits": [],
                                            "uncertainty": "",
                                            "insufficient_image": False,
                                            "multiple_subjects": False,
                                            "unrelated_image": False,
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        client_options.append(kwargs)
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="test-key",
        )
    )
    result = await identifier.identify(b"image", "image/jpeg", [])

    assert result.category == "flowering_plant"
    request = requests[0]
    assert request.url.path == "/v1beta/models/gemma-4-31b-it:generateContent"
    assert request.headers["x-goog-api-key"] == "test-key"
    assert client_options[0]["timeout"].read == 120
    parts = json.loads(request.content)["contents"][0]["parts"]
    assert parts[1]["inlineData"]["mimeType"] == "image/jpeg"
    assert parts[1]["inlineData"]["data"] == "aW1hZ2U="


@pytest.mark.asyncio
async def test_ai_studio_error_includes_provider_message_without_key(monkeypatch):
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"status": "INTERNAL", "message": "Key test-key: internal error"}},
        )

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="test-key",
        )
    )

    with pytest.raises(httpx.HTTPStatusError) as raised:
        await identifier.identify(b"image", "image/jpeg", [])

    assert "Gemma HTTP 500 INTERNAL: Key [REDACTED]: internal error" in str(raised.value)
    assert "test-key" not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("google_status", [400, 429, 500])
async def test_google_failure_uses_same_gemma_model_on_backboard(monkeypatch, google_status):
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(
                google_status, json={"error": {"status": "INTERNAL", "message": "failure"}}
            )
        return httpx.Response(200, json={"status": "COMPLETED", "content": '{"confirmed": []}'})

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="google-key",
            backboard_key="backboard-key",
        )
    )

    assert await identifier.validate_traits(b"image", "image/jpeg", ["five_petals"]) == []
    assert len(requests) == 2
    assert requests[0].url.path == "/v1beta/models/gemma-4-31b-it:generateContent"
    fallback = requests[1]
    assert fallback.url == vision.BACKBOARD_MESSAGES_URL
    assert fallback.headers["x-api-key"] == "backboard-key"
    assert b'form-data; name="llm_provider"' in fallback.content
    assert b"openrouter" in fallback.content
    assert b'form-data; name="model_name"' in fallback.content
    assert b"google/gemma-4-31b-it" in fallback.content
    assert b'filename="discovery.jpg"' in fallback.content
    assert b"image" in fallback.content


@pytest.mark.asyncio
async def test_google_success_never_uses_backboard(monkeypatch):
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"confirmed": []}'}]}}]},
        )

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="google-key",
            backboard_key="backboard-key",
        )
    )

    assert await identifier.validate_traits(b"image", "image/jpeg", ["five_petals"]) == []
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_backboard_failure_redacts_key_and_fails_job(monkeypatch):
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(500, json={"error": {"status": "INTERNAL"}})
        return httpx.Response(
            401, json={"error": {"status": "AUTH", "message": "Key backboard-key invalid"}}
        )

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="google-key",
            backboard_key="backboard-key",
        )
    )

    with pytest.raises(httpx.HTTPStatusError, match="Backboard HTTP 401") as raised:
        await identifier.validate_traits(b"image", "image/jpeg", ["five_petals"])

    assert "backboard-key" not in str(raised.value)
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "expected_status"), [("flower", "verified"), (None, "needs_review")]
)
async def test_backboard_fallback_parses_identification(monkeypatch, subject, expected_status):
    result = {
        "primary_subject": subject,
        "category": "flowering_plant",
        "scientific_name": None,
        "common_name": None,
        "candidate_rank": "category",
        "traits": [],
        "uncertainty": "",
        "insufficient_image": False,
        "multiple_subjects": False,
        "unrelated_image": False,
    }

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(500, json={"error": {"status": "INTERNAL"}})
        return httpx.Response(200, json={"status": "COMPLETED", "content": json.dumps(result)})

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(vision.httpx, "AsyncClient", client_factory)
    identifier = vision.GemmaVisionIdentifier(
        Settings(
            _env_file=None,
            gemma_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            gemma_model="gemma-4-31b-it",
            gemma_api_key="google-key",
            backboard_key="backboard-key",
        )
    )

    identified = await identifier.identify(b"image", "image/jpeg", [])
    assert identified.category == "flowering_plant"
    status, uncertainty = assess_identification(identified, identified.category)
    assert status == expected_status
    if subject is None:
        assert uncertainty == "The model could not identify a clear primary subject."
