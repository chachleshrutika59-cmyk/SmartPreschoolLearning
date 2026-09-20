from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


student = Blueprint("student", __name__)


@student.route("/admin/students")
def student_list():

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
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.gender,
                    s.parent_name,
                    s.parent_mobile,
                    u.email,
                    u.is_active,
                    c.class_name,
                    ay.year_name
                FROM students s

                JOIN users u
                    ON s.user_id = u.id

                LEFT JOIN student_enrollments se
                    ON s.id = se.student_id
                    AND se.status = 'ACTIVE'

                LEFT JOIN classes c
                    ON se.class_id = c.id

                LEFT JOIN academic_years ay
                    ON se.academic_year_id = ay.id

                ORDER BY s.id DESC
                """
            )

            students = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "students.html",
        students=students
    )


@student.route("/admin/students/add", methods=["GET", "POST"])
def add_student():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id, class_name
                FROM classes
                ORDER BY class_order
                """
            )

            classes = cur.fetchall()

            cur.execute(
                """
                SELECT id, year_name
                FROM academic_years
                ORDER BY start_date DESC
                """
            )

            academic_years = cur.fetchall()

    finally:
        conn.close()

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        admission_number = request.form["admission_number"].strip()
        date_of_birth = request.form.get("date_of_birth") or None
        gender = request.form.get("gender") or None

        parent_name = request.form.get("parent_name", "").strip()
        parent_mobile = request.form.get("parent_mobile", "").strip()
        parent_email = request.form.get("parent_email", "").strip().lower()

        address = request.form.get("address", "").strip()

        class_id = request.form.get("class_id")
        academic_year_id = request.form.get("academic_year_id")

        if not name or not email or not password:
            return "Name, email and password are required."

        if not admission_number:
            return "Admission number is required."

        if not class_id or not academic_year_id:
            return "Class and academic year are required."

        if len(password) < 6:
            return "Password must contain at least 6 characters."

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # Check duplicate email
                cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                if cur.fetchone():
                    conn.rollback()
                    return "A user with this email already exists."

                # Check duplicate admission number
                cur.execute(
                    """
                    SELECT id
                    FROM students
                    WHERE admission_number = %s
                    """,
                    (admission_number,)
                )

                if cur.fetchone():
                    conn.rollback()
                    return "This admission number already exists."

                # Create login account
                cur.execute(
                    """
                    INSERT INTO users
                        (name, email, password_hash, role, is_active)
                    VALUES
                        (%s, %s, %s, 'STUDENT', TRUE)
                    RETURNING id
                    """,
                    (
                        name,
                        email,
                        password_hash
                    )
                )

                user_id = cur.fetchone()[0]

                # Create student profile
                cur.execute(
                    """
                    INSERT INTO students
                        (
                            user_id,
                            student_name,
                            admission_number,
                            date_of_birth,
                            gender,
                            parent_name,
                            parent_mobile,
                            parent_email,
                            address
                        )
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        name,
                        admission_number,
                        date_of_birth,
                        gender,
                        parent_name,
                        parent_mobile,
                        parent_email,
                        address
                    )
                )

                student_id = cur.fetchone()[0]

                # Create enrollment
                cur.execute(
                    """
                    INSERT INTO student_enrollments
                        (
                            student_id,
                            class_id,
                            academic_year_id,
                            status
                        )
                    VALUES
                        (%s, %s, %s, 'ACTIVE')
                    """,
                    (
                        student_id,
                        class_id,
                        academic_year_id
                    )
                )

                # Create parent contact record
                if parent_name:

                    cur.execute(
                        """
                        INSERT INTO parents
                            (
                                student_id,
                                parent_name,
                                relationship,
                                mobile,
                                email,
                                address
                            )
                        VALUES
                            (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            student_id,
                            parent_name,
                            "Parent",
                            parent_mobile,
                            parent_email,
                            address
                        )
                    )

            conn.commit()

        except Exception as e:

            conn.rollback()

            return f"Error creating student: {e}"

        finally:
            conn.close()

        return redirect(url_for("student.student_list"))

    return render_template(
        "add_student.html",
        classes=classes,
        academic_years=academic_years
    )
# =========================================================
# ACTIVATE / DEACTIVATE STUDENT
# =========================================================

@student.route("/admin/students/toggle/<int:student_id>", methods=["POST"])
def toggle_student(student_id):

    # Check login
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # Only ADMIN can change student status
    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Get student's user account and current status
            cur.execute(
                """
                SELECT u.id, u.is_active
                FROM students s
                JOIN users u
                    ON s.user_id = u.id
                WHERE s.id = %s
                """,
                (student_id,)
            )

            student_data = cur.fetchone()

            if not student_data:
                return "Student not found", 404

            user_id, current_status = student_data

            # Toggle status
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

        return f"Error updating student status: {e}"

    finally:

        conn.close()

    return redirect(url_for("student.student_list"))
