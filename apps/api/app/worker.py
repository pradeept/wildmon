import asyncio
import hashlib
import logging
from datetime import timedelta
from typing import Any

import httpx
from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.ai.image_prep import prepare_model_image
from app.ai.vision import GemmaVisionIdentifier
from app.api.challenges import ensure_hunts
from app.core.config import get_settings
from app.core.rewards import award, issue_badge
from app.core.serializers import now
from app.core.storage import load_image
from app.domain.focus import reconcile_free_hunt
from app.domain.matching import challenge_result
from app.domain.packs import refresh_pack

logger = logging.getLogger("wildmon.worker")


async def award_discovery(db: AsyncDatabase[dict[str, Any]], item: dict[str, Any]) -> int:
    """Award one XP event per discovery, even across concurrent worker claims."""
    user_id, species_id = item["user_id"], item.get("species_id")
    existing = await db.xp_transactions.find_one({"discovery_source_id": item["_id"]})
    if not existing:
        existing = await db.xp_transactions.find_one(
            {
                "source_id": item["_id"],
                "kind": {"$in": ["new_species", "repeat", "category_discovery"]},
            }
        )
    if existing:
        return existing["amount"]

    async def try_award(amount: int, kind: str, key: str) -> int | None:
        """Distinguish a full award slot from another worker awarding this photo."""
        if await award(db, user_id, amount, kind, item["_id"], key, item["_id"]):
            return amount
        winner = await db.xp_transactions.find_one({"discovery_source_id": item["_id"]})
        return winner["amount"] if winner else None

    if species_id:
        first = await try_award(100, "new_species", f"species:{user_id}:{species_id}")
        if first is not None:
            return first
        day = now().date().isoformat()
        for slot in range(2):
            awarded = await try_award(10, "repeat", f"repeat:{user_id}:{species_id}:{day}:{slot}")
            if awarded is not None:
                return awarded
        return 0
    day = now().date().isoformat()
    for slot in range(10):
        awarded = await try_award(10, "category_discovery", f"category:{user_id}:{day}:{slot}")
        if awarded is not None:
            return awarded
    return 0


