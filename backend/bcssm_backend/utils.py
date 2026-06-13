import hmac
import logging
import os
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache

import bcrypt

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from backend.globals import db, cache
from backend.bcssm_backend.cache_utils import (
    cached_result, get_ttl_registry, clear_group,
)
from backend.bcssm_backend.exceptions import ValidationError, CacheError, AuthenticationError

logger = logging.getLogger(__name__)

CYCLE_ANCHOR = datetime(2026, 7, 4)

@lru_cache(maxsize=2)
def _cycle_week_for_date(target_date):
    days_since_cycle_start = (target_date - CYCLE_ANCHOR.date()).days
    return (days_since_cycle_start // 7) % 2

def get_current_cycle_week():
    return _cycle_week_for_date(datetime.now().date())

def execute_readonly_query(query, params=None, silent=False):
    """
    Execute a read-only SQL query using a dedicated engine connection, avoiding session overhead.
    Pass silent=True for auth/sensitive queries to suppress param and row logging.
    Returns: list of result rows
    """
    try:
        with db.engine.connect() as conn:
            if not silent:
                logger.info("Executing read-only query: %s with params: %s", query, params)
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            if not silent:
                logger.info("Rows fetched: %s", rows)
            return rows
    except SQLAlchemyError as e:
        logger.error(
            "Read-only query failed. Query: %s, Error: %s", query, e
        )
        raise

user_assignments = {}

def execute_query(query, params=None, silent=False):
    try:
        with db.session.begin():
            if not silent:
                logger.info("Executing query: %s with params: %s", query, params)
            result = db.session.execute(text(query), params)
            if result.returns_rows:
                rows = result.fetchall()
                if not silent:
                    logger.info("Raw rows fetched: %s", rows)
                return rows
            if not silent:
                logger.info("Query executed successfully with no rows returned.")
            return None

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(
            "Query failed. Query: %s, Params: %s, Error: %s",
            query,
            "<redacted>" if silent else params,
            e,
        )
        raise

@cached_result('users:all:list', on_error=[])
def get_all_users():
    query = """
    SELECT
        u.name,
        COALESCE(s.name, 'Unassigned') AS section,
        u.role,
        COALESCE(dt.name, 'No Team') AS team
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    ORDER BY
        CASE
            WHEN POSITION(' ' IN u.name) > 0
            THEN SUBSTRING(u.name FROM POSITION(' ' IN u.name) + 1)
            ELSE u.name
        END,
        u.name;
    """
    rows = execute_readonly_query(query)
    return [row[0] for row in rows]

def _user_duty_key(user_name):
    return f'user:duty:{user_name}:{datetime.now().date()}'


@cached_result(_user_duty_key, registry_key='user:duty:{name}:{date}')
def get_user_duty(user_name):
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
    query = """
    SELECT
        u.name AS user_name,
        COALESCE(s.name, 'Unassigned') AS section,
        u.role,
        COALESCE(dt.name, 'No Team') AS team,
        COALESCE(d.name, 'No Duty') AS duty
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    LEFT JOIN duty_schedule ds ON dt.id = ds.duty_team_id
        AND ds.day = :day
        AND ds.cycle_week = :cycle_week
    LEFT JOIN duties d ON ds.duty_id = d.id
    WHERE u.name = :user_name;
    """
    result = execute_readonly_query(query, {
        "user_name": user_name,
        "day": current_day,
        "cycle_week": current_cycle
    })
    if not result:
        return {"error": "User not found or no duty assigned"}
    row = result[0]
    if len(row) < 5:
        logger.error("Unexpected row format in get_user_duty for %s: %s", user_name, row)
        return {"error": "Unexpected data format from database"}
    return {
        "user": row[0],
        "section": row[1],
        "role": row[2],
        "team": row[3],
        "duty": row[4],
    }

def _todays_duties_key(user_name):
    day = (datetime.now().weekday() + 1) % 7
    cycle = get_current_cycle_week()
    return f'duties:today:day{day}:cycle{cycle}:user{user_name}'


@cached_result(_todays_duties_key, registry_key='duties:today:{day}:{cycle}:{name}', on_error=[])
def get_todays_duties(user_name):
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
    query = '''
    SELECT
        d.id,
        d.name,
        d.duty_description,
        dt.name AS team_name,
        array_agg(
            jsonb_build_object(
                'name', u.name,
                'week', u.week
            )
            ORDER BY
                CASE u.week
                    WHEN 'Both' THEN 0
                    WHEN 'Week A' THEN 1
                    WHEN 'Week B' THEN 2
                    ELSE 3
                END,
                u.name
        ) AS members,
        bool_or(u.name = :user_name) AS is_current_user
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.day = :day
        AND ds.cycle_week = :cycle_week
    GROUP BY d.id, d.name, d.duty_description, dt.name
    ORDER BY d.name;
    '''
    rows = execute_readonly_query(query, {
        "day": current_day,
        "user_name": user_name,
        "cycle_week": current_cycle
    })
    return [
        {
            "id": row[0],
            "name": row[1],
            "duty_description": row[2],
            "team_name": row[3],
            "members": row[4] or [],
            "is_current_user": row[5],
        }
        for row in rows
    ]
def _duty_schedule_key():
    return f'duties:schedule:14day:{datetime.now().date()}'


@cached_result(_duty_schedule_key, registry_key='duties:schedule:14day:{date}', on_error=[])
def get_duty_schedule():
    start_date = CYCLE_ANCHOR

    # Pre-calculate all day/cycle combinations we need
    day_cycle_combinations = []
    date_to_info = {}

    for i in range(14):
        current_date = start_date + timedelta(days=i)
        db_day = (current_date.weekday() + 1) % 7  # Adjust to Sunday=0
        cycle_week = _cycle_week_for_date(current_date.date())
        
        day_cycle_combinations.append((db_day, cycle_week))
        date_to_info[current_date.date()] = {
            "day": db_day, 
            "cycle_week": cycle_week,
            "week_name": "Week A" if cycle_week == 0 else "Week B"
        }

    # Use a more efficient parameterized query
    query = '''
    SELECT
        ds.day,
        ds.cycle_week,
        d.name AS duty_name,
        d.duty_description,
        dt.name AS team_name,
        array_agg(
            jsonb_build_object(
                'name', u.name,
                'week', u.week
            )
            ORDER BY
                CASE u.week
                    WHEN 'Both' THEN 0
                    WHEN 'Week A' THEN 1
                    WHEN 'Week B' THEN 2
                    ELSE 3
                END,
                u.name
        ) AS team_members
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.day = ANY(:days) 
        AND ds.cycle_week = ANY(:cycles)
    GROUP BY ds.day, ds.cycle_week, d.name, d.duty_description, dt.name, d.id
    ORDER BY ds.day, d.name;
    '''

    days = list(set(combo[0] for combo in day_cycle_combinations))
    cycles = list(set(combo[1] for combo in day_cycle_combinations))
    rows = execute_readonly_query(query, {"days": days, "cycles": cycles})

    # Group duties by (day, cycle_week) combination
    duty_lookup = defaultdict(list)
    for row in rows:
        day, cycle_week, duty_name, duty_description, team_name, team_members = row
        duty = {
            "duty_name": duty_name,
            "duty_description": duty_description,
            "team_name": team_name,
            "team_members": team_members or []
        }
        duty_lookup[(day, cycle_week)].append(duty)

    # Assemble final schedule
    schedule = []
    for dt in sorted(date_to_info.keys()):
        info = date_to_info[dt]
        duties_for_date = duty_lookup.get((info["day"], info["cycle_week"]), [])
        
        schedule.append({
            "date": dt.strftime("%Y-%m-%d"),
            "day_name": dt.strftime("%A"),
            "week": info["week_name"],
            "duties": duties_for_date
        })

    return schedule


@cached_result('sections:all:list',
               on_error=lambda e: {"error": f"Failed to fetch sections: {e}"})
def get_all_sections():
    query = """
    SELECT name
    FROM sections
    ORDER BY display_order, name;
    """
    result = execute_readonly_query(query)
    return [row[0] for row in result]

@cached_result(lambda section: f'users:section:{section}',
               registry_key='users:section:{name}',
               on_error=lambda e: {"error": f"Failed to fetch users by section: {e}"})
def get_users_by_section(section):
    query = """
    SELECT u.name, u.role
    FROM users u
    INNER JOIN sections s ON u.section_id = s.id
    WHERE s.name = :section
    ORDER BY u.name;
    """
    result = execute_readonly_query(query, {"section": section})
    return [{"name": row[0], "role": row[1]} for row in result]

@cached_result('feedback:dates:all',
               on_error=lambda e: {"error": f"Failed to fetch feedback dates: {e}"})
def get_all_feedback_dates():
    query = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    result = execute_readonly_query(query)
    return [row[0] for row in result]

def get_feedback_by_date(date_str):
    query = """
    SELECT s.name AS section_name, f.feedback
    FROM sections s
    LEFT JOIN feedback f ON s.id = f.section_id AND f.date = :date;
    """
    try:
        feedback_rows = execute_readonly_query(query, {"date": date_str})
        daily_feedback = {row[0]: row[1] if row[1] is not None else "No feedback available" for row in feedback_rows}
        return daily_feedback, None
    except SQLAlchemyError as e:
        logger.error("Error in get_feedback_by_date for date %s: %s", date_str, e)
        return None, "An error occurred while fetching feedback"


def _fetch_user_info(where_clause, params, log_identifier):
    # where_clause must be a hard-coded SQL fragment (e.g. "u.name = :user_name");
    # all user input goes through params so execute_readonly_query keeps it parameterized.
    query = (
        "SELECT u.name, u.role, s.name AS section_name "
        "FROM users u "
        "LEFT JOIN sections s ON u.section_id = s.id "
        f"WHERE {where_clause};"
    )
    try:
        rows = execute_readonly_query(query, params)
        if rows:
            return {"name": rows[0][0], "role": rows[0][1], "section": rows[0][2]}
        return None
    except SQLAlchemyError as e:
        logger.error("Failed to fetch user info for %s: %s", log_identifier, e)
        raise


def get_user_info(user_name):
    return _fetch_user_info("u.name = :user_name", {"user_name": user_name}, user_name)


def get_user_info_by_id(user_id):
    return _fetch_user_info("u.id = :user_id", {"user_id": user_id}, f"id {user_id}")


def save_devos_feedback(section_name: str, date_str: str, new_feedback: str, editor_id: int) -> None:
    # Single-query approach: INSERT...SELECT eliminates the TOCTOU gap between
    # the section lookup and the upsert. RETURNING lets us detect a missing section.
    query = """
        INSERT INTO feedback (section_id, date, feedback, last_edited_by, last_edited_at)
        SELECT s.id, :date_str, :new_feedback, :editor_id, CURRENT_TIMESTAMP
        FROM sections s WHERE s.name = :section_name
        ON CONFLICT (section_id, date) DO UPDATE
          SET feedback = EXCLUDED.feedback,
              last_edited_by = EXCLUDED.last_edited_by,
              last_edited_at = EXCLUDED.last_edited_at
        RETURNING section_id;
    """
    rows = execute_query(query, {
        'section_name': section_name,
        'date_str': date_str,
        'new_feedback': new_feedback,
        'editor_id': editor_id
    })
    if not rows:
        raise ValidationError("Section not found")
    clear_feedback_cache()


def clear_duty_cache():
    """Clear duty-related caches after duty data changes."""
    try:
        clear_group("duties")
        logger.info("Cleared duty-related caches")
    except RedisError as e:
        logger.warning("Failed to clear duty caches: %s", e)


def clear_feedback_cache():
    """Clear feedback caches after feedback data changes."""
    try:
        clear_group("feedback")
        logger.info("Cleared feedback caches")
    except RedisError as e:
        logger.warning("Failed to clear feedback caches: %s", e)

def clear_all_cache():
    """Nuclear option - clear everything"""
    try:
        cache.clear()
        logger.info("Cleared all caches")
    except RedisError as e:
        logger.warning("Failed to clear all caches: %s", e)

@cached_result('sections:with_users:all_v6',
               on_error=lambda e: {"error": f"Failed to fetch sections with users: {e}"})
def get_all_sections_with_users():
    # Optimized query using proper JOINs and leveraging indexes
    query = """
    SELECT 
        COALESCE(s.name, 'Unassigned') AS section_name,
        COALESCE(s.display_order, 999) AS display_order,
        u.name AS user_name,
        CASE 
            WHEN u.role = 'Admin' THEN 'Section Leader'
            ELSE u.role
        END AS display_role,
        u.week
    FROM sections s
    RIGHT JOIN users u ON s.id = u.section_id
    ORDER BY 
        COALESCE(s.display_order, 999),
        COALESCE(s.name, 'Unassigned'),
        -- Sort Section Leaders first (by first name), then others by surname
        CASE 
            WHEN u.role = 'Admin' OR u.role = 'Section Leader' THEN 0
            ELSE 1
        END,
        CASE 
            WHEN u.role = 'Admin' OR u.role = 'Section Leader' THEN u.name
            ELSE CASE 
                WHEN POSITION(' ' IN u.name) > 0 
                THEN SUBSTRING(u.name FROM POSITION(' ' IN u.name) + 1)
                ELSE u.name 
            END
        END,
        u.name;
    """
    
    rows = execute_readonly_query(query)
    sections_dict = {}
    for row in rows:
        section_name = row[0]
        user_name = row[2]
        display_role = row[3]
        week = row[4]
        if section_name not in sections_dict:
            sections_dict[section_name] = {
                "name": section_name,
                "display_order": row[1],
                "users": [],
                "user_count": 0
            }
        if user_name:
            sections_dict[section_name]["users"].append({
                "name": user_name,
                "role": display_role,
                "week": week
            })
            sections_dict[section_name]["user_count"] += 1
    sections_list = list(sections_dict.values())
    sections_list.sort(key=lambda x: (x["display_order"], x["name"]))
    return sections_list
    
@cached_result('sections:statistics:summary',
               on_error=lambda e: {"error": f"Failed to fetch section statistics: {e}"})
def get_section_statistics():
    query = """
    SELECT
        COALESCE(s.name, 'Unassigned') AS section_name,
        COALESCE(s.display_order, 999) AS display_order,
        COUNT(u.id) AS total_users,
        COUNT(CASE WHEN u.role IN ('Section Leader', 'Admin') THEN 1 END) AS section_leaders,
        COUNT(CASE WHEN u.role = 'Team Leader' THEN 1 END) AS team_leaders,
        COUNT(CASE WHEN u.role NOT IN ('Section Leader', 'Admin', 'Team Leader') THEN 1 END) AS other_roles
    FROM sections s
    RIGHT JOIN users u ON s.id = u.section_id
    GROUP BY s.id, s.name, s.display_order
    ORDER BY COALESCE(s.display_order, 999), COALESCE(s.name, 'Unassigned');
    """
    rows = execute_readonly_query(query)
    return [
        {
            "section_name": row[0],
            "display_order": row[1],
            "total_users": row[2],
            "section_leaders": row[3],
            "team_leaders": row[4],
            "other_roles": row[5]
        }
        for row in rows
    ]

@cached_result(lambda section_name: f'users:section:{section_name}:detailed',
               registry_key='users:section:{name}:detailed',
               on_error=lambda e: {"error": f"Failed to fetch users by section: {e}"})
def get_users_by_section_optimized(section_name):
    if section_name == "Unassigned":
        query = """
        SELECT u.name, 
               CASE 
                   WHEN u.role = 'Admin' THEN 'Section Leader'
                   ELSE u.role
               END AS display_role
        FROM users u
        WHERE u.section_id IS NULL
        ORDER BY u.name;
        """
        params = {}
    else:
        query = """
        SELECT u.name,
               CASE 
                   WHEN u.role = 'Admin' THEN 'Section Leader'
                   ELSE u.role
               END AS display_role
        FROM users u
        INNER JOIN sections s ON u.section_id = s.id
        WHERE s.name = :section_name
        ORDER BY u.name;
        """
        params = {"section_name": section_name}
    
    result = execute_readonly_query(query, params)
    return [{"name": row[0], "role": row[1]} for row in result]


def clear_user_cache():
    """Clear user-related caches after user data changes."""
    try:
        clear_group("users")
        clear_group("sections")
        logger.info("Cleared user-related caches")
    except RedisError as e:
        logger.warning("Failed to clear user caches: %s", e)


def _fmt_ttl(ttl: int) -> str:
    if ttl >= 3600:
        hours = ttl // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if ttl >= 60:
        minutes = ttl // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{ttl} second{'s' if ttl != 1 else ''}"


def _redact_redis_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    return f"{host}:{port}"


def get_cache_status() -> dict:
    test_key = 'status:test'
    try:
        cache.set(test_key, 'working', timeout=10)
        test_result = cache.get(test_key)
        cache.delete(test_key)
    except Exception as e:
        raise CacheError(f"Cache probe failed: {e}") from e
    return {
        "status": "healthy" if test_result == 'working' else "unhealthy",
        "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379')),
        "default_timeout": 300,
        "test_result": test_result,
        "cache_type": "RedisCache",
        "available_operations": {
            "clear_users": "/api/admin/cache/clear (POST with type: users)",
            "clear_duties": "/api/admin/cache/clear (POST with type: duties)",
            "clear_feedback": "/api/admin/cache/clear (POST with type: feedback)",
            "clear_all": "/api/admin/cache/clear (POST with type: all)"
        }
    }


def get_cache_info() -> dict:
    return {
        "cache_config": {
            "type": "RedisCache",
            "url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379')),
            "default_timeout": 300
        },
        "cached_functions": {
            name: _fmt_ttl(ttl) for name, ttl in get_ttl_registry().items()
        },
        "management_endpoints": {
            "status": "GET /api/admin/cache/status",
            "clear": "POST /api/admin/cache/clear",
            "info": "GET /api/admin/cache/info"
        }
    }


def get_health_status() -> dict:
    try:
        cache.set('health:test', 'ok', timeout=10)
        cache_ok = cache.get('health:test') == 'ok'
        cache.delete('health:test')
    except Exception as e:
        raise CacheError(f"Cache probe failed: {e}") from e
    health = {
        "status": "healthy",
        "database": "connected",
        "cache": "healthy" if cache_ok else "unhealthy",
        "environment": os.getenv('FLASK_ENV', 'development'),
        "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
    }
    if not cache_ok:
        health["status"] = "degraded"
    return health


def authenticate_user(user_name: str, password: str) -> dict:
    """Validate credentials against DB. Raises AuthenticationError on any failure."""
    rows = execute_readonly_query(
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
        raise AuthenticationError("Invalid credentials")
    if not is_valid:
        raise AuthenticationError("Invalid credentials")
    return {
        "id": user_id,
        "name": name,
        "role": role,
        "section_name": section_name,
        "can_edit_all": role in {"Section Leader", "Team Leader", "Admin"},
    }


def get_user_role(user_name: str):
    """Return the role string for a user, or None if not found."""
    rows = execute_readonly_query(
        "SELECT role FROM users WHERE name = :name",
        {'name': user_name},
        silent=True,
    )
    return rows[0][0] if rows else None


def get_all_users_password_status() -> list:
    """Return list of {name, has_password} dicts ordered by name."""
    rows = execute_readonly_query(
        "SELECT u.name, (u.password_hash IS NOT NULL) AS has_password "
        "FROM users u ORDER BY u.name"
    )
    return [{'name': r[0], 'has_password': bool(r[1])} for r in rows]


def set_user_password(user_name: str, password_hash: str) -> bool:
    """Write a bcrypt hash for a user. Returns True if the user was found."""
    rows = execute_query(
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