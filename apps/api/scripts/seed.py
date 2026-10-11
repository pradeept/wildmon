import asyncio

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from app.core.config import get_settings

SPECIES = [
    ("azadirachta_indica", "Azadirachta indica", "Neem", "tree"),
    ("ficus_benghalensis", "Ficus benghalensis", "Banyan", "tree"),
    ("hibiscus_rosa_sinensis", "Hibiscus rosa-sinensis", "Hibiscus", "flowering_plant"),
    ("bougainvillea_glabra", "Bougainvillea glabra", "Bougainvillea", "flowering_plant"),
    ("columba_livia", "Columba livia", "Rock pigeon", "bird"),
    ("corvus_splendens", "Corvus splendens", "House crow", "bird"),
    ("passer_domesticus", "Passer domesticus", "House sparrow", "bird"),
    ("danaus_chrysippus", "Danaus chrysippus", "Plain tiger", "butterfly"),
    ("papilio_demoleus", "Papilio demoleus", "Lime butterfly", "butterfly"),
    ("apis_cerana", "Apis cerana", "Asian honey bee", "insect"),
]

PACKS = [
    (
        "backyard-biodiversity",
        "Backyard Biodiversity",
        "Find the life near home.",
        [
            ("flowering_plant", 1, 0),
            ("butterfly", 1, 0),
            ("insect", 1, 0),
            ("bird", 1, 0),
            ("tree", 1, 0),
        ],
    ),
    (
        "urban-wildlife",
        "Urban Wildlife",
        "Spot nature among the streets.",
        [
            ("tree", 1, 0),
            ("bird", 1, 0),
            ("plant", 1, 0),
            ("insect", 1, 0),
            ("flowering_plant", 1, 0),
        ],
    ),
    (
        "garden-life",
        "Garden Life",
        "A closer look at living gardens.",
        [
            ("flowering_plant", 2, 2),
            ("butterfly", 1, 0),
            ("insect", 1, 0),
            ("plant", 1, 0),
            ("tree", 1, 0),
        ],
    ),
]

BADGES = [
    ("first_discovery", "First Discovery"),
    ("plant_collector", "Plant Collector"),
    ("bird_spotter", "Bird Spotter"),
    ("bug_hunter", "Bug Hunter"),
    ("first_victory", "First Victory"),
    ("five_wins", "Five Wins"),
    ("perfect_hunt", "Perfect Hunt"),
    ("ecosystem_explorer", "Ecosystem Explorer"),
    ("all_three_packs", "All Three Packs"),
    ("pocket_explorer", "Pocket Explorer"),
]


async def main() -> None:
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
    db = client[settings.mongodb_database]
    indexes = [
        (db.users, [("username_lower", ASCENDING)], True),
        (db.users, [("email_lower", ASCENDING)], True),
        (db.friendships, [("pair_key", ASCENDING)], True),
        (db.discoveries, [("user_id", ASCENDING), ("client_capture_id", ASCENDING)], True),
        (db.discoveries, [("image_key", ASCENDING)], True),
        (
            db.discoveries,
            [("user_id", ASCENDING), ("session_id", ASCENDING), ("image_hash", ASCENDING)],
            True,
        ),
        (
            db.discoveries,
            [("user_id", ASCENDING), ("challenge_id", ASCENDING), ("image_hash", ASCENDING)],
            True,
        ),
        (db.processing_jobs, [("kind", ASCENDING), ("record_id", ASCENDING)], True),
        (
            db.challenge_captures,
            [("challenge_id", ASCENDING), ("user_id", ASCENDING), ("client_capture_id", ASCENDING)],
            True,
        ),
        (db.hunt_sessions, [("challenge_id", ASCENDING), ("user_id", ASCENDING)], True),
        (
            db.user_pack_progress,
            [("user_id", ASCENDING), ("pack_id", ASCENDING), ("pack_version", ASCENDING)],
            True,
        ),
        (db.xp_transactions, [("idempotency_key", ASCENDING)], True),
        (db.user_badges, [("user_id", ASCENDING), ("code", ASCENDING)], True),
        (db.ecosystem_packs, [("slug", ASCENDING)], True),
        (db.species, [("scientific_name", ASCENDING)], True),
    ]
    for collection, fields, unique in indexes:
        kwargs = {"unique": unique}
        if collection.name == "hunt_sessions":
            kwargs["partialFilterExpression"] = {"challenge_id": {"$exists": True}}
        if collection.name == "discoveries" and fields[-1][0] == "image_hash":
            kwargs["partialFilterExpression"] = {
                fields[1][0]: {"$type": "string"},
                "image_hash": {"$type": "string"},
            }
        await collection.create_index(fields, **kwargs)
    await db.hunt_sessions.create_index([("user_id", ASCENDING), ("started_at", DESCENDING)])
    await db.processing_jobs.create_index([("state", 1), ("available_at", 1), ("lease_until", 1)])
    await db.friendships.create_index([("user_ids", 1), ("status", 1)])
    await db.upload_intents.create_index([("expires_at", 1)], expireAfterSeconds=0)
    await db.challenges.create_index([("state", 1), ("deadline_at", 1)])
    await db.xp_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.discoveries.create_index([("user_id", 1), ("created_at", -1)])
    for identifier, scientific, common, category in SPECIES:
        await db.species.update_one(
            {"_id": identifier},
            {
                "$setOnInsert": {
                    "_id": identifier,
                    "scientific_name": scientific,
                    "common_name": common,
                    "category": category,
                    "supported": False,
                }
            },
            upsert=True,
        )
    for slug, title, description, categories in PACKS:
        slots = [
            {
                "id": f"slot_{index}",
                "kind": "taxon_category",
                "category": category,
                "count": count,
                "distinct_species": distinct,
            }
            for index, (category, count, distinct) in enumerate(categories)
        ]
        await db.ecosystem_packs.update_one(
            {"slug": slug},
            {
                "$setOnInsert": {"_id": slug},
                "$set": {
                    "slug": slug,
                    "title": title,
                    "description": description,
                    "version": 1,
                    "slots": slots,
                    "active": True,
                },
            },
            upsert=True,
        )
    for code, title in BADGES:
        await db.badges.update_one(
            {"code": code}, {"$set": {"code": code, "title": title}}, upsert=True
        )
    await client.close()
    print("Wildmon indexes and provisional catalog seeded.")


if __name__ == "__main__":
    asyncio.run(main())
