from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
import bcrypt


student = Blueprint("student", __name__)


# ============================================================
# ADMIN - STUDENT LIST
# ============================================================

@student.route("/admin/students")
def admin_students():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
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
                    u.email,
                    u.mobile,
                    u.is_active
                FROM students s
                JOIN users u
                    ON s.user_id = u.id
                ORDER BY s.id
            """)

            students = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "admin_students.html",
        students=students
    )


# ============================================================
# ADMIN - ADD STUDENT
# ============================================================

@student.route("/admin/students/add", methods=["GET", "POST"])
def add_student():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # GET REQUEST
            # ------------------------------------------------

            if request.method == "GET":

                cur.execute("""
                    SELECT
                        id,
                        class_name,
                        class_order
                    FROM classes
                    ORDER BY class_order
                """)

                classes = cur.fetchall()

                cur.execute("""
                    SELECT
                        id,
                        year_name,
                        start_date,
                        end_date
                    FROM academic_years
                    ORDER BY start_date DESC
                """)

                academic_years = cur.fetchall()

                cur.execute("""
                    SELECT
                        id,
                        teacher_name
                    FROM teachers
                    ORDER BY teacher_name
                """)

                teachers = cur.fetchall()

                return render_template(
                    "admin_add_student.html",
                    classes=classes,
                    academic_years=academic_years,
                    teachers=teachers
                )

            # ------------------------------------------------
            # POST REQUEST
            # ------------------------------------------------

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            mobile = request.form.get("mobile", "").strip()
            password = request.form.get("password", "")

            admission_number = request.form.get(
                "admission_number",
                ""
            ).strip()

            date_of_birth = request.form.get(
                "date_of_birth"
            ) or None

            gender = request.form.get(
                "gender",
                ""
            ).strip()

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
            ).strip()

            address = request.form.get(
                "address",
                ""
            ).strip()

            class_id = request.form.get(
                "class_id"
            )

            academic_year_id = request.form.get(
                "academic_year_id"
            )

            # Teacher is optional because the class-teacher
            # relationship is handled separately.
            teacher_id = request.form.get(
                "teacher_id"
            ) or None

            # ------------------------------------------------
            # BASIC VALIDATION
            # ------------------------------------------------

            if not name or not email or not password:
                return "Name, email and password are required."

            if not admission_number:
                return "Admission number is required."

            if not class_id or not academic_year_id:
                return "Class and academic year are required."

            # ------------------------------------------------
            # CHECK DUPLICATE EMAIL
            # ------------------------------------------------

            cur.execute("""
                SELECT id
                FROM users
                WHERE email = %s
            """, (email,))

            existing_user = cur.fetchone()

            if existing_user:
                return "Email already exists."

            # ------------------------------------------------
            # CHECK DUPLICATE ADMISSION NUMBER
            # ------------------------------------------------

            cur.execute("""
                SELECT id
                FROM students
                WHERE admission_number = %s
            """, (admission_number,))

            existing_admission = cur.fetchone()

            if existing_admission:
                return "Admission number already exists."

            # ------------------------------------------------
            # HASH PASSWORD
            # ------------------------------------------------

            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            # ------------------------------------------------
            # CREATE USER
            # ------------------------------------------------

            cur.execute("""
                INSERT INTO users
                (
                    name,
                    email,
                    password_hash,
                    mobile,
                    role,
                    is_active
                )
                VALUES
                (%s, %s, %s, %s, 'STUDENT', TRUE)
                RETURNING id
            """, (
                name,
                email,
                password_hash,
                mobile or None
            ))

            user_id = cur.fetchone()[0]

            # ------------------------------------------------
            # CREATE STUDENT
            # ------------------------------------------------

            cur.execute("""
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
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id
            """, (
                user_id,
                name,
                admission_number,
                date_of_birth,
                gender or None,
                parent_name or None,
                parent_mobile or None,
                parent_email or None,
                address or None
            ))

            student_id = cur.fetchone()[0]

            # ------------------------------------------------
            # CREATE ENROLLMENT
            # ------------------------------------------------

            cur.execute("""
                INSERT INTO student_enrollments
                (
                    student_id,
                    class_id,
                    academic_year_id,
                    teacher_id,
                    status
                )
                VALUES
                (
                    %s, %s, %s, %s, 'ACTIVE'
                )
            """, (
                student_id,
                class_id,
                academic_year_id,
                teacher_id
            ))

            # ------------------------------------------------
            # CREATE PARENT RECORD
            # ------------------------------------------------

            if parent_name:

                cur.execute("""
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
                        %s, %s, %s, %s, %s, %s
                    )
                """, (
                    student_id,
                    parent_name,
                    request.form.get(
                        "relationship",
                        ""
                    ).strip() or None,
                    parent_mobile or None,
                    parent_email or None,
                    address or None
                ))

            conn.commit()

            return redirect(
                url_for("student.admin_students")
            )

    except Exception as e:

        conn.rollback()

        return f"""
        <h2>Error while creating student</h2>
        <p>{e}</p>
        <a href="{url_for('student.add_student')}">
            Go Back
        </a>
        """

    finally:
        conn.close()


# ============================================================
# ADMIN - TOGGLE STUDENT ACTIVE / INACTIVE
# ============================================================

@student.route(
    "/admin/students/toggle/<int:student_id>",
    methods=["POST"]
)
def toggle_student(student_id):

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT u.id, u.is_active
                FROM students s
                JOIN users u
                    ON s.user_id = u.id
                WHERE s.id = %s
            """, (student_id,))

            student_data = cur.fetchone()

            if not student_data:
                return "Student not found.", 404

            user_id = student_data[0]
            current_status = student_data[1]

            cur.execute("""
                UPDATE users
                SET is_active = %s
                WHERE id = %s
            """, (
                not current_status,
                user_id
            ))

        conn.commit()

    finally:
        conn.close()

    return redirect(
        url_for("student.admin_students")
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@student.route("/student/dashboard")
def student_dashboard():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # --------------------------------------------------------
    # ROLE CHECK
    # --------------------------------------------------------

    if session.get("role") != "STUDENT":
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # STUDENT PROFILE + CURRENT ENROLLMENT
            # =================================================

            cur.execute("""
                SELECT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.date_of_birth,
                    s.gender,
                    s.parent_name,
                    s.parent_mobile,
                    s.parent_email,
                    se.id AS enrollment_id,
                    c.class_name,
                    ay.year_name,
                    se.status
                FROM students s

                JOIN student_enrollments se
                    ON s.id = se.student_id

                JOIN classes c
                    ON se.class_id = c.id

                JOIN academic_years ay
                    ON se.academic_year_id = ay.id

                JOIN users u
                    ON s.user_id = u.id

                WHERE u.id = %s
                  AND se.status = 'ACTIVE'

                ORDER BY ay.start_date DESC

                LIMIT 1
            """, (user_id,))

            student_data = cur.fetchone()

            if not student_data:
                return """
                    <h2>Student profile not found.</h2>
                    <p>
                        Your account exists, but no active student
                        enrollment was found.
                    </p>
                """, 404

            # =================================================
            # MAP STUDENT DATA
            # =================================================

            student_id = student_data[0]

            student_name = student_data[1]

            admission_number = student_data[2]

            date_of_birth = student_data[3]

            gender = student_data[4]

            parent_name = student_data[5]

            parent_mobile = student_data[6]

            parent_email = student_data[7]

            enrollment_id = student_data[8]

            class_name = student_data[9]

            academic_year = student_data[10]

            enrollment_status = student_data[11]

            # =================================================
            # LEARNING ACTIVITIES
            # =================================================

            cur.execute("""
                SELECT
                    activity_name,
                    activity_date,
                    score,
                    max_score,
                    attempts,
                    time_taken_seconds,
                    remarks
                FROM learning_activities
                WHERE student_id = %s
                  AND (
                        enrollment_id = %s
                        OR enrollment_id IS NULL
                      )
                ORDER BY activity_date DESC, id DESC
            """, (
                student_id,
                enrollment_id
            ))

            activities = cur.fetchall()

            # =================================================
            # ACTIVITY COUNT
            # =================================================

            cur.execute("""
                SELECT COUNT(*)
                FROM learning_activities
                WHERE student_id = %s
            """, (student_id,))

            total_activities = cur.fetchone()[0]

            # =================================================
            # AVERAGE SCORE
            # =================================================

            cur.execute("""
                SELECT
                    COALESCE(
                        AVG(
                            CASE
                                WHEN max_score > 0
                                THEN (score / max_score) * 100
                                ELSE NULL
                            END
                        ),
                        0
                    )
                FROM learning_activities
                WHERE student_id = %s
                  AND score IS NOT NULL
            """, (student_id,))

            average_score = cur.fetchone()[0]

            if average_score is None:
                average_score = 0

            # =================================================
            # TOTAL ATTEMPTS
            # =================================================

            cur.execute("""
                SELECT
                    COALESCE(SUM(attempts), 0)
                FROM learning_activities
                WHERE student_id = %s
            """, (student_id,))

            total_attempts = cur.fetchone()[0]

            # =================================================
            # RECOMMENDATIONS
            # =================================================

            cur.execute("""
                SELECT
                    learning_area,
                    recommendation,
                    generated_date
                FROM recommendations
                WHERE student_id = %s
                ORDER BY generated_date DESC, id DESC
                LIMIT 5
            """, (student_id,))

            recommendations = cur.fetchall()

            # =================================================
            # PERFORMANCE SUMMARY
            # =================================================

            performance = {
                "average_score": round(
                    float(average_score), 2
                ),
                "total_activities": total_activities,
                "total_attempts": total_attempts
            }

    finally:
        conn.close()

    # ========================================================
    # RENDER STUDENT DASHBOARD
    # ========================================================

    return render_template(
        "student_dashboard.html",

        # Original object
        student=student_data,

        # Student profile
        student_name=student_name,
        admission_number=admission_number,
        date_of_birth=date_of_birth,
        gender=gender,
        parent_name=parent_name,
        parent_mobile=parent_mobile,
        parent_email=parent_email,

        # Academic information
        class_name=class_name,
        academic_year=academic_year,
        enrollment_status=enrollment_status,

        # Performance
        performance=performance,

        # Statistics
        total_activities=total_activities,
        activity_count=total_activities,
        average_score=round(
            float(average_score), 2
        ),
        total_attempts=total_attempts,

        # Activities
        activities=activities,
        recent_activities=activities,

        # Recommendations
        recommendations=recommendations
    )


# ============================================================
# STUDENT PROFILE
# ============================================================

@student.route("/student/profile")
def student_profile():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "STUDENT":
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute("""
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
                    u.email,
                    u.mobile,
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

                WHERE u.id = %s

                ORDER BY ay.start_date DESC NULLS LAST

                LIMIT 1
            """, (user_id,))

            student = cur.fetchone()

            if not student:
                return "Student profile not found.", 404

    finally:
        conn.close()

    return render_template(
        "student_profile.html",
        student=student
    )


# ============================================================
# STUDENT ACTIVITIES
# ============================================================

@student.route("/student/activities")
def student_activities():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "STUDENT":
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # FIND STUDENT
            # ------------------------------------------------

            cur.execute("""
                SELECT id, student_name
                FROM students
                WHERE user_id = %s
            """, (user_id,))

            student = cur.fetchone()

            if not student:
                return "Student profile not found.", 404

            student_id = student[0]
            student_name = student[1]

            # ------------------------------------------------
            # GET ACTIVITIES
            # ------------------------------------------------

            cur.execute("""
                SELECT
                    la.activity_name,
                    la.activity_date,
                    la.score,
                    la.max_score,
                    la.attempts,
                    la.time_taken_seconds,
                    la.remarks,
                    c.class_name
                FROM learning_activities la

                LEFT JOIN student_enrollments se
                    ON la.enrollment_id = se.id

                LEFT JOIN classes c
                    ON se.class_id = c.id

                WHERE la.student_id = %s

                ORDER BY
                    la.activity_date DESC,
                    la.id DESC
            """, (student_id,))

            activities = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "student_activities.html",
        student_name=student_name,
        activities=activities
    )