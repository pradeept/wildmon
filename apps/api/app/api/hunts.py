from datetime import timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.core.rewards import award, issue_badge
from app.core.security import User
from app.core.serializers import now, public_discovery
from app.schemas import FocusSignal, HuntInput

router = APIRouter(tags=["hunts"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.post("/hunts")
async def start_hunt(data: HuntInput, user: User, db: Db):
    stamp = now()
    hunt = {
        "_id": uuid4().hex,
        "user_id": user["_id"],
        "mode": "free",
        "state": "active",
        "started_at": stamp,
        "deadline_at": stamp + timedelta(minutes=data.duration_minutes),
        "duration_minutes": data.duration_minutes,
        "focus_signals": [],
    }
    await db.hunt_sessions.insert_one(hunt)
    return hunt_view(hunt)


def hunt_view(hunt: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": hunt["_id"],
        "state": hunt["state"],
        "mode": hunt["mode"],
        "started_at": hunt["started_at"],
        "deadline_at": hunt["deadline_at"],
        "ended_at": hunt.get("ended_at"),
        "duration_minutes": hunt["duration_minutes"],
    }


@router.get("/hunts/{hunt_id}")
async def get_hunt(hunt_id: str, user: User, db: Db):
    hunt = await db.hunt_sessions.find_one({"_id": hunt_id, "user_id": user["_id"]})
    if not hunt:
        raise HTTPException(404)
    return hunt_view(hunt)


@router.post("/hunts/{hunt_id}/visibility")
async def visibility(hunt_id: str, data: FocusSignal, user: User, db: Db):
    stamp = now()
    result = await db.hunt_sessions.update_one(
        {"_id": hunt_id, "user_id": user["_id"], "state": "active", "deadline_at": {"$gt": stamp}},
        {"$push": {"focus_signals": {"kind": data.kind, "received_at": stamp}}},
    )
    if not result.modified_count:
        raise HTTPException(409, detail={"code": "hunt_closed", "message": "This hunt has ended."})
    return {"ok": True}


def estimated_focus_seconds(hunt: dict[str, Any], end: Any) -> int:
    """Count only paired app-hidden intervals observed by the server, never missing time."""
    hidden_at = None
    total = 0
    for signal in hunt.get("focus_signals", []):
        at = signal["received_at"]
        if at > end:
            break
        if signal["kind"] in {"hidden", "pagehide"} and hidden_at is None:
            hidden_at = at
        elif signal["kind"] == "visible" and hidden_at is not None:
            total += max(0, int((at - hidden_at).total_seconds()))
            hidden_at = None
    return total


@router.post("/hunts/{hunt_id}/finish")
async def finish_hunt(hunt_id: str, user: User, db: Db):
    stamp = now()
    hunt = await db.hunt_sessions.find_one_and_update(
        {"_id": hunt_id, "user_id": user["_id"], "mode": "free", "state": "active"},
        {"$set": {"state": "finishing", "ended_at": stamp}},
    )
    if not hunt:
        hunt = await db.hunt_sessions.find_one({"_id": hunt_id, "user_id": user["_id"]})
        if not hunt:
            raise HTTPException(404)
    return hunt_view({**hunt, "state": "finishing", "ended_at": hunt.get("ended_at", stamp)})


@router.get("/hunts/{hunt_id}/summary")
async def summary(hunt_id: str, user: User, db: Db):
    hunt = await db.hunt_sessions.find_one({"_id": hunt_id, "user_id": user["_id"]})
    if not hunt:
        raise HTTPException(404)
    items = (
        await db.discoveries.find({"session_id": hunt_id, "user_id": user["_id"]})
        .sort("created_at", 1)
        .to_list(None)
    )
    pending = any(item["status"] in {"queued", "processing"} for item in items)
    end = min(hunt.get("ended_at", now()), hunt["deadline_at"])
    focus_seconds = max(0, estimated_focus_seconds(hunt, end) - 60 * len(items) - 60)
    if not pending and hunt["state"] == "finishing":
        await db.hunt_sessions.update_one(
            {"_id": hunt_id, "state": "finishing"}, {"$set": {"state": "completed"}}
        )
        hunt["state"] = "completed"
        valid = sum(item["status"] == "verified" for item in items)
        tier = (
            100
            if focus_seconds >= 1200
            else 60
            if focus_seconds >= 600
            else 25
            if focus_seconds >= 300
            else 0
        )
        if valid and tier and len(hunt.get("focus_signals", [])) >= 2:
            prior = await db.xp_transactions.find_one({"source_id": hunt_id, "kind": "focus"})
            if not prior:
                day = now().date().isoformat()
                for slot in range(3):
                    if await award(
                        db, user["_id"], tier, "focus", hunt_id, f"focus:{user['_id']}:{day}:{slot}"
                    ):
                        if tier == 100:
                            top_hunts = await db.xp_transactions.count_documents(
                                {
                                    "user_id": user["_id"],
                                    "kind": "focus",
                                    "amount": 100,
                                }
                            )
                            if top_hunts >= 3:
                                await issue_badge(db, user["_id"], "pocket_explorer")
                        break
    return {
        **hunt_view(hunt),
        "pending": pending,
        "estimated_in_app_focus_seconds": focus_seconds,
        "discoveries": [public_discovery(item) for item in items],
        "xp_awarded": sum(item.get("xp_awarded", 0) for item in items),
    }
