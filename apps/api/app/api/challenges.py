from datetime import timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now
from app.schemas import CaptureRegistration, ChallengeInput

router = APIRouter(tags=["challenges"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


def view(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["_id"],
        "inviter_id": item["inviter_id"],
        "invitee_id": item["invitee_id"],
        "requirements": item["requirements"],
        "duration_minutes": item["duration_minutes"],
        "state": item["state"],
        "ready_ids": item.get("ready_ids", []),
        "done_ids": item.get("done_ids", []),
        "started_at": item.get("started_at"),
        "deadline_at": item.get("deadline_at"),
        "result": item.get("result"),
    }


async def participant(challenge_id: str, user: dict[str, Any], db: Db) -> dict[str, Any]:
    item = await db.challenges.find_one(
        {
            "_id": challenge_id,
            "$or": [{"inviter_id": user["_id"]}, {"invitee_id": user["_id"]}],
        }
    )
    if not item:
        raise HTTPException(404)
    return item


@router.post("/challenges")
async def create_challenge(data: ChallengeInput, user: User, db: Db):
    friend = await db.friendships.find_one(
        {"user_ids": sorted([user["_id"], data.friend_id]), "status": "accepted"}
    )
    if not friend:
        raise HTTPException(
            403, detail={"code": "friend_required", "message": "Choose an accepted friend."}
        )
    requirements = [requirement.model_dump() for requirement in data.requirements]
    if (
        len({item["id"] for item in requirements}) != len(requirements)
        or sum(item["count"] for item in requirements) > 8
    ):
        raise HTTPException(
            422,
            detail={
                "code": "invalid_targets",
                "message": "Use unique target IDs and up to 8 total units.",
            },
        )
    species_ids = [item["species_id"] for item in requirements if item["kind"] == "species"]
    if species_ids and await db.species.count_documents(
        {"_id": {"$in": species_ids}, "supported": True}
    ) != len(species_ids):
        raise HTTPException(
            422, detail={"code": "unsupported_species", "message": "Choose supported species."}
        )
    item = {
        "_id": uuid4().hex,
        "inviter_id": user["_id"],
        "invitee_id": data.friend_id,
        "requirements": requirements,
        "duration_minutes": data.duration_minutes,
        "state": "invited",
        "ready_ids": [],
        "done_ids": [],
        "created_at": now(),
    }
    await db.challenges.insert_one(item)
    return view(item)


@router.get("/challenges")
async def list_challenges(user: User, db: Db):
    items = (
        await db.challenges.find(
            {"$or": [{"inviter_id": user["_id"]}, {"invitee_id": user["_id"]}]}
        )
        .sort("created_at", -1)
        .limit(50)
        .to_list(None)
    )
    return [view(item) for item in items]


@router.get("/challenges/{challenge_id}")
async def get_challenge(challenge_id: str, user: User, db: Db):
    return view(await participant(challenge_id, user, db))


@router.post("/challenges/{challenge_id}/accept")
async def accept(challenge_id: str, user: User, db: Db):
    item = await db.challenges.find_one_and_update(
        {"_id": challenge_id, "invitee_id": user["_id"], "state": "invited"},
        {"$set": {"state": "accepted", "accepted_at": now()}},
        return_document=ReturnDocument.AFTER,
    )
    if not item:
        raise HTTPException(
            409, detail={"code": "invalid_state", "message": "Invitation is unavailable."}
        )
    return view(item)


@router.post("/challenges/{challenge_id}/decline")
async def decline(challenge_id: str, user: User, db: Db):
    item = await db.challenges.find_one_and_update(
        {"_id": challenge_id, "invitee_id": user["_id"], "state": "invited"},
        {"$set": {"state": "declined", "declined_at": now()}},
        return_document=ReturnDocument.AFTER,
    )
    if not item:
        raise HTTPException(409)
    return view(item)


async def ensure_hunts(item: dict[str, Any], db: Db) -> None:
    """Create participant sessions idempotently after the atomic shared start."""
    for user_id in (item["inviter_id"], item["invitee_id"]):
        await db.hunt_sessions.update_one(
            {"challenge_id": item["_id"], "user_id": user_id},
            {
                "$setOnInsert": {
                    "_id": uuid4().hex,
                    "challenge_id": item["_id"],
                    "user_id": user_id,
                    "mode": "challenge",
                    "state": "active",
                    "started_at": item["started_at"],
                    "deadline_at": item["deadline_at"],
                    "duration_minutes": item["duration_minutes"],
                    "focus_signals": [],
                }
            },
            upsert=True,
        )


@router.post("/challenges/{challenge_id}/ready")
async def ready(challenge_id: str, user: User, db: Db):
    item = await participant(challenge_id, user, db)
    if item["state"] == "active":
        await ensure_hunts(item, db)
        return view(item)
    if item["state"] not in {"accepted", "ready_wait"}:
        raise HTTPException(
            409, detail={"code": "invalid_state", "message": "Challenge is not ready."}
        )
    await db.challenges.update_one(
        {"_id": challenge_id, "state": {"$in": ["accepted", "ready_wait"]}},
        {"$addToSet": {"ready_ids": user["_id"]}, "$set": {"state": "ready_wait"}},
    )
    item = await db.challenges.find_one({"_id": challenge_id})
    if len(item["ready_ids"]) == 2:
        stamp = now()
        started = await db.challenges.find_one_and_update(
            {
                "_id": challenge_id,
                "state": "ready_wait",
                "ready_ids": {"$all": [item["inviter_id"], item["invitee_id"]]},
            },
            {
                "$set": {
                    "state": "active",
                    "started_at": stamp,
                    "deadline_at": stamp + timedelta(minutes=item["duration_minutes"]),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        item = started or await db.challenges.find_one({"_id": challenge_id})
        if item["state"] == "active":
            await ensure_hunts(item, db)
    return view(item)


@router.post("/challenges/{challenge_id}/captures")
async def register_capture(challenge_id: str, data: CaptureRegistration, user: User, db: Db):
    item = await participant(challenge_id, user, db)
    stamp = now()
    if (
        item["state"] != "active"
        or stamp >= item["deadline_at"]
        or user["_id"] in item.get("done_ids", [])
    ):
        raise HTTPException(
            409, detail={"code": "challenge_closed", "message": "Capture window closed."}
        )
    entry = {
        "_id": uuid4().hex,
        "challenge_id": challenge_id,
        "user_id": user["_id"],
        "client_capture_id": data.client_capture_id,
        "created_at": stamp,
        "deadline_at": item["deadline_at"],
    }
    try:
        await db.challenge_captures.insert_one(entry)
    except DuplicateKeyError:
        entry = await db.challenge_captures.find_one(
            {
                "challenge_id": challenge_id,
                "user_id": user["_id"],
                "client_capture_id": data.client_capture_id,
            }
        )
    return {"id": entry["_id"], "registered_at": entry["created_at"]}


@router.post("/challenges/{challenge_id}/done")
async def done(challenge_id: str, user: User, db: Db):
    item = await participant(challenge_id, user, db)
    if item["state"] not in {"active", "verifying"}:
        raise HTTPException(
            409, detail={"code": "invalid_state", "message": "Challenge is not active."}
        )
    if user["_id"] in item.get("done_ids", []):
        return view(item)
    stamp = now()
    captures = await db.challenge_captures.find(
        {"challenge_id": challenge_id, "user_id": user["_id"]}
    ).to_list(None)
    await db.challenges.update_one(
        {"_id": challenge_id, "state": "active", "done_ids": {"$ne": user["_id"]}},
        {
            "$addToSet": {"done_ids": user["_id"]},
            "$set": {
                f"done_at.{user['_id']}": stamp,
                f"locked_capture_ids.{user['_id']}": [
                    capture["client_capture_id"] for capture in captures
                ],
            },
        },
    )
    item = await db.challenges.find_one({"_id": challenge_id})
    if len(item.get("done_ids", [])) == 2:
        await db.challenges.update_one(
            {"_id": challenge_id, "state": "active"},
            {"$set": {"state": "verifying", "verifying_at": stamp}},
        )
        item["state"] = "verifying"
    return view(item)


@router.get("/challenges/{challenge_id}/results")
async def results(challenge_id: str, response: Response, user: User, db: Db):
    item = await participant(challenge_id, user, db)
    if item["state"] != "completed":
        response.status_code = 202
        return {"state": item["state"], "result": None}
    return {"state": "completed", "result": item["result"]}
