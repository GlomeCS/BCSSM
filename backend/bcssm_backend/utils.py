import logging
from datetime import datetime, timedelta
from collections import defaultdict
from functools import lru_cache

from sqlalchemy import text

from backend.globals import db, cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def get_current_cycle_week():
    """Pre-calculate cycle week to avoid repeated computation"""
    days_since_start = (datetime.now().date() - datetime(2025, 7, 7).date()).days
    return (days_since_start // 7) % 2

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
    except Exception as e:
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

    except Exception as e:
        db.session.rollback()
        logger.error("Query failed. Query: %s, Params: %s, Error: %s", query, params, e)
        raise e

@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_all_users():
    """
    Optimized query with better ordering and caching.
    Assumes users table has first_name and last_name columns or a computed last_name.
    """
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
        user_names = [row[0] for row in rows]  # Extract only the name (first column)
        logger.info("Fetched user names: %s", user_names)
        return user_names
    except Exception as e:
        logger.error("Failed to fetch users: %s", e)
        return []

def get_user_duty(user_name):
    """
    Optimized with pre-calculated cycle week and better join strategy.
    """
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
        # Get the current day of the week (0=Monday, 6=Sunday)
        current_day = datetime.now().weekday()
        current_cycle = get_current_cycle_week()

        # Execute the query with the user's name, current day, and cycle week
        result = execute_readonly_query(query, {
            "user_name": user_name, 
            "day": current_day,
            "cycle_week": current_cycle
        })
        
        if not result:
            return {"error": "User not found or no duty assigned"}

        # Extract the user's duty information
        row = result[0]
        duty_data = {
            "user": row[0],  # user_name
            "section": row[1],  # section name
            "role": row[2],  # role
            "team": row[3],  # team name
            "duty": row[4],  # duty name
        }
        return duty_data

    except Exception as e:
        logger.error("Failed to fetch duty for user %s: %s", user_name, e)
        return {"error": f"Failed to fetch duty for user: {e}"}

def get_todays_duties(user_name):
    """
    Simplified query without complex CTE, using pre-calculated cycle week.
    Returns: list of dicts with keys id, name, duty_description, members, is_current_user.
    """
    current_day = datetime.now().weekday()
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
    LEFT JOIN users u ON u.duty_team_id = ds.duty_team_id
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
        return duties
    except Exception as e:
        logger.error("Failed to fetch today's duties for user %s: %s", user_name, e)
        return []

def get_duty_schedule():
    """
    Optimized duty schedule query using parameterized approach instead of dynamic SQL.
    Returns: list of dicts with date, day_name, week, and duties for each day.
    """
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
    except Exception as e:
        logger.error("Failed to fetch 2-week duty schedule: %s", e)
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

    return schedule

@cache.memoize(timeout=600)  # Cache for 10 minutes
def get_all_sections():
    """
    Cached sections query since sections rarely change.
    """
    query = """
    SELECT name
    FROM sections
    ORDER BY display_order, name;
    """
    try:
        result = execute_readonly_query(query)
        sections = [row[0] for row in result]
        return sections
    except Exception as e:
        logger.error("Failed to fetch sections: %s", e)
        return {"error": f"Failed to fetch sections: {e}"}

def get_users_by_section(section):
    """
    Optimized with proper indexing assumption on section_id.
    """
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
        return users
    except Exception as e:
        logger.error("Failed to fetch users by section %s: %s", section, e)
        return {"error": f"Failed to fetch users by section: {e}"}

@cache.memoize(timeout=3600)  # Cache for 1 hour
def get_all_feedback_dates():
    """
    Cached feedback dates since they don't change frequently.
    """
    query = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    try:
        result = execute_readonly_query(query)
        dates = [row[0] for row in result]
        return dates
    except Exception as e:
        logger.error("Failed to fetch feedback dates: %s", e)
        return {"error": f"Failed to fetch feedback dates: {e}"}