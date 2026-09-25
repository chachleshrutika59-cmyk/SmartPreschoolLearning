from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection


classes = Blueprint("classes", __name__)


# =========================================================
# ADMIN - VIEW ALL CLASSES
# =========================================================

@classes.route("/admin/classes")
def class_list():

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
            # GET ALL CLASSES
            # =================================================

            cur.execute(
                """
                SELECT
                    c.id,
                    c.class_name,
                    c.class_order,

                    cta.teacher_id,

                    t.teacher_name,

                    COUNT(DISTINCT se.student_id) AS student_count

                FROM classes c

                LEFT JOIN class_teacher_assignments cta
                    ON c.id = cta.class_id
                    AND cta.academic_year_id = %s

                LEFT JOIN teachers t
                    ON cta.teacher_id = t.id

                LEFT JOIN student_enrollments se
                    ON c.id = se.class_id
                    AND se.academic_year_id = %s
                    AND se.status = 'ACTIVE'

                GROUP BY
                    c.id,
                    c.class_name,
                    c.class_order,
                    cta.teacher_id,
                    t.teacher_name

                ORDER BY c.class_order
                """,
                (
                    academic_year_id,
                    academic_year_id
                )
            )

            classes_data = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "classes.html",
        classes=classes_data,
        academic_year_name=academic_year_name
    )


# =========================================================
# ADMIN - VIEW CLASS DETAILS
# =========================================================

@classes.route("/admin/classes/<int:class_id>")
def class_details(class_id):

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
            # GET CLASS INFORMATION
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    class_name,
                    class_order
                FROM classes
                WHERE id = %s
                """,
                (class_id,)
            )

            class_data = cur.fetchone()

            if not class_data:
                return "Class not found.", 404

            # =================================================
            # GET CURRENT CLASS TEACHER
            # =================================================

            cur.execute(
                """
                SELECT
                    cta.id,
                    cta.teacher_id,
                    t.teacher_name,
                    t.email,
                    t.mobile
                FROM class_teacher_assignments cta

                JOIN teachers t
                    ON cta.teacher_id = t.id

                JOIN users u
                    ON t.user_id = u.id

                WHERE cta.class_id = %s
                  AND cta.academic_year_id = %s
                  AND u.is_active = TRUE

                LIMIT 1
                """,
                (
                    class_id,
                    academic_year_id
                )
            )

            current_teacher = cur.fetchone()

            # =================================================
            # GET ALL ACTIVE TEACHERS
            # =================================================

            cur.execute(
                """
                SELECT
                    t.id,
                    t.teacher_name,
                    t.email
                FROM teachers t

                JOIN users u
                    ON t.user_id = u.id

                WHERE u.is_active = TRUE

                ORDER BY t.teacher_name
                """
            )

            teachers = cur.fetchall()

            # =================================================
            # GET STUDENTS OF THIS CLASS
            # =================================================

            cur.execute(
                """
                SELECT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.gender,
                    se.enrollment_date,
                    se.status
                FROM students s

                JOIN student_enrollments se
                    ON s.id = se.student_id

                WHERE se.class_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY s.student_name
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
        "class_details.html",
        class_data=class_data,
        academic_year_name=academic_year_name,
        current_teacher=current_teacher,
        teachers=teachers,
        students=students
    )


# =========================================================
# ADMIN - ASSIGN CLASS TEACHER
# =========================================================

@classes.route(
    "/admin/classes/<int:class_id>/assign-teacher",
    methods=["POST"]
)
def assign_teacher(class_id):

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

    teacher_id = request.form.get("teacher_id", "").strip()

    if not teacher_id:
        return "Please select a teacher."

    try:
        teacher_id = int(teacher_id)
    except ValueError:
        return "Invalid teacher selected."

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET CURRENT ACADEMIC YEAR
            # =================================================

            cur.execute(
                """
                SELECT
                    id
                FROM academic_years
                WHERE is_current = TRUE
                LIMIT 1
                """
            )

            current_year = cur.fetchone()

            if not current_year:
                return "Current academic year not found.", 404

            academic_year_id = current_year[0]

            # =================================================
            # CHECK CLASS EXISTS
            # =================================================

            cur.execute(
                """
                SELECT id
                FROM classes
                WHERE id = %s
                """,
                (class_id,)
            )

            class_exists = cur.fetchone()

            if not class_exists:
                return "Class not found.", 404

            # =================================================
            # CHECK TEACHER EXISTS AND IS ACTIVE
            # =================================================

            cur.execute(
                """
                SELECT
                    t.id
                FROM teachers t

                JOIN users u
                    ON t.user_id = u.id

                WHERE t.id = %s
                  AND u.is_active = TRUE
                """,
                (teacher_id,)
            )

            teacher_exists = cur.fetchone()

            if not teacher_exists:
                return "Selected teacher is not active or does not exist.", 400

            # =================================================
            # ASSIGN / UPDATE CLASS TEACHER
            # =================================================

            cur.execute(
                """
                INSERT INTO class_teacher_assignments
                (
                    class_id,
                    academic_year_id,
                    teacher_id
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT
                    (class_id, academic_year_id)

                DO UPDATE SET
                    teacher_id = EXCLUDED.teacher_id
                """,
                (
                    class_id,
                    academic_year_id,
                    teacher_id
                )
            )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error assigning class teacher: {e}"

    finally:

        conn.close()

    return redirect(
        url_for(
            "classes.class_details",
            class_id=class_id
        )
    )


# =========================================================
# ADMIN - REMOVE CLASS TEACHER
# =========================================================

@classes.route(
    "/admin/classes/<int:class_id>/remove-teacher",
    methods=["POST"]
)
def remove_teacher(class_id):

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

            # =================================================
            # GET CURRENT ACADEMIC YEAR
            # =================================================

            cur.execute(
                """
                SELECT id
                FROM academic_years
                WHERE is_current = TRUE
                LIMIT 1
                """
            )

            current_year = cur.fetchone()

            if not current_year:
                return "Current academic year not found.", 404

            academic_year_id = current_year[0]

            # =================================================
            # REMOVE ASSIGNMENT
            # =================================================

            cur.execute(
                """
                DELETE FROM class_teacher_assignments
                WHERE class_id = %s
                  AND academic_year_id = %s
                """,
                (
                    class_id,
                    academic_year_id
                )
            )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error removing class teacher: {e}"

    finally:

        conn.close()

    return redirect(
        url_for(
            "classes.class_details",
            class_id=class_id
        )
    )