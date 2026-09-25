from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


teacher = Blueprint("teacher", __name__)


# =========================================================
# ADMIN - TEACHER LIST
# =========================================================

@teacher.route("/admin/teachers")
def teacher_list():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ONLY ADMIN
    # -----------------------------------------------------

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


# =========================================================
# ADMIN - ADD TEACHER
# =========================================================

@teacher.route(
    "/admin/teachers/add",
    methods=["GET", "POST"]
)
def add_teacher():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ONLY ADMIN
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    # -----------------------------------------------------
    # FORM SUBMISSION
    # -----------------------------------------------------

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        mobile = request.form["mobile"].strip()
        qualification = request.form["qualification"].strip()
        password = request.form["password"]

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not name or not email or not password:
            return "Name, email and password are required."

        if len(password) < 6:
            return "Password must contain at least 6 characters."

        # -------------------------------------------------
        # PASSWORD HASH
        # -------------------------------------------------

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # -----------------------------------------
                # CHECK EMAIL
                # -----------------------------------------

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

                # -----------------------------------------
                # CREATE USER
                # -----------------------------------------

                cur.execute(
                    """
                    INSERT INTO users
                        (
                            name,
                            email,
                            password_hash,
                            role,
                            is_active
                        )
                    VALUES
                        (
                            %s,
                            %s,
                            %s,
                            'TEACHER',
                            TRUE
                        )
                    RETURNING id
                    """,
                    (
                        name,
                        email,
                        password_hash
                    )
                )

                user_id = cur.fetchone()[0]

                # -----------------------------------------
                # CREATE TEACHER PROFILE
                # -----------------------------------------

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
                        (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
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

        return redirect(
            url_for("teacher.teacher_list")
        )

    return render_template("add_teacher.html")


# =========================================================
# ADMIN - ACTIVATE / DEACTIVATE TEACHER
# =========================================================

@teacher.route(
    "/admin/teachers/toggle/<int:teacher_id>",
    methods=["POST"]
)
def toggle_teacher(teacher_id):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ONLY ADMIN
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -----------------------------------------
            # GET CURRENT STATUS
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    u.id,
                    u.is_active
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

            # -----------------------------------------
            # TOGGLE STATUS
            # -----------------------------------------

            new_status = not current_status

            cur.execute(
                """
                UPDATE users
                SET is_active = %s
                WHERE id = %s
                """,
                (
                    new_status,
                    user_id
                )
            )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error updating teacher status: {e}"

    finally:

        conn.close()

    return redirect(
        url_for("teacher.teacher_list")
    )


# =========================================================
# TEACHER - VIEW STUDENTS
# =========================================================

@teacher.route("/teacher/students")
def teacher_students():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ONLY TEACHER
    # -----------------------------------------------------

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET TEACHER ID
            # =================================================

            cur.execute(
                """
                SELECT id
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]

            # =================================================
            # GET CURRENT ACADEMIC YEAR
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    year_name
                FROM academic_years
                WHERE is_current = TRUE
                LIMIT 1
                """
            )

            current_year = cur.fetchone()

            if not current_year:
                return "Current academic year not found.", 404

            academic_year_id = current_year[0]
            academic_year_name = current_year[1]

            # =================================================
            # GET STUDENTS THROUGH CLASS TEACHER ASSIGNMENT
            # =================================================
            #
            # Teacher
            #    ↓
            # class_teacher_assignments
            #    ↓
            # class
            #    ↓
            # student_enrollments
            #    ↓
            # students
            #
            # =================================================

            cur.execute(
                """
                SELECT DISTINCT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.gender,
                    c.class_name,
                    ay.year_name
                FROM students s

                JOIN student_enrollments se
                    ON s.id = se.student_id

                JOIN classes c
                    ON se.class_id = c.id

                JOIN academic_years ay
                    ON se.academic_year_id = ay.id

                JOIN class_teacher_assignments cta
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id = se.academic_year_id

                WHERE cta.teacher_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY
                    c.class_order,
                    s.student_name
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            students = cur.fetchall()

    finally:

        conn.close()

    return render_template(
        "teacher_students.html",
        students=students,
        academic_year_name=academic_year_name
    )


# =========================================================
# TEACHER - ADD LEARNING ACTIVITY
# =========================================================

@teacher.route(
    "/teacher/activity/add",
    methods=["GET", "POST"]
)
def add_learning_activity():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ONLY TEACHER
    # -----------------------------------------------------

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET TEACHER ID
            # =================================================

            cur.execute(
                """
                SELECT id
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]

            # =================================================
            # GET CURRENT ACADEMIC YEAR
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    year_name
                FROM academic_years
                WHERE is_current = TRUE
                LIMIT 1
                """
            )

            current_year = cur.fetchone()

            if not current_year:
                return "Current academic year not found.", 404

            academic_year_id = current_year[0]
            academic_year_name = current_year[1]

            # =================================================
            # GET STUDENTS ASSIGNED THROUGH CLASS
            # =================================================

            cur.execute(
                """
                SELECT DISTINCT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    se.id AS enrollment_id,
                    c.class_name
                FROM students s

                JOIN student_enrollments se
                    ON s.id = se.student_id

                JOIN classes c
                    ON se.class_id = c.id

                JOIN class_teacher_assignments cta
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id = se.academic_year_id

                WHERE cta.teacher_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY
                    c.class_order,
                    s.student_name
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            students = cur.fetchall()

            # =================================================
            # HANDLE FORM SUBMISSION
            # =================================================

            if request.method == "POST":

                student_id = request.form.get(
                    "student_id",
                    ""
                ).strip()

                enrollment_id = request.form.get(
                    "enrollment_id",
                    ""
                ).strip()

                activity_name = request.form.get(
                    "activity_name",
                    ""
                ).strip()

                score = request.form.get(
                    "score",
                    ""
                ).strip()

                max_score = request.form.get(
                    "max_score",
                    ""
                ).strip()

                attempts = request.form.get(
                    "attempts",
                    "1"
                ).strip()

                time_taken = request.form.get(
                    "time_taken_seconds",
                    ""
                ).strip()

                activity_date = request.form.get(
                    "activity_date",
                    ""
                ).strip()

                remarks = request.form.get(
                    "remarks",
                    ""
                ).strip()

                # =================================================
                # VALIDATION
                # =================================================

                if not student_id:

                    return "Please select a student."

                if not enrollment_id:

                    return "Invalid enrollment."

                if not activity_name:

                    return "Activity name is required."

                if not score:

                    return "Score is required."

                if not max_score:

                    max_score = "10"

                if not attempts:

                    attempts = "1"

                if not activity_date:

                    return "Activity date is required."

                # =================================================
                # CONVERT VALUES
                # =================================================

                try:

                    student_id = int(student_id)

                    enrollment_id = int(
                        enrollment_id
                    )

                    score = float(score)

                    max_score = float(
                        max_score
                    )

                    attempts = int(
                        attempts
                    )

                    if time_taken:

                        time_taken = int(
                            time_taken
                        )

                    else:

                        time_taken = None

                except ValueError:

                    return (
                        "Please enter valid "
                        "numeric values."
                    )

                # =================================================
                # VALUE VALIDATION
                # =================================================

                if score < 0:

                    return (
                        "Score cannot be negative."
                    )

                if max_score <= 0:

                    return (
                        "Maximum score must "
                        "be greater than 0."
                    )

                if score > max_score:

                    return (
                        "Score cannot be greater "
                        "than maximum score."
                    )

                if attempts < 1:

                    return (
                        "Attempts must be "
                        "at least 1."
                    )

                if (
                    time_taken is not None
                    and time_taken < 0
                ):

                    return (
                        "Time taken cannot "
                        "be negative."
                    )

                # =================================================
                # VERIFY STUDENT BELONGS TO TEACHER'S CLASS
                # =================================================

                cur.execute(
                    """
                    SELECT
                        se.id
                    FROM student_enrollments se

                    JOIN class_teacher_assignments cta
                        ON cta.class_id = se.class_id
                        AND cta.academic_year_id =
                            se.academic_year_id

                    WHERE se.id = %s
                      AND se.student_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'
                      AND cta.teacher_id = %s
                    """,
                    (
                        enrollment_id,
                        student_id,
                        academic_year_id,
                        teacher_id
                    )
                )

                valid_enrollment = cur.fetchone()

                if not valid_enrollment:

                    return (
                        "Invalid student or "
                        "student is not assigned "
                        "to your class.",
                        403
                    )

                # =================================================
                # INSERT LEARNING ACTIVITY
                # =================================================

                cur.execute(
                    """
                    INSERT INTO learning_activities
                    (
                        student_id,
                        enrollment_id,
                        activity_name,
                        activity_date,
                        score,
                        max_score,
                        attempts,
                        time_taken_seconds,
                        teacher_id,
                        remarks
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        student_id,
                        enrollment_id,
                        activity_name,
                        activity_date,
                        score,
                        max_score,
                        attempts,
                        time_taken,
                        teacher_id,
                        remarks
                    )
                )

                conn.commit()

                # =================================================
                # AFTER SUCCESS
                # =================================================

                return redirect(
                    url_for(
                        "teacher.add_learning_activity"
                    )
                )

    except Exception as e:

        conn.rollback()

        return (
            f"Error saving learning activity: {e}"
        )

    finally:

        conn.close()

    # =========================================================
    # SHOW ADD ACTIVITY PAGE
    # =========================================================

    return render_template(
        "add_learning_activity.html",
        students=students,
        academic_year_name=academic_year_name
    )