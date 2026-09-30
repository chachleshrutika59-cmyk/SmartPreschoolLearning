from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


teacher = Blueprint("teacher", __name__)


# =========================================================
# ADMIN - TEACHER LIST
# =========================================================

@teacher.route("/admin/teachers")
def teacher_list():

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


# =========================================================
# ADMIN - ADD TEACHER
# =========================================================

@teacher.route(
    "/admin/teachers/add",
    methods=["GET", "POST"]
)
def add_teacher():

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

        if not name or not email or not password:
            return "Name, email and password are required."

        if len(password) < 6:
            return "Password must contain at least 6 characters."

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # Check email
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

                # Create user
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
# TEACHER - VIEW ALL STUDENTS
# =========================================================

@teacher.route("/teacher/students")
def teacher_students():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -----------------------------------------
            # GET TEACHER ID
            # -----------------------------------------

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

            # -----------------------------------------
            # CURRENT ACADEMIC YEAR
            # -----------------------------------------

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

            # -----------------------------------------
            # GET STUDENTS
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.gender,
                    c.class_name,
                    ay.year_name
                FROM class_teacher_assignments cta

                JOIN student_enrollments se
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id =
                        se.academic_year_id

                JOIN students s
                    ON se.student_id = s.id

                JOIN classes c
                    ON se.class_id = c.id

                JOIN academic_years ay
                    ON se.academic_year_id = ay.id

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
# TEACHER - VIEW STUDENTS OF PARTICULAR CLASS
# =========================================================

