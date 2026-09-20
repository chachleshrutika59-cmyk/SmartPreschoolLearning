from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_connection()

        try:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, name, password_hash, role, is_active
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                user = cur.fetchone()

        finally:
            conn.close()

        if user:

            user_id, name, password_hash, role, is_active = user

            if not is_active:
                return "Your account is inactive."

            if bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8")
            ):

                session.clear()

                session["user_id"] = user_id
                session["user_name"] = name
                session["role"] = role

                if role == "ADMIN":
                    return redirect(url_for("admin_dashboard"))

                elif role == "TEACHER":
                    return redirect(url_for("teacher_dashboard"))

                elif role == "STUDENT":
                    return redirect(url_for("student_dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


@auth.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("auth.login"))