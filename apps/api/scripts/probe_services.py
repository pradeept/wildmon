"""Check Atlas and AI Studio connectivity without printing secrets.

The bundled hero image is synthetic and is used only to test the vision transport.
It is not part of the model accuracy evaluation.
"""

import asyncio
from pathlib import Path

import httpx
from pymongo import AsyncMongoClient

from app.ai.vision import GemmaVisionIdentifier
from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        print("atlas: connected")
    except Exception as exc:
        cause = type(exc.__cause__).__name__ if exc.__cause__ else "unknown"
        print(f"atlas: failed ({type(exc).__name__}; cause: {cause})")
    finally:
        await client.close()

    image = Path(__file__).resolve().parents[2] / "web" / "public" / "wildmon-hero.jpg"
    try:
        result = await GemmaVisionIdentifier(settings).identify(
            image.read_bytes(), "image/jpeg", []
        )
        print(f"gemma: connected; category={result.category}; rank={result.candidate_rank}")
    except httpx.HTTPStatusError as exc:
        print(f"gemma: failed (HTTP {exc.response.status_code})")
    except Exception as exc:
        print(f"gemma: failed ({type(exc).__name__})")


if __name__ == "__main__":
    asyncio.run(main())
