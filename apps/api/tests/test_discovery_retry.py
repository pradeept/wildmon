import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.api.discoveries import retry_discovery
from app.core.rewards import ensure_discovery_xp_index
from app.worker import award_discovery


@pytest.mark.asyncio
async def test_discovery_xp_index_matches_existing_atlas_index():
    class Transactions:
        async def create_index(self, keys, **options):
            assert keys == "discovery_source_id"
            assert options == {
                "unique": True,
                "partialFilterExpression": {"discovery_source_id": {"$exists": True}},
            }

    await ensure_discovery_xp_index(SimpleNamespace(xp_transactions=Transactions()))


@pytest.mark.asyncio
async def test_retry_reuses_failed_discovery_and_job_once():
    item = {
        "_id": "discovery-1",
        "user_id": "owner",
        "status": "failed",
        "guidance": "Unavailable",
        "created_at": datetime(2026, 10, 11, tzinfo=UTC),
    }
    job = {
        "_id": "job-1",
        "kind": "identify",
        "record_id": item["_id"],
        "state": "failed",
        "attempts": 3,
    }

    class Discoveries:
        async def find_one(self, query):
            return (
                item.copy()
                if query.get("_id") == item["_id"] and query.get("user_id") == "owner"
                else None
            )

        async def update_one(self, query, update):
            if query.get("status") == item["status"]:
                item.update(update["$set"])

    class Jobs:
        async def find_one_and_update(self, query, update, **_kwargs):
            if query["state"] != job["state"]:
                return None
            job.update(update["$set"])
            job.pop("last_error", None)
            return job.copy()

    db = SimpleNamespace(discoveries=Discoveries(), processing_jobs=Jobs())
    response = await retry_discovery(item["_id"], {"_id": "owner"}, db)

    assert response["id"] == "discovery-1"
    assert response["status"] == "queued"
    assert job["_id"] == "job-1"
    assert job["attempts"] == 0
    with pytest.raises(HTTPException) as error:
        await retry_discovery(item["_id"], {"_id": "owner"}, db)
    assert error.value.status_code == 409
    assert await db.discoveries.find_one({"_id": item["_id"], "user_id": "stranger"}) is None


@pytest.mark.asyncio
async def test_concurrent_awards_for_same_discovery_create_one_xp_event():
    events = []

    class Transactions:
        async def find_one(self, query):
            for event in events:
                if "discovery_source_id" in query:
                    if event.get("discovery_source_id") == query["discovery_source_id"]:
                        return event
                elif (
                    event["source_id"] == query["source_id"]
                    and event["kind"] in query["kind"]["$in"]
                ):
                    return event
            return None

        async def insert_one(self, event):
            await asyncio.sleep(0)
            if any(
                existing["discovery_source_id"] == event["discovery_source_id"]
                for existing in events
            ):
                raise DuplicateKeyError("duplicate discovery source")
            events.append(event)

    db = SimpleNamespace(xp_transactions=Transactions())
    item = {"_id": "discovery-1", "user_id": "owner"}

    amounts = await asyncio.gather(award_discovery(db, item), award_discovery(db, item))

    assert amounts == [10, 10]
    assert len(events) == 1
    assert events[0]["discovery_source_id"] == "discovery-1"
