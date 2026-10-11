"""Routes for timed, single-attempt ecosystem challenges."""

from datetime import timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now
from app.domain.packs import close_attempt, finalize_ecosystems, total_units
from app.schemas import EcosystemPackView

router = APIRouter(tags=["ecosystems"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


class StartInput(BaseModel):
    duration_hours: int = Field(ge=1, le=168)


def attempt_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "id": item["_id"],
        "state": item["state"],
        "started_at": item["started_at"],
        "deadline_at": item["deadline_at"],
        "closed_at": item.get("closed_at"),
        "verification_deadline": item.get("verification_deadline"),
        "finalized_at": item.get("finalized_at"),
        "duration_hours": item["duration_hours"],
        "assignments": item.get("assignments", {}),
        "matched_units": item.get("matched_units", len(item.get("assignments", {}))),
        "total_units": item.get("total_units", total_units(item["slots"])),
        "bonus_xp": item.get("bonus_xp", 0),
        "end_reason": item.get("end_reason"),
    }


def pack_view(
    pack: dict[str, Any],
    attempt: dict[str, Any] | None,
    legacy: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": pack["_id"],
        "slug": pack["slug"],
        "title": pack["title"],
        "description": pack["description"],
        "version": pack["version"],
        "slots": pack["slots"],
        "attempt": attempt_view(attempt),
        "legacy_progress": (
            {
                "state": legacy["state"],
                "assignments": legacy.get("assignments", {}),
                "completed_at": legacy.get("completed_at"),
            }
            if legacy
            else None
        ),
    }


async def get_pack_document(slug: str, db: AsyncDatabase[dict[str, Any]]) -> dict[str, Any]:
    pack = await db.ecosystem_packs.find_one({"slug": slug, "active": True})
    if not pack:
        raise HTTPException(404, detail="Ecosystem not found.")
    return pack


async def get_pack_view(
    slug: str, user_id: str, db: AsyncDatabase[dict[str, Any]]
) -> dict[str, Any]:
    pack = await get_pack_document(slug, db)
    attempt = await db.ecosystem_attempts.find_one({"user_id": user_id, "pack_slug": slug})
    legacy = await db.user_pack_progress.find_one(
        {"user_id": user_id, "pack_id": pack["_id"]},
        sort=[("pack_version", -1)],
    )
    return pack_view(pack, attempt, legacy)


@router.get("/ecosystems", response_model=list[EcosystemPackView])
async def list_packs(user: User, db: Db):
    await finalize_ecosystems(db)
    packs = await db.ecosystem_packs.find({"active": True}).to_list(None)
    attempts = await db.ecosystem_attempts.find({"user_id": user["_id"]}).to_list(None)
    legacy = await db.user_pack_progress.find({"user_id": user["_id"]}).to_list(None)
    by_slug = {item["pack_slug"]: item for item in attempts}
    by_pack = {item["pack_id"]: item for item in legacy}
    return [pack_view(pack, by_slug.get(pack["slug"]), by_pack.get(pack["_id"])) for pack in packs]


@router.get("/ecosystems/{slug}", response_model=EcosystemPackView)
async def get_pack(slug: str, user: User, db: Db):
    await finalize_ecosystems(db)
    return await get_pack_view(slug, user["_id"], db)


@router.post("/ecosystems/{slug}/start", response_model=EcosystemPackView, status_code=201)
async def start_pack(slug: str, data: StartInput, user: User, db: Db):
    await finalize_ecosystems(db)
    pack = await get_pack_document(slug, db)
    if await db.ecosystem_attempts.find_one({"user_id": user["_id"], "pack_slug": slug}):
        raise HTTPException(409, detail="You have already attempted this ecosystem.")
    if await db.ecosystem_attempts.find_one({"user_id": user["_id"], "state": "active"}):
        raise HTTPException(409, detail="Finish your active ecosystem first.")
    stamp = now()
    attempt = {
        "_id": uuid4().hex,
        "user_id": user["_id"],
        "pack_slug": slug,
        "pack_id": pack["_id"],
        "pack_version": pack["version"],
        "pack_title": pack["title"],
        "slots": pack["slots"],
        "duration_hours": data.duration_hours,
        "started_at": stamp,
        "deadline_at": stamp + timedelta(hours=data.duration_hours),
        "state": "active",
        "assignments": {},
        "uploads_in_flight": 0,
    }
    try:
        await db.ecosystem_attempts.insert_one(attempt)
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, detail="You already attempted this ecosystem or have an active one."
        ) from exc
    return pack_view(pack, attempt, None)


@router.post("/ecosystems/{slug}/finish", response_model=EcosystemPackView)
async def finish_pack(slug: str, user: User, db: Db):
    attempt = await db.ecosystem_attempts.find_one({"user_id": user["_id"], "pack_slug": slug})
    if not attempt:
        raise HTTPException(404, detail="No ecosystem attempt found.")
    if attempt["state"] == "active":
        await close_attempt(db, attempt["_id"], user["_id"])
    await finalize_ecosystems(db)
    return await get_pack_view(slug, user["_id"], db)


@router.get("/ecosystems/{slug}/results", response_model=EcosystemPackView)
async def pack_results(slug: str, user: User, db: Db):
    await finalize_ecosystems(db)
    return await get_pack_view(slug, user["_id"], db)
