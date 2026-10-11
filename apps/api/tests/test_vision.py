import json

import httpx
import pytest

from app.ai import vision
from app.core.config import Settings


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
