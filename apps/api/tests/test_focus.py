from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.domain import focus


def test_focus_counts_only_paired_hidden_intervals():
    start = datetime(2026, 10, 11, 10, tzinfo=UTC)
    hunt = {
        "deadline_at": start + timedelta(minutes=20),
        "ended_at": start + timedelta(minutes=10),
        "focus_signals": [
            {"kind": "hidden", "received_at": start + timedelta(minutes=1)},
            {"kind": "visible", "received_at": start + timedelta(minutes=8)},
            {"kind": "hidden", "received_at": start + timedelta(minutes=9)},
        ],
    }

    assert focus.estimated_focus_seconds(hunt, hunt["ended_at"]) == 420
    assert focus.focus_seconds(hunt, photo_count=1) == 300
    assert focus.focus_tier(300) == 25


def test_visible_signal_after_deadline_closes_interval_at_deadline():
    start = datetime(2026, 10, 11, 10, tzinfo=UTC)
    hunt = {
        "deadline_at": start + timedelta(minutes=10),
        "ended_at": start + timedelta(minutes=10),
        "focus_signals": [
            {"kind": "hidden", "received_at": start + timedelta(minutes=1)},
            {"kind": "visible", "received_at": start + timedelta(minutes=11)},
        ],
    }

    assert focus.estimated_focus_seconds(hunt, hunt["ended_at"]) == 540
    assert focus.has_open_hidden_interval(hunt, hunt["ended_at"]) is False


@pytest.mark.asyncio
async def test_completed_free_hunt_awards_focus_once_without_summary_request(monkeypatch):
    start = datetime(2026, 10, 11, 10, tzinfo=UTC)
    hunt = {
        "_id": "hunt-1",
        "user_id": "user-1",
        "state": "finishing",
        "deadline_at": start + timedelta(minutes=20),
        "ended_at": start + timedelta(minutes=9),
        "focus_signals": [
            {"kind": "hidden", "received_at": start + timedelta(minutes=1)},
            {"kind": "visible", "received_at": start + timedelta(minutes=8)},
        ],
    }
    calls = []

    class Cursor:
        async def to_list(self, _length):
            return [{"status": "verified"}]

    class Discoveries:
        def find(self, _query):
            return Cursor()

    class Hunts:
        async def update_one(self, _query, update):
            hunt.update(update["$set"])

    class Transactions:
        async def find_one(self, _query):
            return None

    async def fake_award(_db, _user_id, amount, _kind, _source_id, _key):
        calls.append(amount)
        return True

    monkeypatch.setattr(focus, "award", fake_award)
    db = SimpleNamespace(
        discoveries=Discoveries(), hunt_sessions=Hunts(), xp_transactions=Transactions()
    )

    await focus.reconcile_free_hunt(db, hunt)
    await focus.reconcile_free_hunt(db, hunt)

    assert hunt["state"] == "completed"
    assert hunt["focus_xp_awarded"] == 25
    assert calls == [25]
