from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (name, email, password_hash)
                )

            conn.commit()

        finally:
            conn.close()

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, password_hash
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                user = cur.fetchone()

        finally:
            conn.close()

        if user:
            user_id, name, password_hash = user

            if bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8")
            ):
                session["user_id"] = user_id
                session["user_name"] = name

                return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))