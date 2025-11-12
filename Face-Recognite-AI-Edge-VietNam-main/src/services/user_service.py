"""
Service layer for user, authentication, and audit log management using MongoDB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId

from src.data.db import ensure_indexes, get_collection
from src.services.security import generate_session_token, hash_password, verify_password


ensure_indexes()

USERS = get_collection("users")
LOGIN_LOGS = get_collection("login_logs")
ACTIVITY_LOGS = get_collection("activity_logs")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _serialize_user(doc) -> Dict:
    if not doc:
        return {}
    result = {
        "id": str(doc.get("_id")),
        "username": doc.get("username"),
        "role": doc.get("role"),
        "full_name": doc.get("full_name"),
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "is_active": bool(doc.get("is_active", True)),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "last_login": doc.get("last_login"),
    }
    return result


def ensure_default_admin() -> None:
    """Create an initial admin account if none exist."""
    if USERS.count_documents({"role": "admin"}, limit=1):
        return
    pwd_hash, salt = hash_password("Admin@123")
    USERS.insert_one(
        {
            "username": "admin",
            "password_hash": pwd_hash,
            "salt": salt,
            "role": "admin",
            "full_name": "Quản trị viên",
            "email": "admin@example.com",
            "phone": "",
            "is_active": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "last_login": None,
        }
    )


def create_user(
    username: str,
    password: str,
    role: str,
    full_name: str = "",
    email: str = "",
    phone: str = "",
    is_active: bool = True,
) -> str:
    if role not in {"admin", "staff"}:
        raise ValueError("Role phải là 'admin' hoặc 'staff'.")
    pwd_hash, salt = hash_password(password)
    now = _now_iso()
    doc = {
        "username": username,
        "password_hash": pwd_hash,
        "salt": salt,
        "role": role,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "is_active": bool(is_active),
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }
    result = USERS.insert_one(doc)
    return str(result.inserted_id)


def update_user(user_id: str, **fields) -> None:
    allowed = {"full_name", "email", "phone", "role", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = _now_iso()
    USERS.update_one({"_id": ObjectId(user_id)}, {"$set": updates})


def set_password(user_id: str, new_password: str) -> None:
    pwd_hash, salt = hash_password(new_password)
    USERS.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "password_hash": pwd_hash,
                "salt": salt,
                "updated_at": _now_iso(),
            }
        },
    )


def set_user_active(user_id: str, is_active: bool) -> None:
    USERS.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "is_active": bool(is_active),
                "updated_at": _now_iso(),
            }
        },
    )


def delete_user(user_id: str) -> None:
    USERS.delete_one({"_id": ObjectId(user_id)})


def get_user_by_username(username: str):
    return USERS.find_one({"username": username})


def authenticate(username: str, password: str) -> Optional[Dict]:
    user_doc = get_user_by_username(username)
    if not user_doc:
        log_login_attempt(None, False, "unknown user", "")
        return None
    if not user_doc.get("is_active", True):
        log_login_attempt(user_doc["_id"], False, "inactive account", "")
        return None
    if verify_password(password, user_doc["password_hash"], user_doc["salt"]):
        now = _now_iso()
        USERS.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_login": now, "updated_at": now}},
        )
        session_token = generate_session_token()
        log_login_attempt(user_doc["_id"], True, "flask-web", "")
        serialized = _serialize_user(user_doc)
        serialized["session_token"] = session_token
        serialized["role"] = user_doc.get("role")
        serialized["full_name"] = user_doc.get("full_name")
        serialized["email"] = user_doc.get("email")
        serialized["phone"] = user_doc.get("phone")
        serialized["is_active"] = bool(user_doc.get("is_active", True))
        return serialized
    log_login_attempt(user_doc["_id"], False, "invalid password", "")
    return None


def log_login_attempt(user_id, success: bool, client_info: str, ip_address: str) -> None:
    LOGIN_LOGS.insert_one(
        {
            "user_id": str(user_id) if user_id else None,
            "successful": bool(success),
            "client_info": client_info,
            "ip_address": ip_address,
            "timestamp": _now_iso(),
        }
    )


def log_activity(user_id: Optional[str], action: str, details: str = "") -> None:
    ACTIVITY_LOGS.insert_one(
        {
            "user_id": str(user_id) if user_id else None,
            "action": action,
            "details": details,
            "created_at": _now_iso(),
        }
    )


def list_users() -> List[Dict]:
    docs = USERS.find().sort("created_at", -1)
    return [_serialize_user(doc) for doc in docs]


def login_logs(limit: int = 200) -> List[Dict]:
    docs = LOGIN_LOGS.find().sort("timestamp", -1).limit(limit)
    return [
        {
            "id": str(doc.get("_id")),
            "user_id": doc.get("user_id"),
            "successful": doc.get("successful"),
            "client_info": doc.get("client_info"),
            "ip_address": doc.get("ip_address"),
            "timestamp": doc.get("timestamp"),
        }
        for doc in docs
    ]


def activity_logs(limit: int = 200) -> List[Dict]:
    docs = ACTIVITY_LOGS.find().sort("created_at", -1).limit(limit)
    return [
        {
            "id": str(doc.get("_id")),
            "user_id": doc.get("user_id"),
            "action": doc.get("action"),
            "details": doc.get("details"),
            "created_at": doc.get("created_at"),
        }
        for doc in docs
    ]
