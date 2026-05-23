import logging
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache
import hashlib

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from backend.globals import db, cache
from backend.bcssm_backend.cache_utils import cached_result
from backend.bcssm_backend.exceptions import ValidationError

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def get_current_cycle_week():
    """Pre-calculate cycle week to avoid repeated computation"""
    current_date = datetime.now()  # or datetime.utcnow() if server uses UTC
    days_since_cycle_start = (current_date.date() - datetime(2025, 7, 7).date()).days
    return (days_since_cycle_start // 7) % 2

def generate_cache_key(*args, **kwargs):
    """Generate a consistent cache key from function arguments"""
    key_data = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_data.encode()).hexdigest()

def execute_readonly_query(query, params=None):
    """
    Execute a read-only SQL query using a dedicated engine connection, avoiding session overhead.
    Returns: list of result rows
    """
    try:
        with db.engine.connect() as conn:
            logger.info("Executing read-only query: %s with params: %s", query, params)
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            logger.info("Rows fetched: %s", rows)
            return rows
    except SQLAlchemyError as e:
        logger.error(
            "Read-only query failed. Query: %s, Params: %s, Error: %s", query, params, e
        )
        raise

user_assignments = {}

def execute_query(query, params=None):
    try:
        with db.session.begin():
            logger.info("Executing query: %s with params: %s", query, params)
            result = db.session.execute(text(query), params)
            if result.returns_rows:
                rows = result.fetchall()
                logger.info("Raw rows fetched: %s", rows)
                return rows
            logger.info("Query executed successfully with no rows returned.")
            return None

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Query failed. Query: %s, Params: %s, Error: %s", query, params, e)
        raise

@cached_result('users:all:list', 900, on_error=[])
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
    day = (datetime.now().weekday() + 1) % 7
    cycle = get_current_cycle_week()
    return f'user:duty:{user_name}:day{day}:cycle{cycle}'


@cached_result(_user_duty_key, 600)
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


@cached_result(_todays_duties_key, 1800, error_ttl=60, on_error=[])
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


@cached_result(_duty_schedule_key, 7200, error_ttl=60, on_error=[])
def get_duty_schedule():
    start_date = datetime(2025, 7, 5)
    
    # Pre-calculate all day/cycle combinations we need
    day_cycle_combinations = []
    date_to_info = {}
    
    for i in range(14):
        current_date = start_date + timedelta(days=i)
        db_day = (current_date.weekday() + 1) % 7  # Adjust to Sunday=0
        days_since_cycle_start = (current_date.date() - datetime(2025, 7, 7).date()).days
        cycle_week = (days_since_cycle_start // 7) % 2
        
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


@cached_result('sections:all:list', 3600, error_ttl=60,
               on_error=lambda e: {"error": f"Failed to fetch sections: {e}"})
def get_all_sections():
    query = """
    SELECT name
    FROM sections
    ORDER BY display_order, name;
    """
    result = execute_readonly_query(query)
    return [row[0] for row in result]

@cached_result(lambda section: f'users:section:{section}', 1800, error_ttl=60,
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

@cached_result('feedback:dates:all', 7200, error_ttl=60,
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


def get_user_info(user_name):
    user_info_query = """
    SELECT u.name, u.role, s.name AS section_name
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    WHERE u.name = :user_name;
    """
    try:
        user_rows = execute_readonly_query(user_info_query, {"user_name": user_name})
        if user_rows:
            return {
                "name": user_rows[0][0],
                "role": user_rows[0][1],
                "section": user_rows[0][2],
            }
        return None
    except SQLAlchemyError as e:
        logger.error("Failed to fetch user info for %s: %s", user_name, e)
        raise


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


def clear_duty_cache():
    """Clear duty-related caches after duty data changes"""
    try:
        today = datetime.now().date()
        cache.delete(f'duties:schedule:14day:{today}')
        # Clear today's duties (harder to clear all variations, so clear all)
        cache.clear()  # Nuclear option for duties
        logger.info("Cleared duty-related caches")
    except RedisError as e:
        logger.warning("Failed to clear duty caches: %s", e)

def clear_feedback_cache():
    """Clear feedback caches after feedback data changes"""
    try:
        cache.delete('feedback:dates:all')
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

@cached_result('sections:with_users:all_v6', 1800, error_ttl=60,
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
    
@cached_result('sections:statistics:summary', 3600, error_ttl=60,
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

@cached_result(lambda section_name: f'users:section:{section_name}:detailed', 1800, error_ttl=60,
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


# Update the clear_user_cache function to include new cache keys
def clear_user_cache():
    """Clear user-related caches after user data changes"""
    try:
        cache.delete('users:all:list')
        cache.delete('sections:all:list')
        cache.delete('sections:with_users:all')
        cache.delete('sections:with_users:all_v2')
        cache.delete('sections:with_users:all_v3')
        cache.delete('sections:with_users:all_v4')
        cache.delete('sections:with_users:all_v6')
        cache.delete('sections:statistics:summary')
        
        # Clear individual section caches using pattern matching if supported
        # Otherwise, clear specific known sections
        sections = get_all_sections()
        if isinstance(sections, list):
            for section in sections:
                cache.delete(f'users:section:{section}')
                cache.delete(f'users:section:{section}:detailed')
        
        # Also clear the "Unassigned" section cache
        cache.delete('users:section:Unassigned:detailed')
        
        logger.info("Cleared user-related caches")
    except RedisError as e:
        logger.warning("Failed to clear user caches: %s", e)