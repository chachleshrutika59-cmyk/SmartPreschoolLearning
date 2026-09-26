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
                SELECT
                    id
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
                    ay.year_name,
                    c.class_order
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
# TEACHER - VIEW STUDENTS OF PARTICULAR CLASS
# =========================================================

@teacher.route("/teacher/class/<int:class_id>/students")
def teacher_class_students(class_id):

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
                SELECT
                    id
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
            # CHECK THAT TEACHER IS CLASS TEACHER
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
                return "You are not assigned as class teacher for this class.", 403

            class_name = class_data[1]

            # =================================================
            # GET ONLY STUDENTS OF THIS CLASS
            # =================================================

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
                SELECT
                    id
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
            # GET STUDENT PROFILE
            # =================================================
            #
            # IMPORTANT:
            # The student must belong to a class where
            # the logged-in teacher is the class teacher.
            #
            # =================================================

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
                    AND cta.academic_year_id = se.academic_year_id

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
                    "Student not found or "
                    "student is not assigned "
                    "to your class.",
                    403
                )

            # =================================================
            # GET LEARNING ACTIVITIES
            # =================================================

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

            # =================================================
            # PERFORMANCE SUMMARY
            # =================================================

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_activities,
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
                SELECT
                    id
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
                    c.class_name,
                    c.class_order
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
        "add_activity.html",
        students=students,
        academic_year_name=academic_year_name
    )


@teacher.route("/activity/add", methods=["GET", "POST"])
def add_activity():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    teacher_user_id = session["user_id"]

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Get teacher ID
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

            # Get students belonging to classes
            # assigned to this teacher
            cur.execute("""
                SELECT DISTINCT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    c.class_name,
                    se.id AS enrollment_id
                FROM class_teacher_assignments cta
                JOIN student_enrollments se
                    ON cta.class_id = se.class_id
                   AND cta.academic_year_id = se.academic_year_id
                JOIN students s
                    ON se.student_id = s.id
                JOIN classes c
                    ON se.class_id = c.id
                WHERE cta.teacher_id = %s
                  AND se.status = 'ACTIVE'
                ORDER BY c.class_order, s.student_name
            """, (teacher_id,))

            students = cur.fetchall()

            if request.method == "POST":

                student_id = request.form.get("student_id")
                enrollment_id = request.form.get("enrollment_id")
                activity_name = request.form.get("activity_name")
                activity_date = request.form.get("activity_date")
                score = request.form.get("score")
                max_score = request.form.get("max_score")
                attempts = request.form.get("attempts")
                time_taken = request.form.get("time_taken_seconds")
                remarks = request.form.get("remarks")

                # Basic validation
                if not student_id or not activity_name:
                    return "Student and activity name are required.", 400

                # Verify that the selected student
                # actually belongs to this teacher
                cur.execute("""
                    SELECT 1
                    FROM class_teacher_assignments cta
                    JOIN student_enrollments se
                        ON cta.class_id = se.class_id
                       AND cta.academic_year_id = se.academic_year_id
                    WHERE cta.teacher_id = %s
                      AND se.student_id = %s
                      AND se.status = 'ACTIVE'
                """, (teacher_id, student_id))

                if not cur.fetchone():
                    return "You are not authorized to add activity for this student.", 403

                cur.execute("""
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
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """, (
                    student_id,
                    enrollment_id if enrollment_id else None,
                    activity_name,
                    activity_date if activity_date else None,
                    score if score else None,
                    max_score if max_score else 10,
                    attempts if attempts else 1,
                    time_taken if time_taken else None,
                    teacher_id,
                    remarks
                ))

                conn.commit()

                return redirect(
                    url_for(
                        "teacher.teacher_student_profile",
                        student_id=student_id
                    )
                )

    finally:
        conn.close()

    return render_template(
        "add_activity.html",
        teacher_name=teacher_name,
        students=students
    )