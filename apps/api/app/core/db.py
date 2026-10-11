from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase


def get_db(request: Request) -> AsyncDatabase[dict[str, Any]]:
    return request.app.state.db
