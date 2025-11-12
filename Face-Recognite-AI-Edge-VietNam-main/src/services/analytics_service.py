"""
Analytics helpers for dashboards and reports using MongoDB aggregations.
"""

from __future__ import annotations

from typing import Dict, List

from src.data.db import get_collection

CUSTOMERS = get_collection("customers")
RECOGNITION = get_collection("recognition_events")
ORDERS = get_collection("orders")
PRODUCTS = get_collection("products")
USERS = get_collection("users")


def recognition_metrics() -> Dict:
    total_events = RECOGNITION.count_documents({})
    unknown_events = RECOGNITION.count_documents({"customer_id": None})
    pipeline = [
        {"$match": {"confidence": {"$exists": True}}},
        {"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence"}}},
    ]
    avg_confidence_doc = next(RECOGNITION.aggregate(pipeline), {"avg_confidence": 0})
    recognised = total_events - unknown_events
    accuracy = 0 if total_events == 0 else round(recognised / total_events, 3)
    return {
        "total_events": total_events,
        "unknown_events": unknown_events,
        "recognised_events": recognised,
        "accuracy": accuracy,
        "avg_confidence": avg_confidence_doc.get("avg_confidence", 0),
    }


def top_customers(limit: int = 5) -> List[Dict]:
    docs = (
        CUSTOMERS.find()
        .sort("total_spend", -1)
        .limit(limit)
    )
    return [
        {
            "id": str(doc["_id"]),
            "full_name": doc.get("full_name"),
            "total_spend": doc.get("total_spend", 0),
            "visit_count": doc.get("visit_count", 0),
            "last_visit": doc.get("last_visit"),
        }
        for doc in docs
    ]


def employee_performance(limit: int = 10) -> List[Dict]:
    pipeline = [
        {"$match": {"staff_id": {"$ne": None}}},
        {
            "$group": {
                "_id": "$staff_id",
                "orders_handled": {"$sum": 1},
                "revenue": {"$sum": "$total_amount"},
            }
        },
        {"$sort": {"revenue": -1}},
        {"$limit": limit},
    ]
    results = []
    user_map = {str(u["_id"]): u for u in USERS.find({"role": "staff"})}
    for doc in ORDERS.aggregate(pipeline):
        staff_id = doc["_id"]
        user = user_map.get(staff_id)
        results.append(
            {
                "id": staff_id,
                "full_name": user.get("full_name") if user else None,
                "orders_handled": doc.get("orders_handled", 0),
                "revenue": doc.get("revenue", 0),
            }
        )
    return results


def frequent_customers(threshold: int = 3) -> int:
    return CUSTOMERS.count_documents({"visit_count": {"$gte": threshold}})


def recommendations_for_customer(customer_id: str, limit: int = 5) -> List[Dict]:
    pipeline = [
        {"$match": {"customer_id": customer_id}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "purchase_count": {"$sum": "$items.quantity"},
            }
        },
        {"$sort": {"purchase_count": -1}},
        {"$limit": limit},
    ]
    product_map = {str(p["_id"]): p for p in PRODUCTS.find()}
    results = []
    for doc in ORDERS.aggregate(pipeline):
        prod_id = doc["_id"]
        prod = product_map.get(prod_id)
        if prod:
            results.append(
                {
                    "id": prod_id,
                    "name": prod.get("name"),
                    "price": prod.get("price"),
                    "image_path": prod.get("image_path"),
                    "purchase_count": doc.get("purchase_count", 0),
                }
            )
    if results:
        return results

    # Fallback: top selling products overall
    fallback_pipeline = [
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "total_sold": {"$sum": "$items.quantity"},
            }
        },
        {"$sort": {"total_sold": -1}},
        {"$limit": limit},
    ]
    fallback = []
    for doc in ORDERS.aggregate(fallback_pipeline):
        prod = product_map.get(doc["_id"])
        if prod:
            fallback.append(
                {
                    "id": doc["_id"],
                    "name": prod.get("name"),
                    "price": prod.get("price"),
                    "image_path": prod.get("image_path"),
                    "total_sold": doc.get("total_sold", 0),
                }
            )
    return fallback
