from types import SimpleNamespace

import pytest

from app.core.rewards import total_xp


@pytest.mark.asyncio
@pytest.mark.parametrize("rows,expected", [([{"total": 125}], 125), ([], 0)])
async def test_total_xp_awaits_async_aggregate_before_reading_cursor(rows, expected):
    class Cursor:
        async def to_list(self, length):
            assert length == 1
            return rows

    class Collection:
        async def aggregate(self, pipeline):
            assert pipeline[0] == {"$match": {"user_id": "player"}}
            return Cursor()

    db = SimpleNamespace(xp_transactions=Collection())
    assert await total_xp(db, "player") == expected
