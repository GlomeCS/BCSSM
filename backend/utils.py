import logging
from datetime import datetime

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