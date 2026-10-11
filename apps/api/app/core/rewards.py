from typing import Any
from uuid import uuid4

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.serializers import now


async def award(
    db: AsyncDatabase[dict[str, Any]],
    user_id: str,
    amount: int,
    kind: str,
    source_id: str,
    key: str,
) -> bool:
    """Insert one immutable XP event; its unique key makes retries safe.

    Leaderboards aggregate this ledger rather than a separately updated counter, so
    a worker crash cannot leave the visible total out of sync.
    """
    try:
        await db.xp_transactions.insert_one(
            {
                "_id": uuid4().hex,
                "user_id": user_id,
                "amount": amount,
                "kind": kind,
                "source_id": source_id,
                "idempotency_key": key,
                "day": now().date().isoformat(),
                "created_at": now(),
            }
        )
        return True
    except DuplicateKeyError:
        return False


async def total_xp(db: AsyncDatabase[dict[str, Any]], user_id: str) -> int:
    cursor = await db.xp_transactions.aggregate(
        [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
    )
    rows = await cursor.to_list(1)
    return rows[0]["total"] if rows else 0


async def issue_badge(db: AsyncDatabase[dict[str, Any]], user_id: str, code: str) -> None:
    await db.user_badges.update_one(
        {"user_id": user_id, "code": code},
        {"$setOnInsert": {"user_id": user_id, "code": code, "earned_at": now()}},
        upsert=True,
    )
