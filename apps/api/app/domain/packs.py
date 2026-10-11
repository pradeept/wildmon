from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.rewards import award, issue_badge
from app.core.serializers import now
from app.domain.matching import assign


async def refresh_pack(
    db: AsyncDatabase[dict[str, Any]], user_id: str, pack: dict[str, Any]
) -> dict[str, Any]:
    """Backfill or advance one joined pack using all verified collection evidence."""
    evidence = await db.discoveries.find({"user_id": user_id, "status": "verified"}).to_list(None)
    evidence = [
        {"id": item["_id"], **{k: v for k, v in item.items() if k != "_id"}} for item in evidence
    ]
    assignments = assign(pack["slots"], evidence)
    total_units = sum(slot.get("count", 1) for slot in pack["slots"])
    complete = len(assignments) == total_units
    stamp = now()
    previous = await db.user_pack_progress.find_one(
        {
            "user_id": user_id,
            "pack_id": pack["_id"],
            "pack_version": pack["version"],
        }
    )
    if previous is None:
        raise ValueError("Pack must be joined before progress is updated")
    completed_at = previous.get("completed_at") or stamp
    progress = await db.user_pack_progress.find_one_and_update(
        {"user_id": user_id, "pack_id": pack["_id"], "pack_version": pack["version"]},
        {
            "$set": {
                "assignments": assignments,
                "state": "completed" if complete else "in_progress",
                "updated_at": stamp,
                **({"completed_at": completed_at} if complete else {}),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if complete:
        await award(
            db,
            user_id,
            300,
            "pack_complete",
            pack["_id"],
            f"pack:{user_id}:{pack['_id']}:{pack['version']}",
        )
        await issue_badge(db, user_id, "ecosystem_explorer")
        completed = await db.user_pack_progress.distinct(
            "pack_id", {"user_id": user_id, "state": "completed"}
        )
        if len(completed) >= 3:
            await issue_badge(db, user_id, "all_three_packs")
    return progress
