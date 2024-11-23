from datetime import datetime

# Single source of truth for user assignments
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

# utils.py

def get_users_by_section(section):
    # Example data (you would pull this from a database or data structure)
    section_users = {
        "Minis": ["Alice", "Ivy"],
        "Micros": ["Bob", "Jack"],
        "Minors": ["Charlie", "Kara"],
        "Majors": ["David", "Liam"],
        "Midis": ["Eve", "Mona"],
        "Maxis": ["Frank", "Nora"],
        "Team Leaders": ["Grace", "Hank"]
    }

    users = section_users.get(section, [])
    
    # Assign a default role ("Team Member") for users who don't have a defined role
    result = []
    for user in users:
        user_info = user_assignments.get(user, {})
        role = user_info.get("role", "Team Member")  # Default to "Team Member"
        result.append({"name": user, "role": role})

    return result