import logging

import bcrypt
from redis.exceptions import RedisError

from backend.globals import cache
import backend.bcssm_backend.db as _db
from backend.bcssm_backend.constants import ELEVATED_ROLES
from backend.bcssm_backend.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


def authenticate_user(user_name: str, password: str) -> dict:
    """Validate credentials against DB. Raises AuthenticationError on any failure."""
    rows = _db.execute_readonly_query(
        "SELECT u.id, u.name, u.role, COALESCE(s.name, 'Unassigned') AS section_name, u.password_hash "
        "FROM users u "
        "LEFT JOIN sections s ON u.section_id = s.id "
        "WHERE u.name = :user_name",
        {"user_name": user_name},
        silent=True,
    )
    if not rows:
        raise AuthenticationError("Invalid credentials")
    user_id, name, role, section_name, password_hash = rows[0]
    if not password_hash:
        raise AuthenticationError("Invalid credentials")
    try:
        is_valid = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid credentials") from None
    if not is_valid:
        raise AuthenticationError("Invalid credentials")
    return {
        "id": user_id,
        "name": name,
        "role": role,
        "section_name": section_name,
        "can_edit_all": role in ELEVATED_ROLES,
    }


def get_user_role(user_name: str):
    """Return the role string for a user, or None if not found."""
    rows = _db.execute_readonly_query(
        "SELECT role FROM users WHERE name = :name",
        {'name': user_name},
        silent=True,
    )
    return rows[0][0] if rows else None


def get_all_users_password_status() -> list:
    """Return list of {name, has_password} dicts ordered by name."""
    rows = _db.execute_readonly_query(
        "SELECT u.name, (u.password_hash IS NOT NULL) AS has_password "
        "FROM users u ORDER BY u.name"
    )
    return [{'name': r[0], 'has_password': bool(r[1])} for r in rows]


def set_user_password(user_name: str, password_hash: str) -> bool:
    """Write a bcrypt hash for a user. Returns True if the user was found."""
    rows = _db.execute_query(
        "UPDATE users SET password_hash = :hash WHERE name = :name RETURNING id",
        {'hash': password_hash, 'name': user_name},
        silent=True,
    )
    return bool(rows)


def cache_user_login(user_data: dict) -> None:
    """Write user data to Redis. Swallows RedisError."""
    try:
        cache.set(f"user:data:{user_data['name']}", user_data, timeout=1800)
    except RedisError as e:
        logger.warning("Failed to cache user data for %s: %s", user_data.get("name"), e)


def evict_user_login_cache(user_name: str) -> None:
    """Delete user data from Redis. Swallows RedisError."""
    try:
        cache.delete(f"user:data:{user_name}")
    except RedisError as e:
        logger.warning("Failed to evict cache for %s: %s", user_name, e)
