# user_assignments.py
from datetime import datetime
from sqlalchemy import text
import logging
from database import db

logger = logging.getLogger(__name__)

# Key: (date_str, section)
# Value: { "feedback": str, "last_edited_by": str, "last_edited_at": datetime }
feedback_records = {}

sections = ["Minis", "Micros", "Minors", "Majors", "Midis", "Maxis", "Team Leaders"]

# Centralized user data (section, role, and team info)
user_assignments = {
    "Alice": {"section": "Minis", "role": "Section Leader"},
    "Bob": {"section": "Micros", "role": "Section Leader"},
    "Charlie": {"section": "Minors", "role": "Section Leader"},
    "David": {"section": "Majors", "role": "Section Leader"},
    "Eve": {"section": "Midis", "role": "Section Leader"},
    "Frank": {"section": "Maxis", "role": "Section Leader"},
    "Grace": {"section": "Team Leaders", "role": "Team Leader"},
    "Hank": {"section": "Team Leaders", "role": "Team Leader"},
    "Ivy": {"section": "Minis", "team": "Duty Team 1"},
    "Jack": {"section": "Micros", "team": "Duty Team 2"},
    "Kara": {"section": "Minors", "team": "Duty Team 3"},
    "Liam": {"section": "Majors", "team": "Duty Team 1"},
    "Mona": {"section": "Midis", "team": "Duty Team 2"},
    "Nora": {"section": "Maxis", "team": "Duty Team 3"},
}


def execute_query(query, params=None):
    try:
        # Start a transaction
        db.session.begin()

        # Wrap the query in text() and log execution details
        query = text(query)  # Explicitly mark as a textual SQL expression
        if params:
            logger.info(f"Executing query: {query} with params: {params}")
            result = db.session.execute(query, params)
        else:
            logger.info(f"Executing query: {query}")
            result = db.session.execute(query)

        # Fetch all rows from the result
        rows = result.fetchall()
        logger.info(f"Raw rows fetched: {rows}")

        # Commit the transaction after successful execution
        db.session.commit()
        logger.info("Query successful.")
        return rows  # Return the fetched rows

    except Exception as e:
        # Rollback the transaction in case of an error
        db.session.rollback()
        logger.error(f"Query failed. Query: {query}, Params: {params}, Error: {e}")
        raise e  # Re-raise the exception to propagate it further

def get_all_users():
    query = """
    SELECT 
        u.name, 
        COALESCE(s.name, 'Unassigned') AS section,  -- Use 'Unassigned' if section is NULL
        u.role, 
        COALESCE(dt.name, 'No Team') AS team       -- Use 'No Team' if team is NULL
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id;
    """
    try:
        logger.info("Starting query execution for get_all_users...")
        rows = execute_query(query)
        logger.info(f"Query returned rows: {rows}")

        # Extract only the names for the dropdown
        user_names = [row[0] for row in rows]  # Extract only the name (first column)
        logger.info(f"Fetched user names: {user_names}")
        return user_names
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        return []

# Function to get a user's duty
def get_user_duty(user_name):
    if user_name not in user_assignments:
        return {"error": "User not found"}

    user_info = user_assignments[user_name]
    
    # Get today's duty index (e.g., Monday = 0, Sunday = 6)
    today_index = datetime.now().weekday()

    # Assuming duties are pre-defined
    duties = ["Breakfast", "Toilets", "Lunch", "General Clean", "Dinner", "Supper"]
    team = user_info.get("team", "None")
    
    # If the user is a section leader or team leader, return that info
    if "role" in user_info:
        return {"user": user_name, "section": user_info["section"], "role": user_info["role"]}

    # If the user is assigned to a duty team, get their duty for today
    duty = duties[(today_index) % len(duties)]
    return {"user": user_name, "section": user_info["section"], "team": team, "duty": duty}

# Function to get all users in a given section
def get_users_by_section(section):
    query = """
    SELECT name, role
    FROM users
    WHERE section = :section;
    """
    try:
        result = db.session.execute(query, {"section": section})
        users = [{"name": row[0], "role": row[1]} for row in result]
        return users
    except Exception as e:
        db.session.rollback()
        return {"error": f"Failed to fetch users by section: {e}"}

def get_all_feedback_dates():
    dates = set(date for (date, section) in feedback_records.keys())
    return sorted(dates, reverse=True)  # Most recent first