"""Requeue failed identification jobs caused by Gemma HTTP 500 responses.

Run from apps/api after confirming a working model. The default is a dry run;
pass --apply to reset matching jobs and their failed discoveries.
"""

import argparse
import asyncio

from pymongo import AsyncMongoClient

from app.core.config import get_settings
from app.core.serializers import now

GEMMA_500 = r"Gemma HTTP 500|Server error '500 Internal Server Error'"


async def requeue(apply: bool) -> None:
    """Reset only exhausted Gemma 500 jobs whose discovery is still failed."""
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[settings.mongodb_database]
        await db.command("ping")
        jobs = await db.processing_jobs.find(
            {"kind": "identify", "state": "failed", "last_error": {"$regex": GEMMA_500}}
        ).to_list(None)
        eligible = 0
        reset = 0
        for job in jobs:
            discovery = await db.discoveries.find_one({"_id": job["record_id"]})
            if not discovery or discovery.get("status") != "failed":
                continue
            eligible += 1
            if not apply:
                continue
            stamp = now()
            result = await db.processing_jobs.update_one(
                {"_id": job["_id"], "state": "failed"},
                {
                    "$set": {
                        "state": "queued",
                        "attempts": 0,
                        "available_at": stamp,
                        "lease_until": stamp,
                    },
                    "$unset": {"last_error": ""},
                },
            )
            if result.modified_count:
                await db.discoveries.update_one(
                    {"_id": job["record_id"], "status": "failed"},
                    {"$set": {"status": "queued"}, "$unset": {"guidance": ""}},
                )
                reset += 1
        if apply:
            print(f"Requeued {reset} of {eligible} eligible Gemma HTTP 500 jobs.")
        else:
            print(f"Dry run: {eligible} failed Gemma HTTP 500 jobs can be requeued.")
            print("Run with --apply after setting and testing a working GEMMA_MODEL.")
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="requeue matching failed jobs")
    args = parser.parse_args()
    asyncio.run(requeue(args.apply))


if __name__ == "__main__":
    main()
