from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db

router = APIRouter(tags=["catalog"])
Db = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.get("/species")
async def supported_species(db: Db):
    species = await db.species.find({"supported": True}).sort("common_name", 1).to_list(None)
    return [
        {
            "id": item["_id"],
            "common_name": item["common_name"],
            "scientific_name": item["scientific_name"],
            "category": item["category"],
        }
        for item in species
    ]
