from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Example user assignments (later, fetch from a database)
user_assignments = {
    "Alice": {"section": "Minis", "team": "Duty Team 1"},
    "Bob": {"section": "Micros", "team": "Duty Team 2"},
    "Charlie": {"section": "Majors", "team": "Duty Team 3"},
    # Add more users as needed
}

# Define the 2-week duty rotation
duties = ["Breakfast", "Toilets", "Lunch", "General Clean and Tidy", "Dinner", "Supper"]

# Example duty team assignments
teams = ["Duty Team 1", "Duty Team 2", "Duty Team 3"]

def get_duty_schedule():
    """Generate a unique duty schedule for each day of the rotation."""
    today = datetime.now()
    day_of_cycle = today.timetuple().tm_yday % len(duties)
    rotated_duties = duties[day_of_cycle:] + duties[:day_of_cycle]
    return {teams[i]: rotated_duties[i] for i in range(len(teams))}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/user-duty', methods=['GET'])
def user_duty():
    # Simulate a user (later, use authentication to determine logged-in user)
    username = request.args.get('user', "Alice")
    user_info = user_assignments.get(username)

    if not user_info:
        return jsonify({"error": "User not found"}), 404

    # Get today's duty schedule
    schedule = get_duty_schedule()
    team = user_info["team"]
    duty = schedule.get(team, "No duty assigned")
    
    return jsonify({
        "user": username,
        "section": user_info["section"],
        "team": team,
        "duty": duty
    })

if __name__ == '__main__':
    app.run(debug=True)