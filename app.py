from flask import Flask, render_template, request, jsonify
from datetime import datetime
import re

app = Flask(__name__)

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

@app.route('/users-by-section', methods=['GET'])
def get_users_by_section():
    """Return a list of users in the selected section."""
    section = request.args.get('section')
    if not section:
        return jsonify({"error": "No section provided"}), 400

    # Filter users based on section
    filtered_users = [
        {"name": name, "role": info.get("role", "Team Member")}
        for name, info in user_assignments.items()
        if info["section"] == section
    ]

    if not filtered_users:
        return jsonify({"error": "No users found in this section"}), 404

    return jsonify({"users": filtered_users})

# Define the 2-week duty rotation
duties = ["Breakfast", "Toilets", "Lunch", "General Clean and Tidy", "Dinner", "Supper"]
teams = ["Duty Team 1", "Duty Team 2", "Duty Team 3"]

def get_duty_schedule():
    """Generate a unique duty schedule for each day of the rotation."""
    today = datetime.now()
    day_of_cycle = today.timetuple().tm_yday % len(duties)
    rotated_duties = duties[day_of_cycle:] + duties[:day_of_cycle]
    return {teams[i]: rotated_duties[i] for i in range(len(teams))}

@app.route('/')
def home():
    """Home page with links to other features."""
    return render_template('index.html')

@app.route('/duty-teams')
def duty_teams():
    """Duty Team selection page."""
    return render_template('duty_teams.html')

@app.route('/users', methods=['GET'])
def get_users():
    """Return a list of all users."""
    return jsonify({"users": list(user_assignments.keys())})

@app.route('/user-duty', methods=['GET'])
def user_duty():
    user = request.args.get('user')
    if user not in user_assignments:
        return jsonify({"error": "User not found"}), 404

    user_info = user_assignments[user]
    team = user_info.get("team", None)

    # Extract team number if it's a valid team (e.g. "Duty Team 1" -> 1)
    team_number = None
    if team:
        match = re.match(r"Duty Team (\d+)", team)
        if match:
            team_number = int(match.group(1))

    # If the user doesn't have a team (Section Leaders, Team Leaders), return an appropriate message
    if not team_number:
        return jsonify({"error": f"{user} is a section or team leader and does not have a duty team."}), 400

    # Define duties for each day (this could be a rotating schedule over two weeks)
    duties = ["Breakfast", "Toilets", "Lunch", "General Clean and Tidy", "Dinner", "Supper"]

    # Get today's index (for example, it could be the day of the week or a specific index based on the current date)
    today_index = datetime.now().weekday()  # Monday is 0 and Sunday is 6  # Monday is 0 and Sunday is 6

    # Calculate the duty for today
    duty = duties[(team_number - 1 + today_index) % len(duties)]

    return jsonify({
        "user": user,
        "section": user_info["section"],
        "role": user_info.get("role", "Leader"),
        "team": team if team else "None",
        "duty": duty
    })

@app.route('/devos-feedback')
def devos_feedback():
    """Placeholder for Devo's Feedback page."""
    return render_template('devos_feedback.html')

if __name__ == '__main__':
    app.run(debug=True)