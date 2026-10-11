import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import boto3
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings

MAX_BYTES = 6 * 1024 * 1024
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
MIME_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def make_key(mime_type: str) -> str:
    return f"{uuid4().hex}.{MIME_EXTENSIONS[mime_type]}"


def s3_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        region_name=settings.s3_region,
    )


async def store_local(key: str, data: bytes) -> None:
    if len(data) > MAX_BYTES:
        raise HTTPException(
            413, detail={"code": "too_large", "message": "Image must be under 6 MB."}
        )
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            if image.width < 320 or image.height < 320 or image.width * image.height > 25_000_000:
                raise ValueError("Invalid image dimensions")
    except (UnidentifiedImageError, ValueError) as exc:
        raise HTTPException(
            422, detail={"code": "invalid_image", "message": "Choose a clear photo."}
        ) from exc
    UPLOAD_DIR.mkdir(exist_ok=True)
    await asyncio.to_thread((UPLOAD_DIR / key).write_bytes, data)


async def load_image(key: str, settings: Settings) -> tuple[bytes, str]:
    if "/" in key or ".." in key:
        raise ValueError("Invalid object key")
    mime = next(
        (name for name, extension in MIME_EXTENSIONS.items() if key.endswith("." + extension)), None
    )
    if not mime:
        raise ValueError("Unsupported image type")
    if settings.storage_mode == "local":
        return await asyncio.to_thread((UPLOAD_DIR / key).read_bytes), mime
    obj = await asyncio.to_thread(
        s3_client(settings).get_object, Bucket=settings.s3_bucket, Key=key
    )
    if obj.get("ContentLength", 0) > MAX_BYTES:
        raise ValueError("Image exceeds upload limit")
    return await asyncio.to_thread(obj["Body"].read), mime
