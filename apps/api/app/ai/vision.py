import base64
import json
import logging
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import Settings

logger = logging.getLogger("wildmon.vision")
BACKBOARD_MESSAGES_URL = "https://app.backboard.io/api/threads/messages"


class VisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_subject: str | None
    category: Literal["plant", "bird", "insect", "butterfly", "flowering_plant", "tree"] | None
    scientific_name: str | None
    common_name: str | None
    candidate_rank: Literal["species", "genus", "family", "category", "unknown"]
    traits: list[Literal["serrated_leaf", "yellow_flower", "five_petals", "striped_wing"]]
    uncertainty: str
    insufficient_image: bool
    multiple_subjects: bool
    unrelated_image: bool


class VisionIdentifier(Protocol):
    async def identify(
        self, image: bytes, mime_type: str, species: list[dict[str, Any]]
    ) -> VisionResult: ...


class GemmaVisionIdentifier:
    """Use an OpenAI-compatible multimodal Gemma endpoint without trusting raw model text.

    The model can abstain. Catalog resolution and app verification are separate
    decisions made by the worker, never by the model itself.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.gemma_base_url or not settings.gemma_model:
            raise RuntimeError("Gemma endpoint and model are not configured")
        self.settings = settings
        parsed = urlparse(settings.gemma_base_url)
        self.google_native = (
            parsed.hostname == "generativelanguage.googleapis.com"
            and parsed.path.rstrip("/") == "/v1beta/openai"
        )
        self.model = (
            None
            if self.google_native
            else ChatOpenAI(
                model=settings.gemma_model,
                base_url=settings.gemma_base_url,
                api_key=settings.gemma_api_key or "not-required",
                temperature=0,
                timeout=settings.gemma_timeout_seconds,
                max_retries=1,
            )
        )
        self.chain = RunnableLambda(self._identify_payload) | RunnableLambda(self._complete)

    @staticmethod
    def _identify_payload(payload: dict[str, str]) -> dict[str, str]:
        """Keep prompt construction separate from transport so runs can be inspected."""
        instruction = (
            "Identify the one primary organism in this nature photograph. Respond with JSON only, "
            "using keys primary_subject, category, scientific_name, common_name, candidate_rank, "
            "traits, uncertainty, insufficient_image, multiple_subjects, unrelated_image. "
            "Set primary_subject to null if no single organism is identifiable. "
            "candidate_rank must be species, genus, family, category, or unknown. "
            "category must be plant, bird, insect, butterfly, flowering_plant, tree, or null. "
            "traits may only include serrated_leaf, yellow_flower, five_petals, striped_wing. "
            "Use an empty uncertainty string only if the visible evidence is clear; otherwise "
            "explain uncertainty and use a broad rank or unknown. "
            "Do not force a catalog match. Candidate catalog: " + payload["catalog"]
        )
        return {**payload, "instruction": instruction}

    async def _complete(self, payload: dict[str, str]) -> str:
        """Try Google once and use Backboard for provider failures when configured."""
        if self.google_native:
            try:
                return await self._google_complete(payload)
            except (httpx.HTTPError, ValueError) as exc:
                if not self.settings.backboard_key:
                    raise
                failure = (
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                )
                logger.warning("Google Gemma failed (%s); trying Backboard", failure)
                content = await self._backboard_complete(payload)
                logger.info("Backboard Gemma returned a response for validation")
                return content
        message = HumanMessage(
            content=[
                {"type": "text", "text": payload["instruction"]},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{payload['mime_type']};base64,{payload['image']}"},
                },
            ]
        )
        response = await self.model.ainvoke([message])
        return StrOutputParser().invoke(response)

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=10, read=self.settings.gemma_timeout_seconds, write=30, pool=10
        )

    @staticmethod
    def _raise_http_error(response: httpx.Response, provider: str, key: str) -> None:
        """Keep provider detail bounded while excluding the configured API key."""
        try:
            error = response.json().get("error", {})
            status = error.get("status", "unknown")
            message = error.get("message", "No error message returned")
        except (ValueError, AttributeError):
            status, message = "unknown", "No JSON error message returned"
        safe_status = str(status).replace(key, "[REDACTED]") if key else str(status)
        safe_message = str(message).replace(key, "[REDACTED]") if key else str(message)
        summary = f"{provider} HTTP {response.status_code} {safe_status[:50]}: {safe_message[:300]}"
        raise httpx.HTTPStatusError(summary, request=response.request, response=response)

    async def _google_complete(self, payload: dict[str, str]) -> str:
        """Send one native Google request; the caller decides whether to fall back."""
        base = self.settings.gemma_base_url.rstrip("/").removesuffix("/openai")
        url = f"{base}/models/{self.settings.gemma_model}:generateContent"
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": payload["instruction"]},
                        {
                            "inlineData": {
                                "mimeType": payload["mime_type"],
                                "data": payload["image"],
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": self.settings.gemma_api_key},
                json=body,
            )
        if response.is_error:
            self._raise_http_error(response, "Gemma", self.settings.gemma_api_key)
        candidates = response.json().get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        if not text:
            raise ValueError("Gemma returned no text")
        return text

    async def _backboard_complete(self, payload: dict[str, str]) -> str:
        """Send the same image and prompt through Backboard's multipart vision API."""
        model = (
            f"google/{self.settings.gemma_model.removeprefix('models/').removeprefix('google/')}"
        )
        mime = payload["mime_type"]
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(mime, "jpg")
        image = base64.b64decode(payload["image"])
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(
                BACKBOARD_MESSAGES_URL,
                headers={"X-API-Key": self.settings.backboard_key},
                data={
                    "content": payload["instruction"],
                    "llm_provider": "openrouter",
                    "model_name": model,
                    "stream": "false",
                    "memory": "off",
                },
                files={"files": (f"discovery.{extension}", image, mime)},
            )
        if response.is_error:
            self._raise_http_error(response, "Backboard", self.settings.backboard_key)
        result = response.json()
        if result.get("status") != "COMPLETED":
            raise ValueError(f"Backboard returned status {result.get('status', 'unknown')}")
        content = result.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Backboard returned no text")
        return content

    async def identify(
        self, image: bytes, mime_type: str, species: list[dict[str, Any]]
    ) -> VisionResult:
        catalog = ", ".join(f"{item['scientific_name']} ({item['category']})" for item in species)
        encoded = base64.b64encode(image).decode("ascii")
        content = await self.chain.ainvoke(
            {"catalog": catalog, "mime_type": mime_type, "image": encoded}
        )
        content = (
            content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        try:
            return VisionResult.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError("Model returned invalid identification JSON") from exc

    async def validate_traits(self, image: bytes, mime_type: str, codes: list[str]) -> list[str]:
        """Ask a separate constrained visual question before trait evidence can score."""
        if not codes:
            return []
        encoded = base64.b64encode(image).decode("ascii")
        content = await self._complete(
            {
                "instruction": (
                    "Inspect this image. Return JSON with key confirmed "
                    "listing only visible codes. Omit uncertain codes. Allowed codes: "
                    + ", ".join(codes)
                ),
                "mime_type": mime_type,
                "image": encoded,
            }
        )
        content = (
            content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        parsed = json.loads(content)
        return [code for code in parsed.get("confirmed", []) if code in codes]
