from flask import Flask, redirect, url_for, session
from db import get_connection
from auth import auth

app = Flask(__name__)

# Secret key for Flask sessions
app.secret_key = "smart-preschool-secret-key"

# Register authentication blueprint
app.register_blueprint(auth)


# Home page → Login page
@app.route("/")
def home():
    return redirect(url_for("auth.login"))


# Dashboard
@app.route("/dashboard")
def dashboard():

    # If user is not logged in, go to Login
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    return f"""
    <h1>Welcome to Smart Preschool Learning</h1>

    <h2>Hello, {session["user_name"]}!</h2>

    <p>You are successfully logged in.</p>

    <a href="/logout">Logout</a>
    """


# Run Flask
if __name__ == "__main__":
    app.run(debug=True)