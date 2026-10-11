"""Diagnose an AI Studio API key and Gemma model without printing secrets.

Run from apps/api: uv run python -m scripts.check_gemma_credentials
Add --vision to test the image request used by the Wildmon worker.
"""

import argparse
import asyncio
import base64
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

GOOGLE_ORIGIN = "https://generativelanguage.googleapis.com"


def describe_error(response: httpx.Response, key: str) -> str:
    """Show Google's error code and message while redacting the configured key."""
    try:
        error = response.json().get("error", {})
        code = error.get("status", "unknown")
        message = error.get("message", "No error message returned")
    except (ValueError, AttributeError):
        code, message = "unknown", "No JSON error message returned"
    safe = str(message).replace(key, "[REDACTED]") if key else str(message)
    return f"HTTP {response.status_code} {code}: {safe[:350]}"


async def check_response(
    client: httpx.AsyncClient, method: str, url: str, key: str, **kwargs: object
) -> httpx.Response | None:
    """Make one request and print a bounded, secret-safe failure if it fails."""
    started = monotonic()
    try:
        response = await client.request(method, url, headers={"x-goog-api-key": key}, **kwargs)
    except httpx.ConnectTimeout:
        print(f"  failed: connection timed out after {monotonic() - started:.1f}s")
        return None
    except httpx.ReadTimeout:
        print(f"  failed: no response received after {monotonic() - started:.1f}s")
        print("  Google may be slow, or a proxy/network may be holding the response.")
        return None
    except httpx.WriteTimeout:
        print(f"  failed: upload timed out after {monotonic() - started:.1f}s")
        return None
    except httpx.TimeoutException as exc:
        print(f"  failed: {type(exc).__name__} after {monotonic() - started:.1f}s")
        return None
    except httpx.ConnectError as exc:
        cause = type(exc.__cause__).__name__ if exc.__cause__ else "unknown"
        print(f"  failed: connection/DNS error ({cause}); credentials were not checked")
        return None
    except httpx.RequestError as exc:
        print(f"  failed: network error ({type(exc).__name__}); credentials were not checked")
        return None
    if response.is_error:
        print(f"  failed: {describe_error(response, key)}")
        return None
    print(f"  response received in {monotonic() - started:.1f}s")
    return response


async def diagnose(
    vision: bool = False,
    read_timeout: float = 120,
    model_override: str | None = None,
    vision_only: bool = False,
) -> int:
    """Separate key, model, text, and optional image failures to locate the cause."""
    settings = get_settings()
    key = settings.gemma_api_key.strip()
    model = (model_override or settings.gemma_model).strip().removeprefix("models/")
    base = urlparse(settings.gemma_base_url)
    if not key:
        print("GEMMA_API_KEY is empty in apps/api/.env")
        return 2
    if not model:
        print("GEMMA_MODEL is empty in apps/api/.env")
        return 2
    if base.scheme != "https" or base.hostname != "generativelanguage.googleapis.com":
        print("This diagnostic supports AI Studio keys with the Google Gemini API host only.")
        print("Set GEMMA_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/")
        return 2
    if base.path.rstrip("/") != "/v1beta/openai":
        print("Warning: GEMMA_BASE_URL should end in /v1beta/openai/ for the Wildmon adapter.")
    print(f"Testing AI Studio key with model {model} (key hidden)")
    timeout = httpx.Timeout(connect=10, read=read_timeout, write=30, pool=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        print("1. Key / model-list access")
        response = await check_response(client, "GET", f"{GOOGLE_ORIGIN}/v1beta/models", key)
        if response is None:
            print("Check the key's status/restrictions in AI Studio and your network connection.")
            return 1
        print("  passed: Google accepted the key for model listing")

        print(f"2. Model access ({model})")
        response = await check_response(
            client, "GET", f"{GOOGLE_ORIGIN}/v1beta/models/{model}", key
        )
        if response is None:
            print("Check the model ID and whether this key can access it in AI Studio.")
            return 1
        methods = response.json().get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            print("  failed: this model does not advertise generateContent")
            return 1
        print("  passed: model supports generateContent")

        url = f"{GOOGLE_ORIGIN}/v1beta/models/{model}:generateContent"
        if not vision_only:
            print("3. Text generation")
            response = await check_response(
                client,
                "POST",
                url,
                key,
                json={"contents": [{"parts": [{"text": "Reply with the word OK."}]}]},
            )
            if response is None:
                print("Key and model listing work; generation did not complete.")
                return 1
            if not response.json().get("candidates"):
                print("  failed: request succeeded but returned no candidates")
                return 1
            print("  passed: text generation returned a candidate")

        if vision or vision_only:
            image = Path(__file__).resolve().parents[2] / "web" / "public" / "wildmon-hero.jpg"
            print("4. Image generation" if not vision_only else "3. Image generation")
            response = await check_response(
                client,
                "POST",
                url,
                key,
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": "Name the main subject of this image in one word."},
                                {
                                    "inlineData": {
                                        "mimeType": "image/jpeg",
                                        "data": base64.b64encode(image.read_bytes()).decode(
                                            "ascii"
                                        ),
                                    }
                                },
                            ]
                        }
                    ]
                },
            )
            if response is None:
                print("Image generation failed; compare with another supported Gemma 4 model.")
                return 1
            if not response.json().get("candidates"):
                print("  failed: request succeeded but returned no candidates")
                return 1
            print("  passed: image request returned a candidate")
    print("Gemma API connectivity is working. If jobs still fail, inspect worker logs.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vision", action="store_true", help="also send the bundled test image")
    parser.add_argument(
        "--vision-only", action="store_true", help="test an image without text generation"
    )
    parser.add_argument("--model", help="test a model without changing GEMMA_MODEL in .env")
    parser.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="seconds to wait for each response (default: 120)",
    )
    args = parser.parse_args()
    if not 1 <= args.timeout <= 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    raise SystemExit(asyncio.run(diagnose(args.vision, args.timeout, args.model, args.vision_only)))


if __name__ == "__main__":
    main()
