from datetime import UTC, datetime
from typing import Any


def now() -> datetime:
    return datetime.now(UTC)


def public_profile(user: dict[str, Any], xp: int = 0) -> dict[str, Any]:
    return {
        "id": user["_id"],
        "username": user["username"],
        "xp": xp,
        "public_leaderboard": user.get("public_leaderboard", False),
    }


def public_discovery(discovery: dict[str, Any], image_url: str | None = None) -> dict[str, Any]:
    return {
        "id": discovery["_id"],
        "status": discovery["status"],
        "created_at": discovery["created_at"],
        "image_url": image_url,
        "common_name": discovery.get("common_name"),
        "scientific_name": discovery.get("scientific_name"),
        "category": discovery.get("category"),
        "species_id": discovery.get("species_id"),
        "uncertainty": discovery.get("uncertainty"),
        "guidance": discovery.get("guidance"),
        "xp_awarded": discovery.get("xp_awarded", 0),
        "session_id": discovery.get("session_id"),
    }