@teacher.route("/teacher/class/<int:class_id>/students")
def teacher_class_students(class_id):

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -----------------------------------------
            # GET TEACHER ID
            # -----------------------------------------

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

            # -----------------------------------------
            # CURRENT ACADEMIC YEAR
            # -----------------------------------------

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

            # -----------------------------------------
            # CHECK CLASS TEACHER
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order
                FROM class_teacher_assignments cta
                JOIN classes c
                    ON cta.class_id = c.id
                WHERE cta.teacher_id = %s
                  AND cta.class_id = %s
                  AND cta.academic_year_id = %s
                """,
                (
                    teacher_id,
                    class_id,
                    academic_year_id
                )
            )

            class_data = cur.fetchone()

            if not class_data:
                return (
                    "You are not assigned as class teacher "
                    "for this class.",
                    403
                )

            class_name = class_data[1]

            # -----------------------------------------
            # GET CLASS STUDENTS
            # -----------------------------------------

            cur.execute(
                """
                SELECT
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

                WHERE se.class_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY
                    s.student_name
                """,
                (
                    class_id,
                    academic_year_id
                )
            )

            students = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "teacher_students.html",
        students=students,
        academic_year_name=academic_year_name,
        selected_class_name=class_name
    )


# =========================================================
# TEACHER - VIEW STUDENT PROFILE
# =========================================================

@teacher.route("/teacher/student/<int:student_id>")
def student_profile(student_id):

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -----------------------------------------
            # GET TEACHER ID
            # -----------------------------------------

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

            # -----------------------------------------
            # CURRENT YEAR
            # -----------------------------------------

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

            # -----------------------------------------
            # GET STUDENT PROFILE
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.date_of_birth,
                    s.gender,
                    s.parent_name,
                    s.parent_mobile,
                    s.parent_email,
                    s.address,
                    c.id AS class_id,
                    c.class_name,
                    ay.year_name,
                    se.enrollment_date,
                    se.status
                FROM students s

                JOIN student_enrollments se
                    ON s.id = se.student_id

                JOIN classes c
                    ON se.class_id = c.id

                JOIN academic_years ay
                    ON se.academic_year_id = ay.id

                JOIN class_teacher_assignments cta
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id =
                        se.academic_year_id

                WHERE s.id = %s
                  AND cta.teacher_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                LIMIT 1
                """,
                (
                    student_id,
                    teacher_id,
                    academic_year_id
                )
            )

            student = cur.fetchone()

            if not student:
                return (
                    "Student not found or student is not "
                    "assigned to your class.",
                    403
                )

            # -----------------------------------------
            # GET ACTIVITIES
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    id,
                    activity_name,
                    activity_date,
                    score,
                    max_score,
                    attempts,
                    time_taken_seconds,
                    remarks
                FROM learning_activities
                WHERE student_id = %s
                  AND enrollment_id = (
                      SELECT se.id
                      FROM student_enrollments se
                      WHERE se.student_id = %s
                        AND se.academic_year_id = %s
                        AND se.status = 'ACTIVE'
                      LIMIT 1
                  )
                ORDER BY
                    activity_date DESC,
                    id DESC
                """,
                (
                    student_id,
                    student_id,
                    academic_year_id
                )
            )

            activities = cur.fetchall()

            # -----------------------------------------
            # PERFORMANCE
            # -----------------------------------------

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_activities,

                    COALESCE(
                        ROUND(
                            AVG(
                                CASE
                                    WHEN max_score > 0
                                    THEN
                                        (score / max_score) * 100
                                    ELSE NULL
                                END
                            ),
                            2
                        ),
                        0
                    ) AS average_score,

                    COALESCE(
                        SUM(attempts),
                        0
                    ) AS total_attempts

                FROM learning_activities

                WHERE student_id = %s

                  AND enrollment_id = (
                      SELECT se.id
                      FROM student_enrollments se
                      WHERE se.student_id = %s
                        AND se.academic_year_id = %s
                        AND se.status = 'ACTIVE'
                      LIMIT 1
                  )
                """,
                (
                    student_id,
                    student_id,
                    academic_year_id
                )
            )

            performance = cur.fetchone()

    finally:
        conn.close()

    return render_template(
        "student_profile.html",
        student=student,
        activities=activities,
        performance=performance,
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

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET TEACHER
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    teacher_name
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]
            teacher_name = teacher_data[1]

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
            # GET STUDENT ID
            # =================================================

            selected_student_id = request.args.get(
                "student_id",
                type=int
            )

            if request.method == "POST":

                selected_student_id = request.form.get(
                    "student_id",
                    type=int
                )

            selected_student = None

            # =================================================
            # GET ALL STUDENTS ASSIGNED TO THIS TEACHER
            # =================================================

            cur.execute(
                """
                SELECT DISTINCT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    c.class_name
                FROM class_teacher_assignments cta

                JOIN student_enrollments se
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id =
                        se.academic_year_id

                JOIN students s
                    ON se.student_id = s.id

                JOIN classes c
                    ON se.class_id = c.id

                WHERE cta.teacher_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY
                    c.class_name,
                    s.student_name
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            teacher_students = cur.fetchall()

            # =================================================
            # GET SELECTED STUDENT
            # =================================================

            if selected_student_id:

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.student_name,
                        s.admission_number,
                        c.class_name,
                        se.id AS enrollment_id
                    FROM students s

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    JOIN classes c
                        ON se.class_id = c.id

                    JOIN class_teacher_assignments cta
                        ON cta.class_id = se.class_id
                        AND cta.academic_year_id =
                            se.academic_year_id

                    WHERE s.id = %s
                      AND cta.teacher_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                    LIMIT 1
                    """,
                    (
                        selected_student_id,
                        teacher_id,
                        academic_year_id
                    )
                )

                selected_student = cur.fetchone()

                if not selected_student:

                    return (
                        "Student not found or student is "
                        "not assigned to your class.",
                        403
                    )

            # =================================================
            # SAVE ACTIVITY
            # =================================================

            if request.method == "POST":

                student_id = request.form.get(
                    "student_id",
                    type=int
                )

                activity_name = request.form.get(
                    "activity_name",
                    ""
                ).strip()

                activity_date = request.form.get(
                    "activity_date",
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
                    ""
                ).strip()

                time_taken = request.form.get(
                    "time_taken_seconds",
                    ""
                ).strip()

                remarks = request.form.get(
                    "remarks",
                    ""
                ).strip()

                # -----------------------------------------
                # VALIDATION
                # -----------------------------------------

                if not student_id:
                    return "Please select a student.", 400

                if not activity_name:
                    return "Activity name is required.", 400

                if not activity_date:
                    return "Activity date is required.", 400

                if not score:
                    return "Score is required.", 400

                if not max_score:
                    return "Maximum score is required.", 400

                if not attempts:
                    return "Attempts are required.", 400

                if not time_taken:
                    return "Time taken is required.", 400

                if not remarks:
                    return "Teacher remarks are required.", 400

                # -----------------------------------------
                # GET VALID ENROLLMENT
                # -----------------------------------------

                cur.execute(
                    """
                    SELECT
                        se.id
                    FROM student_enrollments se

                    JOIN class_teacher_assignments cta
                        ON cta.class_id = se.class_id
                        AND cta.academic_year_id =
                            se.academic_year_id

                    WHERE se.student_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'
                      AND cta.teacher_id = %s

                    LIMIT 1
                    """,
                    (
                        student_id,
                        academic_year_id,
                        teacher_id
                    )
                )

                enrollment_data = cur.fetchone()

                if not enrollment_data:

                    return (
                        "Student is not assigned to "
                        "your class.",
                        403
                    )

                enrollment_id = enrollment_data[0]

                # -----------------------------------------
                # CONVERT NUMERIC VALUES
                # -----------------------------------------

                try:

                    score = float(score)

                    max_score = float(max_score)

                    attempts = int(attempts)

                    time_taken = int(time_taken)

                except ValueError:

                    return (
                        "Please enter valid numeric values.",
                        400
                    )

                # -----------------------------------------
                # VALUE VALIDATION
                # -----------------------------------------

                if score < 0:
                    return "Score cannot be negative.", 400

                if max_score <= 0:
                    return (
                        "Maximum score must be greater than 0.",
                        400
                    )

                if score > max_score:
                    return (
                        "Score cannot be greater than "
                        "maximum score.",
                        400
                    )

                if attempts < 1:
                    return (
                        "Attempts must be at least 1.",
                        400
                    )

                if time_taken < 0:
                    return (
                        "Time taken cannot be negative.",
                        400
                    )

                # -----------------------------------------
                # INSERT ACTIVITY
                # -----------------------------------------

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

                return redirect(
                    url_for(
                        "teacher.student_profile",
                        student_id=student_id
                    )
                )

    except Exception as e:

        conn.rollback()

        return f"Error saving learning activity: {e}"

    finally:

        conn.close()

    return render_template(
        "add_activity.html",
        teacher_name=teacher_name,
        selected_student=selected_student,
        teacher_students=teacher_students,
        academic_year_name=academic_year_name
    )


