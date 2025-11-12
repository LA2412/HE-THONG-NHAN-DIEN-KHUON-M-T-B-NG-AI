"""
Service layer for product and category management backed by MongoDB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId

from src.data.db import get_collection
from src.services.user_service import log_activity

CATEGORIES = get_collection("categories")
PRODUCTS = get_collection("products")
INVENTORY = get_collection("inventory_movements")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _serialize(doc) -> Dict:
    if not doc:
        return {}
    result = dict(doc)
    result["id"] = str(doc["_id"])
    result.pop("_id", None)
    if "category_id" in result and isinstance(result["category_id"], ObjectId):
        result["category_id"] = str(result["category_id"])
    return result


def create_category(name: str, description: str = "") -> str:
    now = _now_iso()
    result = CATEGORIES.insert_one(
        {
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(result.inserted_id)


def list_categories() -> List[Dict]:
    docs = CATEGORIES.find().sort("name", 1)
    return [_serialize(doc) for doc in docs]


def update_category(category_id: str, **fields) -> None:
    allowed = {"name", "description"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = _now_iso()
    CATEGORIES.update_one({"_id": ObjectId(category_id)}, {"$set": updates})


def delete_category(category_id: str) -> None:
    CATEGORIES.delete_one({"_id": ObjectId(category_id)})


def create_product(
    sku: str,
    name: str,
    price: float,
    stock: int,
    description: str = "",
    category_id: Optional[str] = None,
    image_path: str = "",
    is_active: bool = True,
    user_id: Optional[str] = None,
) -> str:
    now = _now_iso()
    doc = {
        "sku": sku,
        "name": name,
        "description": description,
        "price": float(price),
        "stock": int(stock),
        "category_id": ObjectId(category_id) if category_id else None,
        "image_path": image_path,
        "is_active": bool(is_active),
        "created_at": now,
        "updated_at": now,
    }
    result = PRODUCTS.insert_one(doc)
    inserted_id = str(result.inserted_id)
    if user_id:
        log_activity(user_id, "create_product", f"{inserted_id}:{name}")
    return inserted_id


def update_product(product_id: str, user_id: Optional[str] = None, **fields) -> None:
    allowed = {"name", "description", "price", "stock", "category_id", "image_path", "is_active"}
    updates = {}
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "category_id" and value:
            updates[key] = ObjectId(value)
        else:
            updates[key] = value
    if not updates:
        return
    updates["updated_at"] = _now_iso()
    PRODUCTS.update_one({"_id": ObjectId(product_id)}, {"$set": updates})
    if user_id:
        log_activity(user_id, "update_product", f"{product_id}:{updates.get('name', '')}")


def delete_product(product_id: str, user_id: Optional[str] = None) -> None:
    PRODUCTS.delete_one({"_id": ObjectId(product_id)})
    if user_id:
        log_activity(user_id, "delete_product", str(product_id))


def get_product(product_id: str) -> Optional[Dict]:
    doc = PRODUCTS.find_one({"_id": ObjectId(product_id)})
    return _serialize(doc)


def search_products(keyword: str = "", category_id: Optional[str] = None, only_active: bool = True) -> List[Dict]:
    query = {}
    if keyword:
        regex = {"$regex": keyword, "$options": "i"}
        query["$or"] = [{"sku": regex}, {"name": regex}]
    if category_id:
        query["category_id"] = ObjectId(category_id)
    if only_active:
        query["is_active"] = True

    docs = PRODUCTS.find(query).sort("updated_at", -1)
    categories = {str(cat["_id"]): cat for cat in CATEGORIES.find()}
    results = []
    for doc in docs:
        item = _serialize(doc)
        cat_id = item.get("category_id")
        if cat_id and cat_id in categories:
            item["category_name"] = categories[cat_id]["name"]
        else:
            item["category_name"] = None
        results.append(item)
    return results


def adjust_stock(product_id: str, delta: int, reason: str = "", related_order_id: Optional[str] = None) -> None:
    PRODUCTS.update_one(
        {"_id": ObjectId(product_id)},
        {
            "$inc": {"stock": int(delta)},
            "$set": {"updated_at": _now_iso()},
        },
    )
    INVENTORY.insert_one(
        {
            "product_id": str(product_id),
            "delta": int(delta),
            "reason": reason,
            "related_order_id": related_order_id,
            "created_at": _now_iso(),
        }
    )
