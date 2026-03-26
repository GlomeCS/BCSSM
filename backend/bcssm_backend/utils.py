import logging
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache
import hashlib

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from backend.globals import db, cache

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

        # Return rows only if the query expects a result
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

def get_all_users():
    """
    Optimized query with Redis caching and better ordering.
    Cache timeout: 15 minutes (users don't change frequently)
    """
    cache_key = 'users:all:list'
    
    # Try to get from cache first
    cached_users = cache.get(cache_key)
    if cached_users is not None:
        logger.info("Retrieved users from cache")
        return cached_users
    
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
    try:
        logger.info("Starting query execution for get_all_users...")
        rows = execute_readonly_query(query)
        logger.info("Query returned rows: %s", rows)

        # Extract only the names for the dropdown
        user_names = [row[0] for row in rows]
        logger.info("Fetched user names: %s", user_names)
        
        # Cache the results
        cache.set(cache_key, user_names, timeout=900)  # 15 minutes
        logger.info("Cached users list")
        
        return user_names
    except SQLAlchemyError as e:
        logger.error("Failed to fetch users: %s", e)
        return []

def get_user_duty(user_name):
    """
    Optimized with Redis caching and pre-calculated cycle week.
    Cache timeout: 10 minutes (duty assignments change daily)
    """
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
    
    # Create cache key that includes day and cycle for accurate caching
    cache_key = f'user:duty:{user_name}:day{current_day}:cycle{current_cycle}'

    # Try to get from cache first
    cached_duty = cache.get(cache_key)
    if cached_duty is not None:
        logger.info("Retrieved user duty from cache for %s", user_name)
        return cached_duty
    
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
    try:
        # Execute the query with the user's name, current day, and cycle week
        result = execute_readonly_query(query, {
            "user_name": user_name, 
            "day": current_day,
            "cycle_week": current_cycle
        })
        
        if not result:
            duty_data = {"error": "User not found or no duty assigned"}
        else:
            # Extract the user's duty information
            row = result[0]
            if len(row) < 5:
                logger.error("Unexpected row format in get_user_duty for %s: %s", user_name, row)
                duty_data = {"error": "Unexpected data format from database"}
            else:
                duty_data = {
                    "user": row[0],  # user_name
                    "section": row[1],  # section name
                    "role": row[2],  # role
                    "team": row[3],  # team name
                    "duty": row[4],  # duty name
                }
        
        # Cache the results (even errors, to avoid repeated failed queries)
        cache.set(cache_key, duty_data, timeout=600)  # 10 minutes
        logger.info("Cached user duty for %s", user_name)
        
        return duty_data

    except SQLAlchemyError as e:
        logger.error("Failed to fetch duty for user %s: %s", user_name, e)
        error_data = {"error": f"Failed to fetch duty for user: {e}"}

        # Cache errors for shorter time to allow recovery
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

def get_todays_duties(user_name):
    """
    Cached today's duties with day-specific cache key.
    Cache timeout: 30 minutes (duties are daily but don't change frequently)
    """
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
    
    # Cache key includes day and cycle for accuracy
    cache_key = f'duties:today:day{current_day}:cycle{current_cycle}:user{user_name}'
    
    # Try to get from cache first
    cached_duties = cache.get(cache_key)
    if cached_duties is not None:
        logger.info("Retrieved today's duties from cache")
        return cached_duties
    
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
    
    try:
        rows = execute_readonly_query(query, {
            "day": current_day, 
            "user_name": user_name,
            "cycle_week": current_cycle
        })
        
        duties = []
        for row in rows:
            duties.append({
                "id": row[0],
                "name": row[1],
                "duty_description": row[2],
                "team_name": row[3],
                "members": row[4] or [],
                "is_current_user": row[5],
            })
        
        # Cache the results
        cache.set(cache_key, duties, timeout=1800)  # 30 minutes
        logger.info("Cached today's duties")
        
        return duties
    except SQLAlchemyError as e:
        logger.error("Failed to fetch today's duties for user %s: %s", user_name, e)

        # Cache empty result for short time to avoid repeated failures
        cache.set(cache_key, [], timeout=60)  # 1 minute

        return []
