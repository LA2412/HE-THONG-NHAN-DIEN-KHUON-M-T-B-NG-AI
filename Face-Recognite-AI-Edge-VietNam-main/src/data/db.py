"""
MongoDB connection helpers for the retail face-recognition application.
"""

from __future__ import annotations

import os
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


DEFAULT_URI = "mongodb://localhost:27017/deep-face-shop"
MONGO_URI = os.getenv("MONGO_URI", DEFAULT_URI)

_client = MongoClient(MONGO_URI)
_db = _client.get_default_database()
if _db is None:
    # Fall back to database name at end of URI or default string.
    db_name = MONGO_URI.rsplit("/", 1)[-1] or "deep-face-shop"
    _db = _client[db_name]


def get_db() -> Database:
    """Return the MongoDB database instance."""
    return _db


def get_collection(name: str) -> Collection:
    return _db[name]


def ensure_indexes() -> None:
    """Create indexes required for application-level guarantees."""
    users = get_collection("users")
    users.create_index([("username", ASCENDING)], unique=True)
    users.create_index([("role", ASCENDING)])
    users.create_index([("is_active", ASCENDING)])

    login_logs = get_collection("login_logs")
    login_logs.create_index([("timestamp", ASCENDING)])
    login_logs.create_index([("user_id", ASCENDING)])

    activity_logs = get_collection("activity_logs")
    activity_logs.create_index([("created_at", ASCENDING)])
    activity_logs.create_index([("user_id", ASCENDING)])

    categories = get_collection("categories")
    categories.create_index([("name", ASCENDING)], unique=True)

    products = get_collection("products")
    products.create_index([("sku", ASCENDING)], unique=True)
    products.create_index([("name", ASCENDING)])
    products.create_index([("category_id", ASCENDING)])
    products.create_index([("is_active", ASCENDING)])

    customers = get_collection("customers")
    customers.create_index([("face_id", ASCENDING)], unique=True, sparse=True)
    customers.create_index([("phone", ASCENDING)], sparse=True)
    customers.create_index([("full_name", ASCENDING)])

    recognition_events = get_collection("recognition_events")
    recognition_events.create_index([("recognized_at", ASCENDING)])
    recognition_events.create_index([("customer_id", ASCENDING), ("staff_id", ASCENDING)])

    orders = get_collection("orders")
    orders.create_index([("order_number", ASCENDING)], unique=True)
    orders.create_index([("created_at", ASCENDING)])
    orders.create_index([("customer_id", ASCENDING)])
    orders.create_index([("staff_id", ASCENDING)])

    inventory_movements = get_collection("inventory_movements")
    inventory_movements.create_index([("product_id", ASCENDING)])
    inventory_movements.create_index([("created_at", ASCENDING)])


def ping() -> dict[str, Any]:
    """Return MongoDB server status for diagnostics."""
    return _client.admin.command("ping")
