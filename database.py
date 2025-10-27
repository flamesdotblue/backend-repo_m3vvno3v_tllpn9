import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

MONGO_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "app_db")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


def _timestamps(data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        **data,
        "created_at": data.get("created_at", now),
        "updated_at": now,
    }


async def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    payload = _timestamps(data)
    res = await db[collection_name].insert_one(payload)
    saved = await db[collection_name].find_one({"_id": res.inserted_id})
    return saved or {}


async def get_documents(
    collection_name: str,
    filter_dict: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    sort: Optional[List] = None,
) -> List[Dict[str, Any]]:
    db = get_db()
    q = filter_dict or {}
    cursor = db[collection_name].find(q)
    if sort:
        cursor = cursor.sort(sort)
    cursor = cursor.limit(limit)
    return [doc async for doc in cursor]


# expose db for direct access when needed
_db_export = get_db()
db = _db_export