def get_duty_schedule():
    """
    Cached duty schedule with date-based cache key.
    Cache timeout: 2 hours (schedule doesn't change frequently)
    """
    # Create cache key based on current date to ensure freshness
    today = datetime.now().date()
    cache_key = f'duties:schedule:14day:{today}'
    
    # Try to get from cache first
    cached_schedule = cache.get(cache_key)
    if cached_schedule is not None:
        logger.info("Retrieved duty schedule from cache")
        return cached_schedule
    
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

    try:
        # Extract unique days and cycles for the query
        days = list(set(combo[0] for combo in day_cycle_combinations))
        cycles = list(set(combo[1] for combo in day_cycle_combinations))
        
        rows = execute_readonly_query(query, {"days": days, "cycles": cycles})
    except SQLAlchemyError as e:
        logger.error("Failed to fetch 2-week duty schedule: %s", e)

        # Cache empty result for short time to avoid repeated failures
        cache.set(cache_key, [], timeout=60)  # 1 minute

        return []

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

    # Cache the results
    cache.set(cache_key, schedule, timeout=7200)  # 2 hours
    logger.info("Cached duty schedule")

    return schedule

def get_all_sections():
    """
    Cached sections query with long timeout since sections rarely change.
    Cache timeout: 1 hour
    """
    cache_key = 'sections:all:list'
    
    # Try to get from cache first
    cached_sections = cache.get(cache_key)
    if cached_sections is not None:
        logger.info("Retrieved sections from cache")
        return cached_sections
    
    query = """
    SELECT name
    FROM sections
    ORDER BY display_order, name;
    """
    try:
        result = execute_readonly_query(query)
        sections = [row[0] for row in result]
        
        # Cache the results
        cache.set(cache_key, sections, timeout=3600)  # 1 hour
        logger.info("Cached sections list")
        
        return sections
    except SQLAlchemyError as e:
        logger.error("Failed to fetch sections: %s", e)
        error_data = {"error": f"Failed to fetch sections: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

def get_users_by_section(section):
    """
    Cached users by section query.
    Cache timeout: 30 minutes
    """
    cache_key = f'users:section:{section}'
    
    # Try to get from cache first
    cached_users = cache.get(cache_key)
    if cached_users is not None:
        logger.info("Retrieved users by section from cache for %s", section)
        return cached_users
    
    query = """
    SELECT u.name, u.role
    FROM users u
    INNER JOIN sections s ON u.section_id = s.id
    WHERE s.name = :section
    ORDER BY u.name;
    """
    try:
        result = execute_readonly_query(query, {"section": section})
        users = [{"name": row[0], "role": row[1]} for row in result]
        
        # Cache the results
        cache.set(cache_key, users, timeout=1800)  # 30 minutes
        logger.info("Cached users by section for %s", section)
        
        return users
    except SQLAlchemyError as e:
        logger.error("Failed to fetch users by section %s: %s", section, e)
        error_data = {"error": f"Failed to fetch users by section: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

def get_all_feedback_dates():
    """
    Cached feedback dates with long timeout since they don't change frequently.
    Cache timeout: 2 hours
    """
    cache_key = 'feedback:dates:all'
    
    # Try to get from cache first
    cached_dates = cache.get(cache_key)
    if cached_dates is not None:
        logger.info("Retrieved feedback dates from cache")
        return cached_dates
    
    query = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    try:
        result = execute_readonly_query(query)
        dates = [row[0] for row in result]
        
        # Cache the results
        cache.set(cache_key, dates, timeout=7200)  # 2 hours
        logger.info("Cached feedback dates")
        
        return dates
    except SQLAlchemyError as e:
        logger.error("Failed to fetch feedback dates: %s", e)
        error_data = {"error": f"Failed to fetch feedback dates: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

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

# Add these functions to your backend/bcssm_backend/utils.py file

def get_all_sections_with_users():
    """
    Get all sections with their users, optimized with caching.
    Cache timeout: 30 minutes (user assignments don't change frequently)
    """
    cache_key = 'sections:with_users:all_v6'  # Updated cache key for new sorting
    
    # Try to get from cache first
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        logger.info("Retrieved sections with users from cache")
        return cached_data
    
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
    
    try:
        logger.info("Executing optimized query to fetch all sections with users")
        rows = execute_readonly_query(query)
        
        # Group users by section efficiently
        sections_dict = {}
        
        for row in rows:
            section_name = row[0]
            user_name = row[2]
            display_role = row[3]
            week = row[4]
            
            # Create section if it doesn't exist
            if section_name not in sections_dict:
                sections_dict[section_name] = {
                    "name": section_name,
                    "display_order": row[1],
                    "users": [],
                    "user_count": 0
                }
            
            # Add user to section (user_name should always exist due to RIGHT JOIN)
            if user_name:
                user_data = {
                    "name": user_name,
                    "role": display_role,  # This is now the display_role
                    "week": week  # Add the week field
                }
                
                sections_dict[section_name]["users"].append(user_data)
                sections_dict[section_name]["user_count"] += 1
        
        # Convert to list and sort by display_order (already sorted by query, but ensure consistency)
        sections_list = list(sections_dict.values())
        sections_list.sort(key=lambda x: (x["display_order"], x["name"]))
        
        # Cache the results
        cache.set(cache_key, sections_list, timeout=1800)  # 30 minutes
        logger.info("Cached sections with users data")
        
        return sections_list
        
    except SQLAlchemyError as e:
        logger.error("Failed to fetch sections with users: %s", e)
        error_data = {"error": f"Failed to fetch sections with users: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data
    
def get_section_statistics():
    """
    Get statistics about users across sections.
    Cache timeout: 1 hour (statistics don't change frequently)
    """
    cache_key = 'sections:statistics:summary'
    
    # Try to get from cache first
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        logger.info("Retrieved section statistics from cache")
        return cached_stats
    
    # Single optimized query to get all statistics
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
    
    try:
        rows = execute_readonly_query(query)
        
        statistics = []
        for row in rows:
            stat = {
                "section_name": row[0],
                "display_order": row[1],
                "total_users": row[2],
                "section_leaders": row[3],  # Now includes both Admin and Section Leader
                "team_leaders": row[4],
                "other_roles": row[5]
            }
            statistics.append(stat)
        
        # Cache the results
        cache.set(cache_key, statistics, timeout=3600)  # 1 hour
        logger.info("Cached section statistics")
        
        return statistics
        
    except SQLAlchemyError as e:
        logger.error("Failed to fetch section statistics: %s", e)
        error_data = {"error": f"Failed to fetch section statistics: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

def get_users_by_section_optimized(section_name):
    """
    Get users for a specific section with optimized caching.
    Cache timeout: 30 minutes
    """
    cache_key = f'users:section:{section_name}:detailed'
    
    # Try to get from cache first
    cached_users = cache.get(cache_key)
    if cached_users is not None:
        logger.info("Retrieved users by section from cache for %s", section_name)
        return cached_users
    
    # Handle "Unassigned" section case
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
    
    try:
        result = execute_readonly_query(query, params)
        users = [{"name": row[0], "role": row[1]} for row in result]
        
        # Cache the results
        cache.set(cache_key, users, timeout=1800)  # 30 minutes
        logger.info("Cached users by section for %s", section_name)
        
        return users
    except SQLAlchemyError as e:
        logger.error("Failed to fetch users by section %s: %s", section_name, e)
        error_data = {"error": f"Failed to fetch users by section: {e}"}

        # Cache error for short time
        cache.set(cache_key, error_data, timeout=60)  # 1 minute

        return error_data

# Update the clear_user_cache function to include new cache keys
def clear_user_cache():
    """Clear user-related caches after user data changes"""
    try:
        cache.delete('users:all:list')
        cache.delete('sections:all:list')
        cache.delete('sections:with_users:all')
        cache.delete('sections:with_users:all_v2')  # Old cache key
        cache.delete('sections:with_users:all_v3')  # Old cache key with week data
        cache.delete('sections:with_users:all_v4')  # New cache key with better week handling
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