# =========================================================
# TEACHER - MARK ATTENDANCE
# =========================================================
#
# SIDEBAR ATTENDANCE
#
# This page is ONLY for marking attendance.
# It does NOT display monthly reports.
# =========================================================

@teacher.route(
    "/teacher/attendance",
    methods=["GET", "POST"]
)
def teacher_attendance():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET TEACHER
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    teacher_name
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]
            teacher_name = teacher_data[1]

            # =================================================
            # CURRENT ACADEMIC YEAR
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
            # GET ASSIGNED CLASSES
            # =================================================

            cur.execute(
                """
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order
                FROM class_teacher_assignments cta

                JOIN classes c
                    ON cta.class_id = c.id

                WHERE cta.teacher_id = %s
                  AND cta.academic_year_id = %s

                ORDER BY c.class_order
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            assigned_classes = cur.fetchall()

            # =================================================
            # SELECTED CLASS
            # =================================================

            selected_class_id = request.args.get(
                "class_id",
                type=int
            )

            if request.method == "POST":

                selected_class_id = request.form.get(
                    "class_id",
                    type=int
                )

            students = []

            selected_class_name = None

            # =================================================
            # GET STUDENTS OF SELECTED CLASS
            # =================================================

            if selected_class_id:

                # -----------------------------------------
                # VERIFY CLASS TEACHER
                # -----------------------------------------

                cur.execute(
                    """
                    SELECT
                        c.id,
                        c.class_name
                    FROM class_teacher_assignments cta

                    JOIN classes c
                        ON cta.class_id = c.id

                    WHERE cta.teacher_id = %s
                      AND cta.class_id = %s
                      AND cta.academic_year_id = %s
                    """,
                    (
                        teacher_id,
                        selected_class_id,
                        academic_year_id
                    )
                )

                class_data = cur.fetchone()

                if not class_data:

                    return (
                        "You are not assigned to this class.",
                        403
                    )

                selected_class_name = class_data[1]

                # -----------------------------------------
                # GET STUDENTS
                # -----------------------------------------

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.student_name,
                        s.admission_number,
                        se.id AS enrollment_id
                    FROM students s

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    WHERE se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                    ORDER BY
                        s.student_name
                    """,
                    (
                        selected_class_id,
                        academic_year_id
                    )
                )

                students = cur.fetchall()

            # =================================================
            # SAVE ATTENDANCE
            # =================================================

            if request.method == "POST":

                attendance_date = request.form.get(
                    "attendance_date",
                    ""
                ).strip()

                if not attendance_date:
                    return "Attendance date is required.", 400

                if not selected_class_id:
                    return "Please select a class.", 400

                if not students:
                    return "No students found.", 400

                # -----------------------------------------
                # SAVE EACH STUDENT
                # -----------------------------------------

                for student in students:

                    student_id = student[0]
                    enrollment_id = student[3]

                    status = request.form.get(
                        f"status_{student_id}"
                    )

                    if status not in [
                        "PRESENT",
                        "ABSENT",
                        "LATE"
                    ]:
                        continue

                    # -------------------------------------
                    # CHECK EXISTING ATTENDANCE
                    # -------------------------------------

                    cur.execute(
                        """
                        SELECT id
                        FROM attendance
                        WHERE student_id = %s
                          AND attendance_date = %s
                        """,
                        (
                            student_id,
                            attendance_date
                        )
                    )

                    existing = cur.fetchone()

                    if existing:

                        # Update existing record
                        cur.execute(
                            """
                            UPDATE attendance
                            SET
                                enrollment_id = %s,
                                status = %s,
                                teacher_id = %s
                            WHERE id = %s
                            """,
                            (
                                enrollment_id,
                                status,
                                teacher_id,
                                existing[0]
                            )
                        )

                    else:

                        # Insert new record
                        cur.execute(
                            """
                            INSERT INTO attendance
                            (
                                student_id,
                                enrollment_id,
                                attendance_date,
                                status,
                                teacher_id
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
                                student_id,
                                enrollment_id,
                                attendance_date,
                                status,
                                teacher_id
                            )
                        )

                conn.commit()

                # Return to MARK ATTENDANCE page
                return redirect(
                    url_for(
                        "teacher.teacher_attendance",
                        class_id=selected_class_id
                    )
                )

    except Exception as e:

        conn.rollback()

        return f"Error saving attendance: {e}"

    finally:

        conn.close()

    return render_template(
        "attendance.html",
        teacher_name=teacher_name,
        academic_year_name=academic_year_name,
        assigned_classes=assigned_classes,
        students=students,
        selected_class_id=selected_class_id,
        selected_class_name=selected_class_name
    )

# =========================================================
# TEACHER - ATTENDANCE RECORDS
# =========================================================

@teacher.route("/teacher/attendance/records", methods=["GET"])
def attendance_records():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -------------------------------------------------
            # GET TEACHER
            # -------------------------------------------------

            cur.execute(
                """
                SELECT id, teacher_name
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]
            teacher_name = teacher_data[1]

            # -------------------------------------------------
            # CURRENT ACADEMIC YEAR
            # -------------------------------------------------

            cur.execute(
                """
                SELECT id, year_name
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

            # -------------------------------------------------
            # GET CLASSES ASSIGNED TO TEACHER
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order
                FROM class_teacher_assignments cta

                JOIN classes c
                    ON cta.class_id = c.id

                WHERE cta.teacher_id = %s
                  AND cta.academic_year_id = %s

                ORDER BY c.class_order
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            assigned_classes = cur.fetchall()

            # -------------------------------------------------
            # SELECTED CLASS
            # -------------------------------------------------

            selected_class_id = request.args.get(
                "class_id",
                type=int
            )

            # -------------------------------------------------
            # SELECTED MONTH
            # Default = current month
            # -------------------------------------------------

            selected_month = request.args.get(
                "month",
                ""
            ).strip()

            if not selected_month:

                from datetime import date

                today = date.today()

                selected_month = today.strftime("%Y-%m")

            attendance_summary = []
            daily_records = []

            selected_class_name = None

            # -------------------------------------------------
            # LOAD RECORDS
            # -------------------------------------------------

            if selected_class_id:

                # ---------------------------------------------
                # CHECK CLASS BELONGS TO TEACHER
                # ---------------------------------------------

                cur.execute(
                    """
                    SELECT c.class_name
                    FROM class_teacher_assignments cta

                    JOIN classes c
                        ON cta.class_id = c.id

                    WHERE cta.teacher_id = %s
                      AND cta.class_id = %s
                      AND cta.academic_year_id = %s
                    """,
                    (
                        teacher_id,
                        selected_class_id,
                        academic_year_id
                    )
                )

                class_data = cur.fetchone()

                if not class_data:
                    return (
                        "You are not assigned to this class.",
                        403
                    )

                selected_class_name = class_data[0]

                # ---------------------------------------------
                # STUDENT-WISE MONTHLY SUMMARY
                # ---------------------------------------------

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.student_name,
                        s.admission_number,

                        COUNT(a.id) AS total_days,

                        COUNT(
                            CASE
                                WHEN a.status = 'PRESENT'
                                THEN 1
                            END
                        ) AS present_days,

                        COUNT(
                            CASE
                                WHEN a.status = 'ABSENT'
                                THEN 1
                            END
                        ) AS absent_days,

                        COUNT(
                            CASE
                                WHEN a.status = 'LATE'
                                THEN 1
                            END
                        ) AS late_days,

                        COALESCE(
                            ROUND(
                                (
                                    COUNT(
                                        CASE
                                            WHEN a.status IN
                                                ('PRESENT', 'LATE')
                                            THEN 1
                                        END
                                    )::numeric
                                    /
                                    NULLIF(COUNT(a.id), 0)
                                ) * 100,
                                2
                            ),
                            0
                        ) AS attendance_percentage

                    FROM students s

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    LEFT JOIN attendance a
                        ON a.student_id = s.id
                        AND a.attendance_date >=
                            TO_DATE(%s || '-01', 'YYYY-MM-DD')
                        AND a.attendance_date <
                            (
                                TO_DATE(
                                    %s || '-01',
                                    'YYYY-MM-DD'
                                )
                                + INTERVAL '1 month'
                            )

                    WHERE se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                    GROUP BY
                        s.id,
                        s.student_name,
                        s.admission_number

                    ORDER BY
                        s.student_name
                    """,
                    (
                        selected_month,
                        selected_month,
                        selected_class_id,
                        academic_year_id
                    )
                )

                attendance_summary = cur.fetchall()

                # ---------------------------------------------
                # DAILY ATTENDANCE DETAILS
                # ---------------------------------------------

                cur.execute(
                    """
                    SELECT
                        a.attendance_date,
                        s.student_name,
                        s.admission_number,
                        a.status

                    FROM attendance a

                    JOIN students s
                        ON a.student_id = s.id

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    WHERE se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                      AND a.attendance_date >=
                          TO_DATE(%s || '-01', 'YYYY-MM-DD')

                      AND a.attendance_date <
                          (
                              TO_DATE(
                                  %s || '-01',
                                  'YYYY-MM-DD'
                              )
                              + INTERVAL '1 month'
                          )

                    ORDER BY
                        a.attendance_date DESC,
                        s.student_name
                    """,
                    (
                        selected_class_id,
                        academic_year_id,
                        selected_month,
                        selected_month
                    )
                )

                daily_records = cur.fetchall()

    finally:

        conn.close()

    return render_template(
        "attendance_records.html",

        teacher_name=teacher_name,

        assigned_classes=assigned_classes,

        academic_year_name=academic_year_name,

        selected_class_id=selected_class_id,

        selected_class_name=selected_class_name,

        selected_month=selected_month,

        attendance_summary=attendance_summary,

        daily_records=daily_records
    )

