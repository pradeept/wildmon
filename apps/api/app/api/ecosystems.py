from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now
from app.domain.packs import refresh_pack

router = APIRouter(tags=["ecosystems"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


def pack_view(pack: dict[str, Any], progress: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": pack["_id"],
        "slug": pack["slug"],
        "title": pack["title"],
        "description": pack["description"],
        "version": pack["version"],
        "slots": pack["slots"],
        "progress": (
            {
                "state": progress["state"],
                "assignments": progress.get("assignments", {}),
                "completed_at": progress.get("completed_at"),
            }
            if progress
            else None
        ),
    }


@router.get("/ecosystems")
async def list_packs(user: User, db: Db):
    packs = await db.ecosystem_packs.find({"active": True}).to_list(None)
    progress = await db.user_pack_progress.find({"user_id": user["_id"]}).to_list(None)
    keyed = {(item["pack_id"], item["pack_version"]): item for item in progress}
    return [pack_view(pack, keyed.get((pack["_id"], pack["version"]))) for pack in packs]


@router.get("/ecosystems/{slug}")
async def get_pack(slug: str, user: User, db: Db):
    pack = await db.ecosystem_packs.find_one({"slug": slug, "active": True})
    if not pack:
        raise HTTPException(404)
    progress = await db.user_pack_progress.find_one(
        {
            "user_id": user["_id"],
            "pack_id": pack["_id"],
            "pack_version": pack["version"],
        }
    )
    return pack_view(pack, progress)


@router.post("/ecosystems/{slug}/join")
async def join_pack(slug: str, user: User, db: Db):
    pack = await db.ecosystem_packs.find_one({"slug": slug, "active": True})
    if not pack:
        raise HTTPException(404)
    try:
        await db.user_pack_progress.insert_one(
            {
                "_id": uuid4().hex,
                "user_id": user["_id"],
                "pack_id": pack["_id"],
                "pack_version": pack["version"],
                "state": "in_progress",
                "assignments": {},
                "joined_at": now(),
            }
        )
    except DuplicateKeyError:
        pass
    progress = await refresh_pack(db, user["_id"], pack)
    return pack_view(pack, progress)


@router.get("/ecosystems/{slug}/progress")
async def pack_progress(slug: str, user: User, db: Db):
    return await get_pack(slug, user, db)
