"""
Customer management utilities backed by MongoDB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId

from src.data.db import get_collection
from src.services.user_service import log_activity

CUSTOMERS = get_collection("customers")
RECOGNITION_EVENTS = get_collection("recognition_events")
ORDERS = get_collection("orders")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _serialize(doc) -> Dict:
    if not doc:
        return {}
    result = dict(doc)
    result["id"] = str(doc["_id"])
    result.pop("_id", None)
    return result


def create_customer(
    full_name: str,
    gender: str = "",
    phone: str = "",
    email: str = "",
    notes: str = "",
    face_id: Optional[int] = None,
) -> str:
    now = _now_iso()
    doc = {
        "full_name": full_name,
        "gender": gender,
        "phone": phone,
        "email": email,
        "notes": notes,
        "face_id": face_id,
        "total_spend": 0.0,
        "visit_count": 0,
        "last_visit": None,
        "first_seen": now,
        "updated_at": now,
    }
    result = CUSTOMERS.insert_one(doc)
    return str(result.inserted_id)


def update_customer(customer_id: str, **fields) -> None:
    allowed = {"full_name", "gender", "phone", "email", "notes", "face_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = _now_iso()
    CUSTOMERS.update_one({"_id": ObjectId(customer_id)}, {"$set": updates})


def get_customer_by_face_id(face_id: int) -> Optional[Dict]:
    doc = CUSTOMERS.find_one({"face_id": face_id})
    return _serialize(doc)


def get_customer(customer_id: str) -> Optional[Dict]:
    doc = CUSTOMERS.find_one({"_id": ObjectId(customer_id)})
    return _serialize(doc)


def list_customers(keyword: str = "") -> List[Dict]:
    query = {}
    if keyword:
        regex = {"$regex": keyword, "$options": "i"}
        query["$or"] = [{"full_name": regex}, {"phone": regex}]
    docs = CUSTOMERS.find(query).sort("last_visit", -1)
    return [_serialize(doc) for doc in docs]


def log_recognition_event(
    customer_id: Optional[str],
    staff_id: Optional[str],
    confidence: float,
    camera_id: str,
) -> None:
    now = _now_iso()
    RECOGNITION_EVENTS.insert_one(
        {
            "customer_id": customer_id,
            "staff_id": staff_id,
            "camera_id": camera_id,
            "confidence": float(confidence),
            "recognized_at": now,
        }
    )
    if customer_id:
        CUSTOMERS.update_one(
            {"_id": ObjectId(customer_id)},
            {
                "$inc": {"visit_count": 1},
                "$set": {"last_visit": now, "updated_at": now},
            },
        )


def record_purchase(customer_id: Optional[str], order_id: str, total_amount: float) -> None:
    if not customer_id:
        return
    now = _now_iso()
    CUSTOMERS.update_one(
        {"_id": ObjectId(customer_id)},
        {
            "$inc": {"total_spend": float(total_amount)},
            "$set": {"last_visit": now, "updated_at": now},
        },
    )


def merge_customers(primary_id: str, duplicate_id: str, user_id: Optional[str] = None) -> None:
    if primary_id == duplicate_id:
        return
    ORDERS.update_many({"customer_id": duplicate_id}, {"$set": {"customer_id": primary_id}})
    RECOGNITION_EVENTS.update_many({"customer_id": duplicate_id}, {"$set": {"customer_id": primary_id}})
    CUSTOMERS.delete_one({"_id": ObjectId(duplicate_id)})
    if user_id:
        log_activity(user_id, "merge_customers", f"{duplicate_id} -> {primary_id}")


def unlink_face(face_id: int) -> None:
    CUSTOMERS.update_many({"face_id": face_id}, {"$set": {"face_id": None}})


def recognition_history(limit: int = 200) -> List[Dict]:
    docs = RECOGNITION_EVENTS.find().sort("recognized_at", -1).limit(limit)
    customer_map = {str(c["_id"]): c for c in CUSTOMERS.find()}
    results = []
    for doc in docs:
        item = dict(doc)
        item["id"] = str(item.pop("_id"))
        cust_id = item.get("customer_id")
        if cust_id and cust_id in customer_map:
            item["customer_name"] = customer_map[cust_id].get("full_name")
        else:
            item["customer_name"] = None
        results.append(item)
    return results
