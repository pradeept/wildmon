from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db
from app.core.security import User
from app.core.serializers import now
from app.schemas import FriendRequestInput

router = APIRouter(tags=["friends"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


def friend_view(item: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["_id"],
        "user_id": other["_id"],
        "username": other["username"],
        "status": item["status"],
        "requested_by_me": item["requester_id"] != other["_id"],
    }


@router.get("/friends")
async def list_friends(user: User, db: Db):
    items = await db.friendships.find({"user_ids": user["_id"]}).to_list(None)
    others = {
        item["_id"]: item
        for item in await db.users.find(
            {
                "_id": {
                    "$in": [uid for item in items for uid in item["user_ids"] if uid != user["_id"]]
                }
            }
        ).to_list(None)
    }
    return [
        friend_view(item, others[next(uid for uid in item["user_ids"] if uid != user["_id"])])
        for item in items
        if next(uid for uid in item["user_ids"] if uid != user["_id"]) in others
    ]


@router.post("/friends/requests")
async def request_friend(data: FriendRequestInput, user: User, db: Db):
    other = await db.users.find_one({"username_lower": data.username.lower()})
    if not other or other["_id"] == user["_id"]:
        raise HTTPException(404, detail={"code": "not_found", "message": "Explorer not found."})
    pair = sorted([user["_id"], other["_id"]])
    item = {
        "_id": uuid4().hex,
        "user_ids": pair,
        "pair_key": ":".join(pair),
        "requester_id": user["_id"],
        "status": "pending",
        "created_at": now(),
    }
    try:
        await db.friendships.insert_one(item)
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, detail={"code": "already_requested", "message": "Friend request already exists."}
        ) from exc
    return friend_view(item, other)


async def resolve_request(request_id: str, state: str, user: dict[str, Any], db: Db):
    item = await db.friendships.find_one_and_update(
        {
            "_id": request_id,
            "status": "pending",
            "user_ids": user["_id"],
            "requester_id": {"$ne": user["_id"]},
        },
        {"$set": {"status": state, "resolved_at": now()}},
    )
    if not item:
        raise HTTPException(
            409, detail={"code": "invalid_request", "message": "Request unavailable."}
        )
    return {"id": request_id, "status": state}


@router.post("/friends/requests/{request_id}/accept")
async def accept_request(request_id: str, user: User, db: Db):
    return await resolve_request(request_id, "accepted", user, db)


@router.post("/friends/requests/{request_id}/reject")
async def reject_request(request_id: str, user: User, db: Db):
    return await resolve_request(request_id, "rejected", user, db)
