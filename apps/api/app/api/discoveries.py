import asyncio
from datetime import timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now, public_discovery
from app.core.storage import (
    MAX_BYTES,
    MIME_EXTENSIONS,
    UPLOAD_DIR,
    make_key,
    s3_client,
    store_local,
)
from app.schemas import Discovery, DiscoveryInput, UploadSignInput, UploadSignOutput

router = APIRouter(tags=["discoveries"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


def image_url(item: dict[str, Any]) -> str:
    return f"/api/v1/discoveries/{item['_id']}/image"


@router.post("/uploads/sign", response_model=UploadSignOutput)
async def sign_upload(data: UploadSignInput, user: User, db: Db):
    key = make_key(data.content_type)
    settings = get_settings()
    await db.upload_intents.insert_one(
        {
            "_id": key,
            "user_id": user["_id"],
            "content_type": data.content_type,
            "expires_at": now() + timedelta(minutes=15),
            "used": False,
        }
    )
    if settings.storage_mode == "local":
        url = f"/api/v1/uploads/{key}"
    else:
        url = await asyncio.to_thread(
            s3_client(settings).generate_presigned_url,
            "put_object",
            Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": data.content_type},
            ExpiresIn=900,
            HttpMethod="PUT",
        )
    return UploadSignOutput(key=key, upload_url=url)


@router.put("/uploads/{key}")
async def upload_local(key: str, request: Request, user: User, db: Db):
    if get_settings().storage_mode != "local":
        raise HTTPException(404)
    intent = await db.upload_intents.find_one(
        {"_id": key, "user_id": user["_id"], "expires_at": {"$gt": now()}}
    )
    if not intent or request.headers.get("content-type") != intent["content_type"]:
        raise HTTPException(
            403, detail={"code": "invalid_upload", "message": "Request a new upload link."}
        )
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > MAX_BYTES:
            raise HTTPException(
                413, detail={"code": "too_large", "message": "Image must be under 6 MB."}
            )
    await store_local(key, bytes(chunks))
    return {"ok": True}


@router.post("/discoveries", response_model=Discovery, status_code=202)
async def create_discovery(data: DiscoveryInput, user: User, db: Db):
    stamp = now()
    existing = await db.discoveries.find_one(
        {"user_id": user["_id"], "client_capture_id": data.client_capture_id}
    )
    if existing:
        await db.processing_jobs.update_one(
            {"kind": "identify", "record_id": existing["_id"]},
            {
                "$setOnInsert": {
                    "_id": uuid4().hex,
                    "kind": "identify",
                    "record_id": existing["_id"],
                    "state": "queued",
                    "attempts": 0,
                    "available_at": stamp,
                    "lease_until": stamp,
                    "created_at": stamp,
                }
            },
            upsert=True,
        )
        return public_discovery(existing, image_url(existing))
    intent = await db.upload_intents.find_one(
        {
            "_id": data.image_key,
            "user_id": user["_id"],
            "expires_at": {"$gt": stamp},
            "used": False,
        }
    )
    if not intent:
        raise HTTPException(
            403, detail={"code": "invalid_upload", "message": "Upload link expired."}
        )
    if data.session_id:
        hunt = await db.hunt_sessions.find_one({"_id": data.session_id, "user_id": user["_id"]})
        if not hunt or hunt["state"] != "active" or hunt["deadline_at"] <= stamp:
            raise HTTPException(
                409, detail={"code": "hunt_closed", "message": "This hunt has ended."}
            )
    if data.challenge_id:
        challenge = await db.challenges.find_one(
            {
                "_id": data.challenge_id,
                "$or": [{"inviter_id": user["_id"]}, {"invitee_id": user["_id"]}],
            }
        )
        registration = await db.challenge_captures.find_one(
            {
                "challenge_id": data.challenge_id,
                "user_id": user["_id"],
                "client_capture_id": data.client_capture_id,
            }
        )
        locked = challenge.get("locked_capture_ids", {}).get(user["_id"], []) if challenge else []
        if (
            not challenge
            or challenge["state"] not in {"active", "verifying"}
            or (
                user["_id"] in challenge.get("done_ids", [])
                and data.client_capture_id not in locked
            )
            or not registration
            or registration["deadline_at"] + timedelta(minutes=2) < stamp
        ):
            raise HTTPException(
                409,
                detail={
                    "code": "capture_not_registered",
                    "message": "Competitive capture window closed.",
                },
            )
    item = {
        "_id": uuid4().hex,
        "user_id": user["_id"],
        "image_key": data.image_key,
        "client_capture_id": data.client_capture_id,
        "session_id": data.session_id,
        "challenge_id": data.challenge_id,
        "status": "queued",
        "created_at": stamp,
    }
    try:
        await db.discoveries.insert_one(item)
    except DuplicateKeyError as exc:
        item = await db.discoveries.find_one(
            {"user_id": user["_id"], "client_capture_id": data.client_capture_id}
        )
        if not item:
            raise HTTPException(
                409,
                detail={"code": "image_used", "message": "This photo has already been submitted."},
            ) from exc
    await db.processing_jobs.update_one(
        {"kind": "identify", "record_id": item["_id"]},
        {
            "$setOnInsert": {
                "_id": uuid4().hex,
                "kind": "identify",
                "record_id": item["_id"],
                "state": "queued",
                "attempts": 0,
                "available_at": stamp,
                "lease_until": stamp,
                "created_at": stamp,
            }
        },
        upsert=True,
    )
    await db.upload_intents.update_one({"_id": data.image_key}, {"$set": {"used": True}})
    return public_discovery(item, image_url(item))


@router.get("/discoveries", response_model=list[Discovery])
async def list_discoveries(user: User, db: Db, limit: int = 30):
    items = (
        await db.discoveries.find({"user_id": user["_id"]})
        .sort("created_at", -1)
        .limit(min(limit, 100))
        .to_list(None)
    )
    return [public_discovery(item, image_url(item)) for item in items]


@router.get("/collection", response_model=list[Discovery])
async def collection(user: User, db: Db):
    items = (
        await db.discoveries.find({"user_id": user["_id"], "status": "verified"})
        .sort("created_at", -1)
        .to_list(None)
    )
    return [public_discovery(item, image_url(item)) for item in items]


@router.get("/discoveries/{discovery_id}", response_model=Discovery)
async def get_discovery(discovery_id: str, user: User, db: Db):
    item = await db.discoveries.find_one({"_id": discovery_id, "user_id": user["_id"]})
    if not item:
        raise HTTPException(404)
    return public_discovery(item, image_url(item))


@router.get("/discoveries/{discovery_id}/image")
async def get_image(discovery_id: str, user: User, db: Db):
    item = await db.discoveries.find_one({"_id": discovery_id, "user_id": user["_id"]})
    if not item:
        raise HTTPException(404)
    settings = get_settings()
    if settings.storage_mode == "local":
        path = UPLOAD_DIR / item["image_key"]
        if not path.exists():
            raise HTTPException(404)
        mime = next(
            (name for name, ext in MIME_EXTENSIONS.items() if path.suffix == "." + ext),
            "image/jpeg",
        )
        return FileResponse(path, media_type=mime)
    url = await asyncio.to_thread(
        s3_client(settings).generate_presigned_url,
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": item["image_key"]},
        ExpiresIn=120,
    )
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url)
