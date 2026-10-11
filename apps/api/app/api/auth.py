from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.db import get_db
from app.core.rewards import total_xp
from app.core.security import User, password_hash, set_session_cookies
from app.core.serializers import now, public_profile
from app.schemas import LoginInput, Profile, ProfileUpdate, RegisterInput

router = APIRouter(tags=["auth"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.post("/auth/register", response_model=Profile)
async def register(data: RegisterInput, response: Response, db: Db):
    user = {
        "_id": uuid4().hex,
        "username": data.username,
        "username_lower": data.username.lower(),
        "email_lower": data.email.lower(),
        "password_hash": password_hash.hash(data.password),
        "public_leaderboard": False,
        "created_at": now(),
    }
    try:
        await db.users.insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, detail={"code": "account_exists", "message": "Username or email is already used."}
        ) from exc
    set_session_cookies(response, user["_id"])
    return public_profile(user)


@router.post("/auth/login", response_model=Profile)
async def login(data: LoginInput, response: Response, db: Db):
    user = await db.users.find_one({"email_lower": data.email.lower()})
    if not user or not password_hash.verify(data.password, user["password_hash"]):
        raise HTTPException(
            401, detail={"code": "invalid_login", "message": "Email or password is incorrect."}
        )
    set_session_cookies(response, user["_id"])
    return public_profile(user, await total_xp(db, user["_id"]))


@router.post("/auth/logout")
async def logout(response: Response, user: User):
    response.delete_cookie("wildmon_session")
    response.delete_cookie("wildmon_csrf")
    return {"ok": True}


@router.get("/me", response_model=Profile)
async def me(user: User, db: Db):
    return public_profile(user, await total_xp(db, user["_id"]))


@router.patch("/me", response_model=Profile)
async def update_me(data: ProfileUpdate, user: User, db: Db):
    if data.public_leaderboard is not None:
        await db.users.update_one(
            {"_id": user["_id"]}, {"$set": {"public_leaderboard": data.public_leaderboard}}
        )
        user["public_leaderboard"] = data.public_leaderboard
    return public_profile(user, await total_xp(db, user["_id"]))


@router.get("/users/{username}", response_model=Profile)
async def profile(username: str, db: Db):
    user = await db.users.find_one({"username_lower": username.lower()})
    if not user:
        raise HTTPException(404, detail={"code": "not_found", "message": "Explorer not found."})
    return public_profile(user, await total_xp(db, user["_id"]))
