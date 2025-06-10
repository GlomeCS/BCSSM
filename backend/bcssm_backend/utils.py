import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from backend.globals import db

logger = logging.getLogger(__name__)

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
        else:
            logger.info("Query executed successfully with no rows returned.")
            return None

    except Exception as e:
        db.session.rollback()
        logger.error("Query failed. Query: %s, Params: %s, Error: %s", query, params, e)
        raise e

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
    ORDER BY SPLIT_PART(u.name, ' ', 2);
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
    LEFT JOIN duty_schedule ds ON dt.id = ds.duty_team_id AND ds.day = :day
    LEFT JOIN duties d ON ds.duty_id = d.id
    WHERE u.name = :user_name;
    """
    try:
        # Get the current day of the week (0=Monday, 6=Sunday)
        current_day = datetime.now().weekday()

        # Execute the query with the user's name and current day
        result = execute_readonly_query(query, {"user_name": user_name, "day": current_day})
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
    Fetch all duties scheduled for today, including member lists and a flag indicating
    whether the given user is part of each duty.
    Returns: list of dicts with keys id, name, duty_description, members, is_current_user.
    """
    # Determine current day of week (0=Monday, 6=Sunday)
    current_day = datetime.now().weekday()
    query = '''
    WITH computed_cycle AS (
      -- calculate 0 for the week starting 2025-07-07, 1 for the following week, etc.
      SELECT ((CURRENT_DATE - DATE '2025-07-07') / 7) % 2 AS cycle_week
    ),
    today_schedule AS (
      SELECT DISTINCT ON (ds.duty_id)
        ds.duty_id,
        ds.duty_team_id
      FROM public.duty_schedule ds, computed_cycle cc
      WHERE ds.day = :day
        AND ds.cycle_week = cc.cycle_week
      ORDER BY ds.duty_id, ds.duty_team_id
    )
    SELECT
      d.id,
      d.name,
      d.duty_description,
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
      bool_or(u.name = :user_name)            AS is_current_user
    FROM today_schedule ts
    JOIN public.duties d
      ON ts.duty_id = d.id
    LEFT JOIN public.users u
      ON u.duty_team_id = ts.duty_team_id
    GROUP BY d.id, d.name, d.duty_description
    ORDER BY d.name;
    '''
    try:
        rows = execute_readonly_query(query, {"day": current_day, "user_name": user_name})
        duties = []
        for row in rows:
            duties.append({
                "id": row[0],
                "name": row[1],
                "duty_description": row[2],
                "members": row[3] or [],
                "is_current_user": row[4],
            })
        return duties
    except Exception as e:
        logger.error("Failed to fetch today's duties for user %s: %s", user_name, e)
        return []

def get_duty_schedule():
    """
    Fetch 2-week duty schedule starting from Saturday July 5th, 2025.
    Returns: list of dicts with date, day_name, week, and duties for each day.
    """
    # Start date: Saturday, July 5th, 2025
    start_date = datetime(2025, 7, 5)
    
    schedule = []
    
    for day_offset in range(14):  # 2 weeks = 14 days
        current_date = start_date + timedelta(days=day_offset)
        
        # Calculate day of week (0=Monday, 6=Sunday) for database query
        # But Saturday = 5, so we need to adjust
        db_day = current_date.weekday()
        if db_day == 6:  # Sunday
            db_day = 0
        else:
            db_day = (db_day + 1) % 7
        
        # Determine which week (A or B) based on cycle
        # Week starting July 7th, 2025 (Monday) is Week A (cycle 0)
        days_since_cycle_start = (current_date.date() - datetime(2025, 7, 7).date()).days
        cycle_week = (days_since_cycle_start // 7) % 2
        week_name = "Week A" if cycle_week == 0 else "Week B"
        
        # Query for duties on this specific day
        query = '''
        SELECT DISTINCT
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
        FROM public.duty_schedule ds
        JOIN public.duties d ON ds.duty_id = d.id
        JOIN public.duty_teams dt ON ds.duty_team_id = dt.id
        LEFT JOIN public.users u ON u.duty_team_id = dt.id
        WHERE ds.day = :day AND ds.cycle_week = :cycle_week
        GROUP BY d.name, d.duty_description, dt.name, d.id
        ORDER BY d.name;
        '''
        
        try:
            rows = execute_readonly_query(query, {"day": db_day, "cycle_week": cycle_week})
            duties = []
            for row in rows:
                duties.append({
                    "duty_name": row[0],
                    "duty_description": row[1],
                    "team_name": row[2],
                    "team_members": row[3] or []
                })
            
            schedule.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "day_name": current_date.strftime("%A"),
                "week": week_name,
                "duties": duties
            })
            
        except Exception as e:
            logger.error("Failed to fetch duties for date %s: %s", current_date.strftime("%Y-%m-%d"), e)
            # Add empty day to schedule to maintain continuity
            schedule.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "day_name": current_date.strftime("%A"),
                "week": week_name,
                "duties": []
            })
    
    return schedule

def get_all_sections():
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
    query = """
    SELECT u.name, u.role
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    WHERE s.name = :section;
    """
    try:
        result = execute_readonly_query(query, {"section": section})
        users = [{"name": row[0], "role": row[1]} for row in result]
        return users
    except Exception as e:
        logger.error("Failed to fetch users by section %s: %s", section, e)
        return {"error": f"Failed to fetch users by section: {e}"}

def get_all_feedback_dates():
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