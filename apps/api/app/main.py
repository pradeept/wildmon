from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient

from app.api import (
    auth,
    badges,
    challenges,
    discoveries,
    ecosystems,
    friends,
    hunts,
    leaderboards,
    species,
)
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if (
        settings.web_origin.startswith("https://")
        and settings.jwt_secret == "local-development-only-change-me"
    ):
        raise RuntimeError("Set JWT_SECRET before production startup")
    client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
    app.state.db = client[settings.mongodb_database]
    yield
    await client.close()


app = FastAPI(title="Wildmon API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, exc: HTTPException):
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {
            "code": "http_error",
            "message": str(exc.detail),
        }
    )
    return JSONResponse({"error": detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(part) for part in issue["loc"]), "message": issue["msg"]}
        for issue in exc.errors()
    ]
    return JSONResponse(
        {
            "error": {
                "code": "validation_error",
                "message": "Check the submitted fields.",
                "details": details,
            }
        },
        status_code=422,
    )


@app.get("/api/v1/health", tags=["system"])
async def health(request: Request):
    try:
        await request.app.state.db.command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)


for router in (
    auth.router,
    discoveries.router,
    hunts.router,
    friends.router,
    challenges.router,
    ecosystems.router,
    leaderboards.router,
    badges.router,
    species.router,
):
    app.include_router(router, prefix="/api/v1")
