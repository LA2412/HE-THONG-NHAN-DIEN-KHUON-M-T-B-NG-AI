"""
Order management backed by MongoDB: checkout, inventory, and reporting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId

from src.data.db import get_collection
from src.services.customer_service import record_purchase
from src.services.user_service import log_activity

ORDERS = get_collection("orders")
PRODUCTS = get_collection("products")
INVENTORY = get_collection("inventory_movements")
USERS = get_collection("users")
CUSTOMERS = get_collection("customers")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _generate_order_number(timestamp: datetime | None = None) -> str:
    ts = timestamp or datetime.utcnow()
    return ts.strftime("ORD-%Y%m%d-%H%M%S-%f")


def create_order(
    items: List[Dict],
    customer_id: Optional[str],
    staff_id: Optional[str],
    payment_method: str,
    notes: str = "",
) -> Dict:
    if not items:
        raise ValueError("Đơn hàng phải có ít nhất một sản phẩm.")

    timestamp = datetime.utcnow()
    order_number = _generate_order_number(timestamp)
    total_amount = 0.0
    order_items: List[Dict] = []

    for item in items:
        product_id = item["product_id"]
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise ValueError("Số lượng phải lớn hơn 0.")

        product_doc = PRODUCTS.find_one({"_id": ObjectId(product_id), "is_active": True})
        if not product_doc:
            raise ValueError(f"Sản phẩm {product_id} không tồn tại hoặc đã bị vô hiệu hóa.")
        if product_doc.get("stock", 0) < quantity:
            raise ValueError(f"Tồn kho không đủ cho sản phẩm {product_doc.get('name')}.")

        line_total = float(product_doc.get("price", 0)) * quantity
        total_amount += line_total
        order_items.append(
            {
                "product_id": str(product_doc["_id"]),
                "name": product_doc.get("name"),
                "sku": product_doc.get("sku"),
                "quantity": quantity,
                "unit_price": product_doc.get("price"),
                "total_price": line_total,
            }
        )

    now_iso = timestamp.isoformat(timespec="seconds")
    customer_doc = CUSTOMERS.find_one({"_id": ObjectId(customer_id)}) if customer_id else None
    staff_doc = USERS.find_one({"_id": ObjectId(staff_id)}) if staff_id else None

    order_doc = {
        "order_number": order_number,
        "customer_id": str(customer_id) if customer_id else None,
        "customer_name": customer_doc.get("full_name") if customer_doc else None,
        "staff_id": str(staff_id) if staff_id else None,
        "staff_name": staff_doc.get("full_name") if staff_doc else None,
        "items": order_items,
        "total_amount": float(total_amount),
        "payment_method": payment_method,
        "status": "completed",
        "notes": notes,
        "created_at": now_iso,
    }

    result = ORDERS.insert_one(order_doc)
    inserted_id = str(result.inserted_id)

    for item in order_items:
        PRODUCTS.update_one(
            {"_id": ObjectId(item["product_id"])},
            {
                "$inc": {"stock": -item["quantity"]},
                "$set": {"updated_at": now_iso},
            },
        )
        INVENTORY.insert_one(
            {
                "product_id": item["product_id"],
                "delta": -item["quantity"],
                "reason": "sale",
                "related_order_id": inserted_id,
                "created_at": now_iso,
            }
        )

    if customer_id:
        record_purchase(customer_id, inserted_id, total_amount)
    if staff_id:
        log_activity(staff_id, "create_order", f"{order_number}:{total_amount}")

    return {
        "order_id": inserted_id,
        "order_number": order_number,
        "total_amount": total_amount,
        "created_at": now_iso,
    }


def list_orders(limit: int = 100, customer_id: Optional[str] = None, staff_id: Optional[str] = None) -> List[Dict]:
    query: Dict = {}
    if customer_id:
        query["customer_id"] = customer_id
    if staff_id:
        query["staff_id"] = staff_id
    docs = ORDERS.find(query).sort("created_at", -1).limit(limit)
    results = []
    for doc in docs:
        item = dict(doc)
        item["id"] = str(item.pop("_id"))
        results.append(item)
    return results


def get_order_details(order_id: str) -> Dict:
    doc = ORDERS.find_one({"_id": ObjectId(order_id)})
    if not doc:
        raise ValueError("Không tìm thấy đơn hàng.")
    doc["id"] = str(doc.pop("_id"))
    return {"order": doc, "items": doc.get("items", [])}


def sales_summary(start_date: str | None = None, end_date: str | None = None) -> Dict:
    match: Dict = {}
    if start_date:
        match.setdefault("created_at", {})
        match["created_at"]["$gte"] = start_date
    if end_date:
        match.setdefault("created_at", {})
        match["created_at"]["$lte"] = end_date

    pipeline = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend(
        [
            {
                "$group": {
                    "_id": None,
                    "total_orders": {"$sum": 1},
                    "revenue": {"$sum": "$total_amount"},
                    "avg_order_value": {"$avg": "$total_amount"},
                }
            }
        ]
    )

    result = next(ORDERS.aggregate(pipeline), None)
    if not result:
        return {"total_orders": 0, "revenue": 0, "avg_order_value": 0}
    return {
        "total_orders": result.get("total_orders", 0),
        "revenue": result.get("revenue", 0),
        "avg_order_value": result.get("avg_order_value", 0),
    }
