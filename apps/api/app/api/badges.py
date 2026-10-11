from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.core.security import User

router = APIRouter(tags=["badges"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.get("/badges")
async def badges(db: Db):
    return await db.badges.find({}, {"_id": 0}).to_list(None)


@router.get("/me/badges")
async def my_badges(user: User, db: Db):
    return await db.user_badges.find({"user_id": user["_id"]}, {"_id": 0}).to_list(None)
