"""Timed ecosystem attempts, evidence matching, and once-only milestone rewards."""

from datetime import timedelta
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.rewards import award, issue_badge
from app.core.serializers import now
from app.domain.matching import assign

VERIFY_GRACE = timedelta(minutes=5)
FINAL_STATES = ("completed", "partial", "missed")


def total_units(slots: list[dict[str, Any]]) -> int:
    return sum(slot.get("count", 1) for slot in slots)


def bonus_for_units(matched: int, total: int) -> int:
    """Return the single completion milestone for a finalized attempt."""
    if matched == 0:
        return 0
    if matched >= total:
        return 300
    return 150 if matched * 2 >= total else 50


async def ensure_ecosystem_indexes(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Enforce one attempt per pack and one active timer per user."""
    await db.ecosystem_attempts.create_index([("user_id", 1), ("pack_slug", 1)], unique=True)
    await db.ecosystem_attempts.create_index(
        "user_id",
        unique=True,
        partialFilterExpression={"state": "active"},
        name="one_active_ecosystem_per_user",
    )
    await db.ecosystem_attempts.create_index([("state", 1), ("deadline_at", 1)])
    await db.discoveries.create_index([("ecosystem_attempt_id", 1), ("status", 1)])
    await db.discoveries.create_index(
        [("user_id", 1), ("ecosystem_attempt_id", 1), ("image_hash", 1)],
        unique=True,
        partialFilterExpression={
            "ecosystem_attempt_id": {"$type": "string"},
            "image_hash": {"$type": "string"},
        },
    )


async def matched_evidence(
    db: AsyncDatabase[dict[str, Any]], attempt: dict[str, Any]
) -> dict[str, str]:
    """Match only verified photos accepted for this attempt before it closed."""
    cutoff = min(attempt.get("closed_at", attempt["deadline_at"]), attempt["deadline_at"])
    rows = await db.discoveries.find(
        {
            "ecosystem_attempt_id": attempt["_id"],
            "user_id": attempt["user_id"],
            "status": "verified",
            "created_at": {"$gte": attempt["started_at"], "$lte": cutoff},
        }
    ).to_list(None)
    return assign(attempt["slots"], [{**row, "id": row["_id"]} for row in rows])


async def refresh_attempt(
    db: AsyncDatabase[dict[str, Any]], attempt_id: str
) -> dict[str, Any] | None:
    """Update provisional progress after an ecosystem photo is verified."""
    attempt = await db.ecosystem_attempts.find_one(
        {"_id": attempt_id, "state": {"$in": ["active", "verifying"]}}
    )
    if not attempt:
        return None
    assignments = await matched_evidence(db, attempt)
    return await db.ecosystem_attempts.find_one_and_update(
        {"_id": attempt_id, "state": {"$in": ["active", "verifying"]}},
        {"$set": {"assignments": assignments, "updated_at": now()}},
        return_document=ReturnDocument.AFTER,
    )


async def close_attempt(
    db: AsyncDatabase[dict[str, Any]], attempt_id: str, user_id: str
) -> dict[str, Any] | None:
    """Stop admission atomically; allow accepted photos five minutes to resolve."""
    stamp = now()
    attempt = await db.ecosystem_attempts.find_one(
        {"_id": attempt_id, "user_id": user_id, "state": "active"}
    )
    if not attempt:
        return None
    closed_at = min(stamp, attempt["deadline_at"])
    return await db.ecosystem_attempts.find_one_and_update(
        {"_id": attempt_id, "user_id": user_id, "state": "active"},
        {
            "$set": {
                "state": "verifying",
                "closed_at": closed_at,
                "verification_deadline": closed_at + VERIFY_GRACE,
                "end_reason": "deadline" if stamp >= attempt["deadline_at"] else "finished",
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def finalize_ecosystems(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Close expired attempts and settle each result and reward idempotently."""
    stamp = now()
    expired = await db.ecosystem_attempts.find(
        {"state": "active", "deadline_at": {"$lte": stamp}}
    ).to_list(None)
    for attempt in expired:
        await db.ecosystem_attempts.find_one_and_update(
            {"_id": attempt["_id"], "state": "active"},
            {
                "$set": {
                    "state": "verifying",
                    "closed_at": attempt["deadline_at"],
                    "verification_deadline": attempt["deadline_at"] + VERIFY_GRACE,
                    "end_reason": "deadline",
                }
            },
        )
    attempts = await db.ecosystem_attempts.find({"state": "verifying"}).to_list(None)
    for attempt in attempts:
        pending = await db.discoveries.count_documents(
            {
                "ecosystem_attempt_id": attempt["_id"],
                "status": {"$in": ["queued", "processing"]},
            }
        )
        if (
            pending + attempt.get("uploads_in_flight", 0) > 0
            and now() < attempt["verification_deadline"]
        ):
            continue
        assignments = await matched_evidence(db, attempt)
        matched = len(assignments)
        total = total_units(attempt["slots"])
        state = "completed" if matched == total else "partial" if matched else "missed"
        await db.ecosystem_attempts.find_one_and_update(
            {"_id": attempt["_id"], "state": "verifying"},
            {
                "$set": {
                    "state": state,
                    "assignments": assignments,
                    "matched_units": matched,
                    "total_units": total,
                    "bonus_xp": bonus_for_units(matched, total),
                    "finalized_at": now(),
                    "reward_processed": False,
                }
            },
        )
    unsettled = await db.ecosystem_attempts.find(
        {"state": {"$in": FINAL_STATES}, "reward_processed": {"$ne": True}}
    ).to_list(None)
    for attempt in unsettled:
        if attempt["bonus_xp"]:
            await award(
                db,
                attempt["user_id"],
                attempt["bonus_xp"],
                "ecosystem_bonus",
                attempt["_id"],
                f"ecosystem:attempt:{attempt['_id']}",
            )
        if attempt["state"] == "completed":
            await issue_badge(db, attempt["user_id"], "ecosystem_explorer")
            completed = await db.ecosystem_attempts.count_documents(
                {"user_id": attempt["user_id"], "state": "completed"}
            )
            if completed >= 3:
                await issue_badge(db, attempt["user_id"], "all_three_packs")
        await db.ecosystem_attempts.update_one(
            {"_id": attempt["_id"]}, {"$set": {"reward_processed": True}}
        )