async def process_identification(db: AsyncDatabase[dict[str, Any]], discovery_id: str) -> None:
    item = await db.discoveries.find_one({"_id": discovery_id})
    if not item:
        return
    if item["status"] == "verified":
        await complete_verified(db, item)
        return
    if item["status"] not in {"queued", "processing", "failed"}:
        return
    settings = get_settings()
    await db.discoveries.update_one({"_id": discovery_id}, {"$set": {"status": "processing"}})
    image, mime = await load_image(item["image_key"], settings)
    digest = hashlib.sha256(image).hexdigest()
    scope = (
        {"session_id": item["session_id"]}
        if item.get("session_id")
        else {"challenge_id": item["challenge_id"]}
        if item.get("challenge_id")
        else None
    )
    if scope:
        duplicate = await db.discoveries.find_one(
            {
                "_id": {"$ne": discovery_id},
                "user_id": item["user_id"],
                **scope,
                "image_hash": digest,
            }
        )
        if duplicate:
            await db.discoveries.update_one(
                {"_id": discovery_id},
                {
                    "$set": {
                        "status": "rejected",
                        "guidance": "This photo is already in this hunt.",
                    }
                },
            )
            return
        try:
            await db.discoveries.update_one({"_id": discovery_id}, {"$set": {"image_hash": digest}})
        except DuplicateKeyError:
            await db.discoveries.update_one(
                {"_id": discovery_id},
                {
                    "$set": {
                        "status": "rejected",
                        "guidance": "This photo is already in this hunt.",
                    }
                },
            )
            return
    catalog = await db.species.find({"supported": True}).to_list(None)
    identifier = GemmaVisionIdentifier(settings)
    model_image, model_mime = await asyncio.to_thread(prepare_model_image, image, mime)
    if len(model_image) < len(image):
        logger.info(
            "Reduced inference image from %d to %d bytes for discovery %s",
            len(image),
            len(model_image),
            discovery_id,
        )
    finding = await identifier.identify(model_image, model_mime, catalog)
    result = finding.model_dump()
    scientific = (finding.scientific_name or "").strip().lower()
    species = next(
        (entry for entry in catalog if entry["scientific_name"].lower() == scientific), None
    )
    category = (
        finding.category
        if finding.category
        in {
            "plant",
            "bird",
            "insect",
            "butterfly",
            "flowering_plant",
            "tree",
        }
        else None
    )
    usable = bool(
        category
        and not finding.insufficient_image
        and not finding.multiple_subjects
        and not finding.unrelated_image
        and finding.candidate_rank != "unknown"
        and not finding.uncertainty.strip()
    )
    status = "verified" if usable else "needs_review"
    if finding.insufficient_image or finding.unrelated_image:
        status = "unidentified"
    traits = []
    if usable:
        desired = sorted(
            {
                requirement["trait_code"]
                for challenge in await db.challenges.find(
                    {"_id": item.get("challenge_id")}
                ).to_list(None)
                for requirement in challenge["requirements"]
                if requirement["kind"] == "visual_trait"
            }
        )
        traits = await identifier.validate_traits(model_image, model_mime, desired)
    categories = [category] if category else []
    if category == "butterfly":
        categories.append("insect")
    if category in {"tree", "flowering_plant"}:
        categories.append("plant")
    update = {
        "status": status,
        "image_hash": digest,
        "ai_result": result,
        "common_name": species["common_name"] if species and usable else finding.common_name,
        "scientific_name": species["scientific_name"]
        if species and usable
        else finding.scientific_name,
        "species_id": species["_id"]
        if species and usable and finding.candidate_rank == "species"
        else None,
        "category": category,
        "categories": categories,
        "traits": traits,
        "uncertainty": finding.uncertainty or None,
        "guidance": ("Try one clear subject in good light." if status != "verified" else None),
        "processed_at": now(),
    }
    changed = await db.discoveries.find_one_and_update(
        {"_id": discovery_id, "status": "processing"},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if changed and status == "verified":
        await complete_verified(db, changed)


async def complete_verified(db: AsyncDatabase[dict[str, Any]], item: dict[str, Any]) -> None:
    """Reconcile idempotent rewards and pack progress after a verified state transition."""
    xp = await award_discovery(db, item)
    await db.discoveries.update_one({"_id": item["_id"]}, {"$set": {"xp_awarded": xp}})
    await issue_badge(db, item["user_id"], "first_discovery")
    if item.get("species_id"):
        for category, count, code in (
            ("plant", 5, "plant_collector"),
            ("bird", 3, "bird_spotter"),
            ("insect", 5, "bug_hunter"),
        ):
            species = await db.discoveries.distinct(
                "species_id",
                {
                    "user_id": item["user_id"],
                    "status": "verified",
                    "categories": category,
                    "species_id": {"$ne": None},
                },
            )
            if len(species) >= count:
                await issue_badge(db, item["user_id"], code)
    packs = await db.ecosystem_packs.find({"active": True}).to_list(None)
    joined = await db.user_pack_progress.find({"user_id": item["user_id"]}).to_list(None)
    joined_keys = {(progress["pack_id"], progress["pack_version"]) for progress in joined}
    for pack in packs:
        if (pack["_id"], pack["version"]) in joined_keys:
            await refresh_pack(db, item["user_id"], pack)


async def claim_job(db: AsyncDatabase[dict[str, Any]]) -> dict[str, Any] | None:
    """Lease long enough for identification and an optional second trait model call."""
    stamp = now()
    lease_seconds = 2 * get_settings().gemma_timeout_seconds + 60
    return await db.processing_jobs.find_one_and_update(
        {
            "state": {"$in": ["queued", "retry", "running"]},
            "available_at": {"$lte": stamp},
            "lease_until": {"$lte": stamp},
        },
        {
            "$set": {"state": "running", "lease_until": stamp + timedelta(seconds=lease_seconds)},
            "$inc": {"attempts": 1},
        },
        sort=[("available_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def run_job(db: AsyncDatabase[dict[str, Any]]) -> bool:
    job = await claim_job(db)
    if not job:
        return False
    logger.info("Claimed %s job %s for record %s", job["kind"], job["_id"], job["record_id"])
    try:
        if job["kind"] == "identify":
            await process_identification(db, job["record_id"])
        await db.processing_jobs.update_one(
            {"_id": job["_id"]}, {"$set": {"state": "completed", "lease_until": now()}}
        )
        logger.info("Completed job %s", job["_id"])
    except Exception as exc:
        attempts = job["attempts"]
        terminal = attempts >= 3
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
            logger.warning("Job %s attempt %s failed: %s", job["_id"], attempts, exc)
        else:
            logger.exception("Job %s failed", job["_id"])
        await db.processing_jobs.update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "state": "failed" if terminal else "retry",
                    "available_at": now() + timedelta(seconds=min(60, 2**attempts)),
                    "lease_until": now(),
                    "last_error": str(exc)[:300],
                }
            },
        )
        if terminal:
            await db.discoveries.update_one(
                {"_id": job["record_id"], "status": {"$in": ["queued", "processing"]}},
                {
                    "$set": {
                        "status": "failed",
                        "guidance": "Identification is unavailable. Try again later.",
                    }
                },
            )
    return True


async def award_challenge(db: AsyncDatabase[dict[str, Any]], item: dict[str, Any]) -> None:
    result = item["result"]
    ids = [item["inviter_id"], item["invitee_id"]]
    for index, user_id in enumerate(ids):
        if result["scores"][index]:
            await award(
                db,
                user_id,
                40,
                "challenge_participation",
                item["_id"],
                f"challenge:participate:{item['_id']}:{user_id}",
            )
        if result["winner_index"] == index:
            await award(
                db,
                user_id,
                200,
                "challenge_win",
                item["_id"],
                f"challenge:win:{item['_id']}:{user_id}",
            )
            wins = await db.xp_transactions.count_documents(
                {"user_id": user_id, "kind": "challenge_win"}
            )
            for code in ("first_victory", "five_wins" if wins >= 5 else None):
                if code:
                    await issue_badge(db, user_id, code)
        if len(result["matches"][index]) == sum(
            req.get("count", 1) for req in item["requirements"]
        ):
            await award(
                db,
                user_id,
                100,
                "perfect_challenge",
                item["_id"],
                f"challenge:perfect:{item['_id']}:{user_id}",
            )
            await issue_badge(db, user_id, "perfect_hunt")
    await db.challenges.update_one({"_id": item["_id"]}, {"$set": {"rewards_issued": True}})


async def finalize_challenges(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Close expired duels and publish immutable results after bounded evidence processing."""
    stamp = now()
    await db.challenges.update_many(
        {"state": "active", "deadline_at": {"$lte": stamp}},
        {"$set": {"state": "verifying", "verifying_at": stamp}},
    )
    pending = await db.challenges.find({"state": "verifying"}).to_list(None)
    for item in pending:
        await ensure_hunts(item, db)
        captures = await db.challenge_captures.find({"challenge_id": item["_id"]}).to_list(None)
        by_user: list[list[dict[str, Any]]] = []
        missing = False
        for user_id in (item["inviter_id"], item["invitee_id"]):
            allowed = {
                entry["client_capture_id"]
                for entry in captures
                if entry["user_id"] == user_id and entry["created_at"] <= item["deadline_at"]
            }
            if user_id in item.get("locked_capture_ids", {}):
                allowed &= set(item["locked_capture_ids"][user_id])
            evidence = await db.discoveries.find(
                {
                    "challenge_id": item["_id"],
                    "user_id": user_id,
                    "client_capture_id": {"$in": list(allowed)},
                }
            ).to_list(None)
            if len(evidence) < len(allowed) or any(
                entry["status"] in {"queued", "processing"} for entry in evidence
            ):
                missing = True
            by_user.append(
                [
                    {
                        "id": entry["_id"],
                        **{key: value for key, value in entry.items() if key != "_id"},
                    }
                    for entry in evidence
                    if entry["status"] == "verified"
                ]
            )
        earliest = item["verifying_at"] + timedelta(minutes=2)
        timeout = item["verifying_at"] + timedelta(minutes=5)
        if (missing and stamp < timeout) or stamp < earliest:
            continue
        done_at = item.get("done_at", {})
        first_done = (
            done_at.get(item["inviter_id"])
            if done_at.get(item["inviter_id"], stamp) < item["deadline_at"]
            else None
        )
        second_done = (
            done_at.get(item["invitee_id"])
            if done_at.get(item["invitee_id"], stamp) < item["deadline_at"]
            else None
        )
        result = challenge_result(item["requirements"], *by_user, first_done, second_done)
        result["winner_id"] = (
            [item["inviter_id"], item["invitee_id"]][result["winner_index"]]
            if result["winner_index"] is not None
            else None
        )
        finished = await db.challenges.find_one_and_update(
            {"_id": item["_id"], "state": "verifying"},
            {
                "$set": {
                    "state": "completed",
                    "result": result,
                    "finalized_at": stamp,
                    "rewards_issued": False,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if finished:
            await award_challenge(db, finished)
    unfinished = await db.challenges.find({"state": "completed", "rewards_issued": False}).to_list(
        None
    )
    for item in unfinished:
        await award_challenge(db, item)


async def expire_free_hunts(db: AsyncDatabase[dict[str, Any]]) -> None:
    await db.hunt_sessions.update_many(
        {"mode": "free", "state": "active", "deadline_at": {"$lte": now()}},
        {"$set": {"state": "finishing", "ended_at": now()}},
    )
    unfinished = await db.hunt_sessions.find(
        {
            "mode": "free",
            "$or": [
                {"state": "finishing"},
                {"state": "completed", "focus_reward_processed": {"$ne": True}},
            ],
        }
    ).to_list(None)
    for hunt in unfinished:
        await reconcile_free_hunt(db, hunt)


async def worker_loop() -> None:
    """Process durable jobs and deadlines until stopped; fail early if MongoDB is unavailable."""
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
    db = client[settings.mongodb_database]
    try:
        await db.command("ping")
        await db.xp_transactions.create_index(
            "discovery_source_id",
            unique=True,
            partialFilterExpression={"discovery_source_id": {"$type": "string"}},
        )
        pending = await db.processing_jobs.count_documents({"state": {"$in": ["queued", "retry"]}})
        logger.info(
            "Wildmon worker connected to database %s; %s jobs pending",
            settings.mongodb_database,
            pending,
        )
        while True:
            worked = await run_job(db)
            await expire_free_hunts(db)
            await finalize_challenges(db)
            if not worked:
                await asyncio.sleep(2)
    finally:
        await client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
