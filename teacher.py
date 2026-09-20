from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


teacher = Blueprint("teacher", __name__)


# ==========================================
# Admin - Teacher List
# ==========================================

@teacher.route("/admin/teachers")
def teacher_list():

    # Only logged-in Admin can access
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    t.id,
                    t.teacher_name,
                    t.mobile,
                    t.email,
                    t.qualification,
                    u.is_active
                FROM teachers t
                JOIN users u
                    ON t.user_id = u.id
                ORDER BY t.id DESC
                """
            )

            teachers = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "teachers.html",
        teachers=teachers
    )


# ==========================================
# Admin - Add Teacher
# ==========================================

@teacher.route("/admin/teachers/add", methods=["GET", "POST"])
def add_teacher():

    # Only logged-in Admin can access
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        mobile = request.form["mobile"].strip()
        qualification = request.form["qualification"].strip()
        password = request.form["password"]

        # Basic validation
        if not name or not email or not password:
            return "Name, email and password are required."

        if len(password) < 6:
            return "Password must contain at least 6 characters."

        # Create secure password hash
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # Check whether email already exists
                cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                existing_user = cur.fetchone()

                if existing_user:
                    conn.rollback()
                    return "A user with this email already exists."

                # Create user account
                cur.execute(
                    """
                    INSERT INTO users
                        (name, email, password_hash, role, is_active)
                    VALUES
                        (%s, %s, %s, 'TEACHER', TRUE)
                    RETURNING id
                    """,
                    (
                        name,
                        email,
                        password_hash
                    )
                )

                user_id = cur.fetchone()[0]

                # Create teacher profile
                cur.execute(
                    """
                    INSERT INTO teachers
                        (
                            user_id,
                            teacher_name,
                            mobile,
                            email,
                            qualification
                        )
                    VALUES
                        (%s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        name,
                        mobile,
                        email,
                        qualification
                    )
                )

            conn.commit()

        except Exception as e:

            conn.rollback()

            return f"Error creating teacher: {e}"

        finally:
            conn.close()

        return redirect(url_for("teacher.teacher_list"))

    return render_template("add_teacher.html")

# =========================================================
# ACTIVATE / DEACTIVATE TEACHER
# =========================================================

@teacher.route("/admin/teachers/toggle/<int:teacher_id>", methods=["POST"])
def toggle_teacher(teacher_id):

    # Check login
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Only ADMIN can activate/deactivate teachers
    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Get current teacher status
            cur.execute(
                """
                SELECT u.id, u.is_active
                FROM teachers t
                JOIN users u
                    ON t.user_id = u.id
                WHERE t.id = %s
                """,
                (teacher_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher not found", 404

            user_id, current_status = teacher_data

            # Change status
            new_status = not current_status

            cur.execute(
                """
                UPDATE users
                SET is_active = %s
                WHERE id = %s
                """,
                (new_status, user_id)
            )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error updating teacher status: {e}"

    finally:

        conn.close()

    return redirect(url_for("teacher.teacher_list"))