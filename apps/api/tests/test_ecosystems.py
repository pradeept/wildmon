"""Timed ecosystem scoring and evidence isolation."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.ecosystems import StartInput, start_pack
from app.domain.packs import bonus_for_units, finalize_ecosystems, matched_evidence


@pytest.mark.parametrize(
    ("matched", "total", "expected"),
    [(0, 5, 0), (1, 5, 50), (2, 5, 50), (3, 5, 150), (4, 5, 150), (5, 5, 300)],
)
def test_ecosystem_milestone_is_single_tier(matched, total, expected):
    assert bonus_for_units(matched, total) == expected


def test_ecosystem_duration_requires_whole_hours_in_range():
    assert StartInput(duration_hours=168).duration_hours == 168
    for value in (0, 169, 1.5):
        with pytest.raises(ValidationError):
            StartInput(duration_hours=value)


@pytest.mark.asyncio
async def test_ecosystem_matches_only_bound_verified_photos():
    start = datetime(2026, 10, 12, tzinfo=UTC)
    attempt = {
        "_id": "attempt-1",
        "user_id": "user-1",
        "started_at": start,
        "deadline_at": start + timedelta(hours=1),
        "closed_at": start + timedelta(minutes=20),
        "slots": [
            {
                "id": "flower",
                "kind": "taxon_category",
                "category": "flowering_plant",
                "count": 1,
            }
        ],
    }
    photos = [
        {
            "_id": "eligible",
            "user_id": "user-1",
            "ecosystem_attempt_id": "attempt-1",
            "created_at": start + timedelta(minutes=5),
            "status": "verified",
            "categories": ["flowering_plant"],
        },
        {
            "_id": "ordinary",
            "user_id": "user-1",
            "created_at": start + timedelta(minutes=6),
            "status": "verified",
            "categories": ["flowering_plant"],
        },
        {
            "_id": "late",
            "user_id": "user-1",
            "ecosystem_attempt_id": "attempt-1",
            "created_at": start + timedelta(minutes=21),
            "status": "verified",
            "categories": ["flowering_plant"],
        },
    ]

    class Cursor:
        async def to_list(self, _length):
            return [
                photo
                for photo in photos
                if photo.get("ecosystem_attempt_id") == "attempt-1"
                and photo["user_id"] == "user-1"
                and photo["status"] == "verified"
                and start <= photo["created_at"] <= attempt["closed_at"]
            ]

    class Discoveries:
        def find(self, query):
            assert query["ecosystem_attempt_id"] == "attempt-1"
            assert query["status"] == "verified"
            assert query["created_at"]["$lte"] == attempt["closed_at"]
            return Cursor()

    db = SimpleNamespace(discoveries=Discoveries())
    assert await matched_evidence(db, attempt) == {"flower:0": "eligible"}


@pytest.mark.asyncio
async def test_start_rejects_repeat_and_another_active_attempt(monkeypatch):
    async def no_finalize(_db):
        return None

    monkeypatch.setattr("app.api.ecosystems.finalize_ecosystems", no_finalize)

    class Packs:
        async def find_one(self, _query):
            return {
                "_id": "garden-life",
                "slug": "garden-life",
                "title": "Garden Life",
                "description": "Look nearby.",
                "version": 2,
                "slots": [],
            }

    class Attempts:
        def __init__(self, existing):
            self.existing = existing

        async def find_one(self, query):
            if "pack_slug" in query:
                return self.existing if self.existing == "same" else None
            return self.existing if self.existing == "other" else None

    from fastapi import HTTPException

    for existing, message in (
        ("same", "already attempted"),
        ("other", "active ecosystem"),
    ):
        db = SimpleNamespace(ecosystem_packs=Packs(), ecosystem_attempts=Attempts(existing))
        with pytest.raises(HTTPException, match=message) as error:
            await start_pack("garden-life", StartInput(duration_hours=24), {"_id": "user-1"}, db)
        assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_finalization_waits_for_pending_and_awards_once(monkeypatch):
    stamp = datetime.now(UTC)
    attempt = {
        "_id": "attempt-1",
        "user_id": "user-1",
        "pack_slug": "garden-life",
        "state": "verifying",
        "started_at": stamp - timedelta(hours=1),
        "deadline_at": stamp,
        "closed_at": stamp,
        "verification_deadline": stamp + timedelta(minutes=5),
        "slots": [
            {"id": "flower", "kind": "taxon_category", "category": "flowering_plant", "count": 1}
        ],
        "uploads_in_flight": 0,
    }
    pending = True
    awarded = []

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        async def to_list(self, _length):
            return self.rows

    class Attempts:
        def find(self, query):
            if query["state"] == "verifying":
                return Cursor([attempt] if attempt["state"] == "verifying" else [])
            return Cursor(
                [attempt]
                if attempt["state"] in {"completed", "partial", "missed"}
                and not attempt.get("reward_processed")
                else []
            )

        async def find_one_and_update(self, query, update):
            if attempt["_id"] == query["_id"] and attempt["state"] == query["state"]:
                attempt.update(update["$set"])
                return attempt
            return None

        async def update_one(self, _query, update):
            attempt.update(update["$set"])

        async def count_documents(self, _query):
            return 1

    class Discoveries:
        async def count_documents(self, _query):
            return 1 if pending else 0

        def find(self, _query):
            return Cursor(
                [
                    {
                        "_id": "photo-1",
                        "status": "verified",
                        "categories": ["flowering_plant"],
                    }
                ]
            )

    async def fake_award(_db, _user, amount, _kind, _source, _key):
        awarded.append(amount)
        return True

    async def fake_badge(_db, _user, _code):
        return None

    monkeypatch.setattr("app.domain.packs.award", fake_award)
    monkeypatch.setattr("app.domain.packs.issue_badge", fake_badge)
    db = SimpleNamespace(ecosystem_attempts=Attempts(), discoveries=Discoveries())
    await finalize_ecosystems(db)
    assert attempt["state"] == "verifying"
    assert not awarded
    pending = False
    await finalize_ecosystems(db)
    await finalize_ecosystems(db)
    assert attempt["state"] == "completed"
    assert attempt["assignments"] == {"flower:0": "photo-1"}
    assert awarded == [300]
