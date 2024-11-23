# app.py
from flask import Flask
from routes import init_routes

app = Flask(__name__)

# Initialize routes from routes.py
init_routes(app)

if __name__ == "__main__":
    app.run(debug=True)