# =========================================================
# TEACHER - ASSESSMENTS
# =========================================================

@teacher.route("/teacher/assessments", methods=["GET", "POST"])
def teacher_assessments():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # -------------------------------------------------
            # GET TEACHER
            # -------------------------------------------------

            cur.execute(
                """
                SELECT id, teacher_name
                FROM teachers
                WHERE user_id = %s
                """,
                (teacher_user_id,)
            )

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]
            teacher_name = teacher_data[1]


            # -------------------------------------------------
            # CURRENT ACADEMIC YEAR
            # -------------------------------------------------

            cur.execute(
                """
                SELECT id, year_name
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


            # -------------------------------------------------
            # GET CLASSES ASSIGNED TO TEACHER
            # -------------------------------------------------

            cur.execute(
                """
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order
                FROM class_teacher_assignments cta

                JOIN classes c
                    ON cta.class_id = c.id

                WHERE cta.teacher_id = %s
                  AND cta.academic_year_id = %s

                ORDER BY c.class_order
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            assigned_classes = cur.fetchall()


            # -------------------------------------------------
            # SELECTED CLASS
            # -------------------------------------------------

            selected_class_id = request.args.get(
                "class_id",
                type=int
            )

            selected_student_id = request.args.get(
                "student_id",
                type=int
            )


            students = []


            # -------------------------------------------------
            # GET STUDENTS OF SELECTED CLASS
            # -------------------------------------------------

            if selected_class_id:

                # Verify teacher is class teacher

                cur.execute(
                    """
                    SELECT id
                    FROM class_teacher_assignments
                    WHERE teacher_id = %s
                      AND class_id = %s
                      AND academic_year_id = %s
                    """,
                    (
                        teacher_id,
                        selected_class_id,
                        academic_year_id
                    )
                )

                class_access = cur.fetchone()

                if not class_access:
                    return "You are not assigned to this class.", 403


                # Get students

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.student_name,
                        s.admission_number,
                        se.id AS enrollment_id
                    FROM students s

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    WHERE se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                    ORDER BY s.student_name
                    """,
                    (
                        selected_class_id,
                        academic_year_id
                    )
                )

                students = cur.fetchall()


            # -------------------------------------------------
            # SAVE ASSESSMENT
            # -------------------------------------------------

            if request.method == "POST":

                selected_class_id = request.form.get(
                    "class_id",
                    type=int
                )

                selected_student_id = request.form.get(
                    "student_id",
                    type=int
                )

                assessment_name = request.form.get(
                    "assessment_name",
                    ""
                ).strip()

                learning_area = request.form.get(
                    "learning_area",
                    ""
                ).strip()

                assessment_date = request.form.get(
                    "assessment_date",
                    ""
                ).strip()

                score = request.form.get(
                    "score",
                    ""
                ).strip()

                max_score = request.form.get(
                    "max_score",
                    "10"
                ).strip()

                teacher_remark = request.form.get(
                    "teacher_remark",
                    ""
                ).strip()


                # -------------------------------------------------
                # VALIDATION
                # -------------------------------------------------

                if not selected_class_id:
                    return "Please select a class.", 400

                if not selected_student_id:
                    return "Please select a student.", 400

                if not assessment_name:
                    return "Assessment name is required.", 400

                if not learning_area:
                    return "Learning area is required.", 400

                if not assessment_date:
                    return "Assessment date is required.", 400

                if not score:
                    return "Score is required.", 400


                # -------------------------------------------------
                # VERIFY STUDENT BELONGS TO TEACHER'S CLASS
                # -------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        se.id
                    FROM student_enrollments se

                    JOIN class_teacher_assignments cta
                        ON se.class_id = cta.class_id
                       AND se.academic_year_id = cta.academic_year_id

                    WHERE se.student_id = %s
                      AND se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'
                      AND cta.teacher_id = %s
                    """,
                    (
                        selected_student_id,
                        selected_class_id,
                        academic_year_id,
                        teacher_id
                    )
                )

                enrollment = cur.fetchone()

                if not enrollment:
                    return "Student does not belong to your assigned class.", 403


                enrollment_id = enrollment[0]


                # -------------------------------------------------
                # INSERT ASSESSMENT
                # -------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO assessments
                    (
                        student_id,
                        enrollment_id,
                        assessment_name,
                        learning_area,
                        assessment_date,
                        score,
                        max_score,
                        teacher_id,
                        teacher_remark
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
                        %s
                    )
                    """,
                    (
                        selected_student_id,
                        enrollment_id,
                        assessment_name,
                        learning_area,
                        assessment_date,
                        score,
                        max_score,
                        teacher_id,
                        teacher_remark
                    )
                )


                conn.commit()


                return redirect(
                    url_for(
                        "teacher.teacher_assessments"
                    )
                )


    except Exception as e:

        conn.rollback()

        return f"Error saving assessment: {e}", 500


    finally:

        conn.close()


    return render_template(
        "teacher_assessments.html",
        teacher_name=teacher_name,
        academic_year_name=academic_year_name,
        assigned_classes=assigned_classes,
        selected_class_id=selected_class_id,
        selected_student_id=selected_student_id,
        students=students
    )


# =========================================================
# TEACHER - STUDENT PROGRESS / ANALYTICS
# =========================================================
@teacher.route("/teacher/progress")
def teacher_progress():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]
    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # -----------------------------------------
            # 1. Get teacher
            # -----------------------------------------
            cur.execute("""
                SELECT id, teacher_name
                FROM teachers
                WHERE user_id = %s
            """, (teacher_user_id,))

            teacher_data = cur.fetchone()

            if not teacher_data:
                return "Teacher profile not found.", 404

            teacher_id = teacher_data[0]
            teacher_name = teacher_data[1]

            # -----------------------------------------
            # 2. Get current academic year
            # -----------------------------------------
            cur.execute("""
                SELECT id, year_name
                FROM academic_years
                WHERE is_current = TRUE
                LIMIT 1
            """)

            current_year = cur.fetchone()

            if not current_year:
                return "Current academic year not found.", 404

            academic_year_id = current_year[0]
            academic_year_name = current_year[1]

            # -----------------------------------------
            # 3. Get teacher's assigned classes
            # -----------------------------------------
            cur.execute("""
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order
                FROM class_teacher_assignments cta
                JOIN classes c
                    ON cta.class_id = c.id
                WHERE cta.teacher_id = %s
                  AND cta.academic_year_id = %s
                ORDER BY c.class_order
            """, (teacher_id, academic_year_id))

            assigned_classes = cur.fetchall()

            # -----------------------------------------
            # 4. Selected class
            # -----------------------------------------
            selected_class_id = request.args.get(
                "class_id",
                type=int
            )

            if not selected_class_id and assigned_classes:
                selected_class_id = assigned_classes[0][0]

            students_progress = []

            # -----------------------------------------
            # 5. Load students
            # -----------------------------------------
            if selected_class_id:

                # Verify teacher is class teacher
                cur.execute("""
                    SELECT c.id, c.class_name
                    FROM class_teacher_assignments cta
                    JOIN classes c
                        ON cta.class_id = c.id
                    WHERE cta.teacher_id = %s
                      AND cta.class_id = %s
                      AND cta.academic_year_id = %s
                """, (
                    teacher_id,
                    selected_class_id,
                    academic_year_id
                ))

                class_data = cur.fetchone()

                if not class_data:
                    return "You are not assigned to this class.", 403

                # -----------------------------------------
                # 6. Student analytics
                # -----------------------------------------
                cur.execute("""
                    WITH activity_stats AS (
                        SELECT
                            student_id,
                            enrollment_id,

                            COUNT(*) AS activity_count,

                            COALESCE(
                                ROUND(
                                    AVG(
                                        CASE
                                            WHEN max_score > 0
                                            THEN (score / max_score) * 100
                                            ELSE NULL
                                        END
                                    ),
                                    2
                                ),
                                0
                            ) AS activity_average,

                            COALESCE(
                                SUM(attempts),
                                0
                            ) AS total_attempts,

                            COALESCE(
                                ROUND(
                                    AVG(time_taken_seconds),
                                    2
                                ),
                                0
                            ) AS average_time

                        FROM learning_activities

                        GROUP BY
                            student_id,
                            enrollment_id
                    ),

                    assessment_stats AS (
                        SELECT
                            student_id,
                            enrollment_id,

                            COUNT(*) AS assessment_count,

                            COALESCE(
                                ROUND(
                                    AVG(
                                        CASE
                                            WHEN max_score > 0
                                            THEN (score / max_score) * 100
                                            ELSE NULL
                                        END
                                    ),
                                    2
                                ),
                                0
                            ) AS assessment_average

                        FROM assessments

                        GROUP BY
                            student_id,
                            enrollment_id
                    ),

                    attendance_stats AS (
                        SELECT
                            student_id,
                            enrollment_id,

                            COUNT(*) AS attendance_days,

                            COALESCE(
                                ROUND(
                                    (
                                        COUNT(
                                            CASE
                                                WHEN status IN ('PRESENT', 'LATE')
                                                THEN 1
                                            END
                                        )::numeric
                                        /
                                        NULLIF(COUNT(*), 0)
                                    ) * 100,
                                    2
                                ),
                                0
                            ) AS attendance_percentage

                        FROM attendance

                        GROUP BY
                            student_id,
                            enrollment_id
                    )

                    SELECT

                        s.id,
                        s.student_name,
                        s.admission_number,

                        COALESCE(
                            ast.activity_count,
                            0
                        ) AS activity_count,

                        COALESCE(
                            ast.activity_average,
                            0
                        ) AS activity_average,

                        COALESCE(
                            ast.total_attempts,
                            0
                        ) AS total_attempts,

                        COALESCE(
                            ast.average_time,
                            0
                        ) AS average_time,

                        COALESCE(
                            asm.assessment_count,
                            0
                        ) AS assessment_count,

                        COALESCE(
                            asm.assessment_average,
                            0
                        ) AS assessment_average,

                        COALESCE(
                            ats.attendance_days,
                            0
                        ) AS attendance_days,

                        COALESCE(
                            ats.attendance_percentage,
                            0
                        ) AS attendance_percentage

                    FROM students s

                    JOIN student_enrollments se
                        ON s.id = se.student_id

                    LEFT JOIN activity_stats ast
                        ON s.id = ast.student_id
                       AND se.id = ast.enrollment_id

                    LEFT JOIN assessment_stats asm
                        ON s.id = asm.student_id
                       AND se.id = asm.enrollment_id

                    LEFT JOIN attendance_stats ats
                        ON s.id = ats.student_id
                       AND se.id = ats.enrollment_id

                    WHERE se.class_id = %s
                      AND se.academic_year_id = %s
                      AND se.status = 'ACTIVE'

                    ORDER BY s.student_name

                """, (
                    selected_class_id,
                    academic_year_id
                ))

                students_progress = cur.fetchall()

            # -----------------------------------------
            # 7. Class averages
            # -----------------------------------------
            total_students = len(students_progress)

            if total_students > 0:

                class_activity_average = round(
                    sum(
                        float(row[4])
                        for row in students_progress
                    ) / total_students,
                    2
                )

                class_assessment_average = round(
                    sum(
                        float(row[8])
                        for row in students_progress
                    ) / total_students,
                    2
                )

                class_attendance_average = round(
                    sum(
                        float(row[10])
                        for row in students_progress
                    ) / total_students,
                    2
                )

            else:

                class_activity_average = 0
                class_assessment_average = 0
                class_attendance_average = 0

            # -----------------------------------------
            # 8. Improvement / Progress Trend
            # -----------------------------------------

            progress_data = {}

            for student in students_progress:

                student_id = student[0]

                cur.execute("""
                    SELECT
                        activity_date,
                        CASE
                            WHEN max_score > 0
                            THEN (score / max_score) * 100
                            ELSE NULL
                        END AS percentage

                    FROM learning_activities

                    WHERE student_id = %s

                    AND enrollment_id IN (
                        SELECT id
                        FROM student_enrollments
                        WHERE student_id = %s
                          AND class_id = %s
                          AND academic_year_id = %s
                    )

                    AND score IS NOT NULL
                    AND max_score > 0

                    ORDER BY activity_date ASC, id ASC
                """, (
                    student_id,
                    student_id,
                    selected_class_id,
                    academic_year_id
                ))

                activity_scores = cur.fetchall()

                trend = "No Data"
                improvement = 0

                if len(activity_scores) >= 2:

                    scores = [
                        float(row[1])
                        for row in activity_scores
                    ]

                    midpoint = len(scores) // 2

                    first_scores = scores[:midpoint]
                    recent_scores = scores[midpoint:]

                    first_average = (
                        sum(first_scores)
                        / len(first_scores)
                    )

                    recent_average = (
                        sum(recent_scores)
                        / len(recent_scores)
                    )

                    improvement = round(
                        recent_average - first_average,
                        2
                    )

                    if improvement > 5:
                        trend = "Improving"

                    elif improvement < -5:
                        trend = "Declining"

                    else:
                        trend = "Stable"

                progress_data[student_id] = {
                    "trend": trend,
                    "improvement": improvement
                }

    except Exception as e:

        return f"Error loading progress analytics: {e}", 500

    finally:
        conn.close()

    return render_template(
        "teacher_progress.html",

        teacher_name=teacher_name,

        academic_year_name=academic_year_name,

        assigned_classes=assigned_classes,

        selected_class_id=selected_class_id,

        students_progress=students_progress,

        total_students=total_students,

        class_activity_average=class_activity_average,

        class_assessment_average=class_assessment_average,

        class_attendance_average=class_attendance_average,

        progress_data=progress_data
    )