from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.core.db import get_db

password_hash = PasswordHash.recommended()
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def make_session(user_id: str) -> tuple[str, str]:
    csrf = token_urlsafe(24)
    token = jwt.encode(
        {"sub": user_id, "csrf": csrf, "exp": datetime.now(UTC) + timedelta(days=7)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    return token, csrf


def set_session_cookies(response: Response, user_id: str) -> None:
    token, csrf = make_session(user_id)
    secure = get_settings().web_origin.startswith("https://")
    response.set_cookie(
        "wildmon_session", token, httponly=True, secure=secure, samesite="lax", max_age=604800
    )
    response.set_cookie(
        "wildmon_csrf", csrf, httponly=False, secure=secure, samesite="lax", max_age=604800
    )


async def current_user(
    request: Request, db: Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]
) -> dict[str, Any]:
    token = request.cookies.get("wildmon_session")
    if not token:
        raise HTTPException(
            401, detail={"code": "auth_required", "message": "Sign in to continue."}
        )
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            401, detail={"code": "invalid_session", "message": "Sign in again."}
        ) from exc
    if request.method not in SAFE_METHODS and request.headers.get("x-csrf-token") != payload.get(
        "csrf"
    ):
        raise HTTPException(
            403, detail={"code": "csrf_failed", "message": "Refresh the page and try again."}
        )
    user = await db.users.find_one({"_id": payload["sub"]})
    if not user:
        raise HTTPException(401, detail={"code": "invalid_session", "message": "Sign in again."})
    return user


User = Annotated[dict[str, Any], Depends(current_user)]


async def optional_user(
    request: Request, db: Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]
) -> dict[str, Any] | None:
    token = request.cookies.get("wildmon_session")
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return await db.users.find_one({"_id": payload.get("sub")})
