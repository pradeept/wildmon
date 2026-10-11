"""Conservative, server-timed focus rewards for completed free hunts."""

from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.rewards import award, issue_badge
from app.core.serializers import now

FOCUS_SIGNAL_GRACE = timedelta(minutes=2)


def estimated_focus_seconds(hunt: dict[str, Any], end: Any) -> int:
    """Count paired app-hidden intervals; an unpaired hidden signal proves no duration."""
    hidden_at = None
    total = 0
    for signal in hunt.get("focus_signals", []):
        at = signal["received_at"]
        if signal["kind"] == "visible" and hidden_at is not None:
            total += max(0, int((min(at, end) - hidden_at).total_seconds()))
            hidden_at = None
        elif at > end:
            break
        elif signal["kind"] in {"hidden", "pagehide"} and hidden_at is None:
            hidden_at = at
    return total


def has_open_hidden_interval(hunt: dict[str, Any], end: Any) -> bool:
    """Detect a final hidden signal that could still be closed during grace."""
    hidden = False
    for signal in hunt.get("focus_signals", []):
        if signal["received_at"] > end:
            if signal["kind"] == "visible":
                hidden = False
            break
        if signal["kind"] in {"hidden", "pagehide"}:
            hidden = True
        elif signal["kind"] == "visible":
            hidden = False
    return hidden


def focus_seconds(hunt: dict[str, Any], photo_count: int) -> int:
    """Exempt one minute per photo and one minute to finish the hunt."""
    end = min(hunt.get("ended_at") or now(), hunt["deadline_at"])
    return max(0, estimated_focus_seconds(hunt, end) - 60 * photo_count - 60)


def focus_tier(seconds: int) -> int:
    if seconds >= 1200:
        return 100
    if seconds >= 600:
        return 60
    if seconds >= 300:
        return 25
    return 0


async def reconcile_free_hunt(db: AsyncDatabase[dict[str, Any]], hunt: dict[str, Any]) -> None:
    """Complete a hunt after inference and issue any eligible bonus once via the XP ledger.

    The worker retries completed hunts with no reward marker after a crash. XP is
    checked by hunt source ID before another daily slot is consumed.
    """
    if hunt["state"] not in {"finishing", "completed"}:
        return
    items = await db.discoveries.find(
        {"session_id": hunt["_id"], "user_id": hunt["user_id"]}
    ).to_list(None)
    if any(item["status"] in {"queued", "processing"} for item in items):
        return
    if hunt["state"] == "finishing":
        await db.hunt_sessions.update_one(
            {"_id": hunt["_id"], "state": "finishing"}, {"$set": {"state": "completed"}}
        )
    if hunt.get("focus_reward_processed"):
        return
    end = min(hunt.get("ended_at") or now(), hunt["deadline_at"])
    if has_open_hidden_interval(hunt, end) and now() < end + FOCUS_SIGNAL_GRACE:
        return
    prior = await db.xp_transactions.find_one({"source_id": hunt["_id"], "kind": "focus"})
    bonus = prior["amount"] if prior else 0
    seconds = focus_seconds(hunt, len(items))
    tier = focus_tier(seconds)
    if not prior and tier and len(hunt.get("focus_signals", [])) >= 2:
        if any(item["status"] == "verified" for item in items):
            day = (hunt.get("ended_at") or now()).date().isoformat()
            for slot in range(3):
                if await award(
                    db,
                    hunt["user_id"],
                    tier,
                    "focus",
                    hunt["_id"],
                    f"focus:{hunt['user_id']}:{day}:{slot}",
                ):
                    bonus = tier
                    break
    if bonus == 100:
        top_hunts = await db.xp_transactions.count_documents(
            {"user_id": hunt["user_id"], "kind": "focus", "amount": 100}
        )
        if top_hunts >= 3:
            await issue_badge(db, hunt["user_id"], "pocket_explorer")
    await db.hunt_sessions.update_one(
        {"_id": hunt["_id"]},
        {"$set": {"focus_reward_processed": True, "focus_xp_awarded": bonus}},
    )
