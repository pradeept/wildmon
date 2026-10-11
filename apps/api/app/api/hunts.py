from datetime import timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now, public_discovery
from app.domain.focus import FOCUS_SIGNAL_GRACE, focus_seconds
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
    if data.kind == "visible":
        eligible = {
            "_id": hunt_id,
            "user_id": user["_id"],
            "state": {"$in": ["active", "finishing", "completed"]},
            "deadline_at": {"$gt": stamp - FOCUS_SIGNAL_GRACE},
        }
    else:
        eligible = {
            "_id": hunt_id,
            "user_id": user["_id"],
            "state": "active",
            "deadline_at": {"$gt": stamp},
        }
    result = await db.hunt_sessions.update_one(
        eligible,
        {"$push": {"focus_signals": {"kind": data.kind, "received_at": stamp}}},
    )
    if not result.modified_count:
        raise HTTPException(409, detail={"code": "hunt_closed", "message": "This hunt has ended."})
    return {"ok": True}


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
    return {
        **hunt_view(hunt),
        "pending": pending,
        "estimated_in_app_focus_seconds": focus_seconds(hunt, len(items)),
        "focus_xp_awarded": hunt.get("focus_xp_awarded", 0),
        "focus_reward_processed": hunt.get("focus_reward_processed", False),
        "discoveries": [public_discovery(item) for item in items],
        "xp_awarded": sum(item.get("xp_awarded", 0) for item in items),
    }
