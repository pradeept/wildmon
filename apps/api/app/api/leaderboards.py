from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.core.security import optional_user
from app.core.serializers import now

router = APIRouter(tags=["leaderboards"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.get("/leaderboards")
async def leaderboard(
    user: Annotated[dict[str, Any] | None, Depends(optional_user)],
    db: Db,
    scope: Literal["friends", "global"] = "global",
    period: Literal["weekly", "all-time"] = "weekly",
    page: int = 1,
):
    if scope == "friends":
        if user is None:
            raise HTTPException(
                401, detail={"code": "auth_required", "message": "Sign in to view friends."}
            )
        friends = await db.friendships.find(
            {"user_ids": user["_id"], "status": "accepted"}
        ).to_list(None)
        ids = [
            user["_id"],
            *[next(uid for uid in item["user_ids"] if uid != user["_id"]) for item in friends],
        ]
        users = await db.users.find({"_id": {"$in": ids}}).to_list(None)
    else:
        users = await db.users.find({"public_leaderboard": True}).limit(500).to_list(None)
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=start.weekday())
    entries = []
    for candidate in users:
        xp_filter = {"user_id": candidate["_id"]}
        if period == "weekly":
            xp_filter["created_at"] = {"$gte": start}
        tx = await db.xp_transactions.find(xp_filter).to_list(None)
        species = await db.discoveries.distinct(
            "species_id",
            {
                "user_id": candidate["_id"],
                "status": "verified",
                "species_id": {"$ne": None},
            },
        )
        entries.append(
            {
                "user_id": candidate["_id"],
                "username": candidate["username"],
                "xp": sum(item["amount"] for item in tx),
                "unique_species": len(species),
                "first_earned_at": min(
                    (item["created_at"] for item in tx), default=candidate["created_at"]
                ),
            }
        )
    entries.sort(
        key=lambda item: (
            -item["xp"],
            -item["unique_species"],
            item["first_earned_at"],
            item["user_id"],
        )
    )
    start_index = max(page - 1, 0) * 20
    return {
        "scope": scope,
        "period": period,
        "page": page,
        "total": len(entries),
        "entries": [{"rank": index + 1, **entry} for index, entry in enumerate(entries)][
            start_index : start_index + 20
        ],
    }
