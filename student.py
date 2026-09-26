from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


student = Blueprint("student", __name__)


# =========================================================
# ADMIN - STUDENT LIST
# =========================================================

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


# =========================================================
# ADMIN - ADD STUDENT
# =========================================================

@student.route(
    "/admin/students/add",
    methods=["GET", "POST"]
)
def add_student():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    # =====================================================
    # GET CLASSES AND ACADEMIC YEARS
    # =====================================================

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    class_name
                FROM classes
                ORDER BY class_order
                """
            )

            classes = cur.fetchall()

            cur.execute(
                """
                SELECT
                    id,
                    year_name
                FROM academic_years
                ORDER BY start_date DESC
                """
            )

            academic_years = cur.fetchall()

    finally:

        conn.close()

    # =====================================================
    # HANDLE FORM SUBMISSION
    # =====================================================

    if request.method == "POST":

        # -------------------------------------------------
        # BASIC STUDENT INFORMATION
        # -------------------------------------------------

        name = request.form["name"].strip()

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        date_of_birth = (
            request.form.get("date_of_birth")
            or None
        )

        gender = (
            request.form.get("gender")
            or None
        )

        # -------------------------------------------------
        # PARENT INFORMATION
        # -------------------------------------------------

        parent_name = request.form.get(
            "parent_name",
            ""
        ).strip()

        parent_mobile = request.form.get(
            "parent_mobile",
            ""
        ).strip()

        parent_email = request.form.get(
            "parent_email",
            ""
        ).strip().lower()

        address = request.form.get(
            "address",
            ""
        ).strip()

        # -------------------------------------------------
        # CLASS / ACADEMIC YEAR
        # -------------------------------------------------

        class_id = request.form.get("class_id")

        academic_year_id = request.form.get(
            "academic_year_id"
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not name or not email or not password:

            return (
                "Name, email and password are required."
            )

        if not class_id or not academic_year_id:

            return (
                "Class and academic year are required."
            )

        if len(password) < 6:

            return (
                "Password must contain at least "
                "6 characters."
            )

        # =================================================
        # HASH PASSWORD
        # =================================================

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # =================================================
        # DATABASE TRANSACTION
        # =================================================

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # =========================================
                # CHECK DUPLICATE EMAIL
                # =========================================

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

                    return (
                        "A user with this email "
                        "already exists."
                    )

                # =========================================
                # GENERATE NEXT ADMISSION NUMBER
                # =========================================
                #
                # Example:
                #
                # STU001
                # STU002
                # STU003
                #
                # Next:
                #
                # STU004
                #
                # =========================================

                cur.execute(
                    """
                    SELECT COALESCE(
                        MAX(
                            CAST(
                                SUBSTRING(
                                    admission_number
                                    FROM 4
                                ) AS INTEGER
                            )
                        ),
                        0
                    )
                    FROM students
                    WHERE admission_number
                          LIKE 'STU%'
                    """
                )

                last_number = cur.fetchone()[0]

                next_number = last_number + 1

                admission_number = (
                    f"STU{next_number:03d}"
                )

                # =========================================
                # CREATE LOGIN ACCOUNT
                # =========================================

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
                            'STUDENT',
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

                # =========================================
                # CREATE STUDENT PROFILE
                # =========================================

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

                # =========================================
                # CREATE ENROLLMENT
                # =========================================

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
                        (
                            %s,
                            %s,
                            %s,
                            'ACTIVE'
                        )
                    """,
                    (
                        student_id,
                        class_id,
                        academic_year_id
                    )
                )

                # =========================================
                # CREATE PARENT CONTACT RECORD
                # =========================================

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
                            (
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
                            parent_name,
                            "Parent",
                            parent_mobile,
                            parent_email,
                            address
                        )
                    )

            # =============================================
            # COMMIT TRANSACTION
            # =============================================

            conn.commit()

        except Exception as e:

            conn.rollback()

            return (
                f"Error creating student: {e}"
            )

        finally:

            conn.close()

        # =============================================
        # STUDENT CREATED SUCCESSFULLY
        # =============================================

        return redirect(
            url_for("student.student_list")
        )

    # =====================================================
    # SHOW ADD STUDENT PAGE
    # =====================================================

    return render_template(
        "add_student.html",
        classes=classes,
        academic_years=academic_years
    )


# =========================================================
# ADMIN - ACTIVATE / DEACTIVATE STUDENT
# =========================================================

@student.route(
    "/admin/students/toggle/<int:student_id>",
    methods=["POST"]
)
def toggle_student(student_id):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("auth.login")
        )

    # -----------------------------------------------------
    # ONLY ADMIN
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":

        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =============================================
            # GET STUDENT USER ACCOUNT
            # =============================================

            cur.execute(
                """
                SELECT
                    u.id,
                    u.is_active
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

            # =============================================
            # TOGGLE STATUS
            # =============================================

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

        return (
            f"Error updating student status: {e}"
        )

    finally:

        conn.close()

    return redirect(
        url_for("student.student_list")
    )