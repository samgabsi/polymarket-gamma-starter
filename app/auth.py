from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

USERS_PATH = DATA_DIR / "users.json"
SECRET_PATH = DATA_DIR / "session_secret.txt"
ROLES = {"admin", "read_only"}
STATUSES = {"active", "suspended"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_session_secret() -> str:
    if os.getenv("POLYMARKET_OP_CONSOLE_EPHEMERAL_SESSION_SECRET", "").lower() in {"1", "true", "yes", "on"}:
        return "ephemeral-doc-generation-session-secret-not-for-production"
    ensure_data_dir()
    if SECRET_PATH.exists():
        value = SECRET_PATH.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    SECRET_PATH.write_text(value, encoding="utf-8")
    try:
        SECRET_PATH.chmod(0o600)
    except OSError:
        pass
    return value


def load_users() -> dict[str, Any]:
    ensure_data_dir()
    if not USERS_PATH.exists():
        return {"version": 1, "users": []}
    try:
        payload = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "users": []}
    if not isinstance(payload, dict):
        return {"version": 1, "users": []}
    payload.setdefault("version", 1)
    payload.setdefault("users", [])
    return payload


def save_users(payload: dict[str, Any]) -> None:
    ensure_data_dir()
    tmp = USERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(USERS_PATH)
    try:
        USERS_PATH.chmod(0o600)
    except OSError:
        pass


def users_exist() -> bool:
    return bool(load_users().get("users"))


def admin_exists() -> bool:
    return any(u.get("username") == "admin" for u in load_users().get("users", []))


def hash_password(password: str, *, salt: str | None = None) -> dict[str, str | int]:
    if salt is None:
        salt_bytes = secrets.token_bytes(16)
    else:
        salt_bytes = base64.b64decode(salt.encode("ascii"))
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": base64.b64encode(salt_bytes).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password: str, password_hash: dict[str, Any]) -> bool:
    try:
        if password_hash.get("algorithm") != "pbkdf2_sha256":
            return False
        salt = password_hash["salt"]
        expected = password_hash["hash"]
        iterations = int(password_hash.get("iterations", 260_000))
        salt_bytes = base64.b64decode(salt.encode("ascii"))
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
        actual = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in user.items() if k != "password_hash"}


def list_users_public() -> list[dict[str, Any]]:
    return [public_user(u) for u in load_users().get("users", [])]


def get_user(username: str) -> dict[str, Any] | None:
    username = username.strip()
    for user in load_users().get("users", []):
        if user.get("username") == username:
            return user
    return None


def create_user(username: str, password: str, role: str = "read_only", *, created_by: str = "system") -> dict[str, Any]:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if role not in ROLES:
        raise ValueError("Role must be admin or read_only.")
    payload = load_users()
    if any(u.get("username") == username for u in payload.get("users", [])):
        raise ValueError("Username already exists.")
    now = utc_now()
    user = {
        "username": username,
        "role": role,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
        "created_by": created_by,
        "password_hash": hash_password(password),
    }
    payload["users"].append(user)
    save_users(payload)
    return public_user(user)


def update_user(username: str, *, role: str | None = None, status: str | None = None, password: str | None = None) -> dict[str, Any]:
    payload = load_users()
    for user in payload.get("users", []):
        if user.get("username") == username:
            if role is not None:
                if role not in ROLES:
                    raise ValueError("Role must be admin or read_only.")
                user["role"] = role
            if status is not None:
                if status not in STATUSES:
                    raise ValueError("Status must be active or suspended.")
                user["status"] = status
            if password:
                if len(password) < 8:
                    raise ValueError("Password must be at least 8 characters.")
                user["password_hash"] = hash_password(password)
            user["updated_at"] = utc_now()
            save_users(payload)
            return public_user(user)
    raise ValueError("User not found.")


def delete_user(username: str, *, acting_username: str | None = None) -> bool:
    if acting_username and username == acting_username:
        raise ValueError("You cannot delete your own active login account.")
    payload = load_users()
    users = payload.get("users", [])
    new_users = [u for u in users if u.get("username") != username]
    if len(new_users) == len(users):
        return False
    if not any(u.get("role") == "admin" and u.get("status") == "active" for u in new_users):
        raise ValueError("At least one active admin account is required.")
    payload["users"] = new_users
    save_users(payload)
    return True


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    user = get_user(username)
    if not user:
        return None
    if user.get("status") != "active":
        return None
    if not verify_password(password, user.get("password_hash", {})):
        return None
    payload = load_users()
    for stored in payload.get("users", []):
        if stored.get("username") == username:
            stored["last_login_at"] = utc_now()
            stored["updated_at"] = utc_now()
            save_users(payload)
            return public_user(stored)
    return public_user(user)


def setup_initial_admin(password: str) -> dict[str, Any]:
    if users_exist():
        raise ValueError("Initial setup has already been completed.")
    return create_user("admin", password, role="admin", created_by="initial_setup")
