from flask import Flask, redirect, url_for, session, render_template

from db import get_connection

from auth import auth
from teacher import teacher
from student import student
from classes import classes
from academic_year import academic_year

app = Flask(__name__)

app.secret_key = "smart-preschool-secret-key"


# =========================================================
# REGISTER BLUEPRINTS
# =========================================================

app.register_blueprint(auth)
app.register_blueprint(teacher)
app.register_blueprint(student)
app.register_blueprint(classes)
app.register_blueprint(academic_year)

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return redirect(
        url_for("auth.login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

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

            # =================================================
            # TOTAL TEACHERS
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM teachers
                """
            )

            teacher_count = cur.fetchone()[0]


            # =================================================
            # TOTAL STUDENTS
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM students
                """
            )

            student_count = cur.fetchone()[0]


            # =================================================
            # TOTAL CLASSES
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM classes
                """
            )

            class_count = cur.fetchone()[0]


            # =================================================
            # TOTAL LEARNING ACTIVITIES
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM learning_activities
                """
            )

            activity_count = cur.fetchone()[0]

    finally:

        conn.close()


    return render_template(
        "admin_dashboard.html",

        teacher_count=teacher_count,

        student_count=student_count,

        class_count=class_count,

        activity_count=activity_count
    )


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route("/teacher/dashboard")
def teacher_dashboard():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("auth.login")
        )

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
            # GET TEACHER INFORMATION
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

                return (
                    "Teacher profile not found.",
                    404
                )

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

                return (
                    "Current academic year "
                    "not found.",
                    404
                )

            academic_year_id = current_year[0]

            academic_year_name = current_year[1]


            # =================================================
            # COUNT ASSIGNED STUDENTS
            # =================================================
            #
            # NEW RELATIONSHIP:
            #
            # Teacher
            #    ↓
            # Class Teacher Assignment
            #    ↓
            # Class
            #    ↓
            # Student Enrollment
            #    ↓
            # Student
            #
            # =================================================

            cur.execute(
                """
                SELECT COUNT(DISTINCT se.student_id)

                FROM student_enrollments se

                JOIN class_teacher_assignments cta
                    ON cta.class_id = se.class_id
                    AND cta.academic_year_id =
                        se.academic_year_id

                WHERE cta.teacher_id = %s
                  AND se.academic_year_id = %s
                  AND se.status = 'ACTIVE'
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            student_count = cur.fetchone()[0]


            # =================================================
            # COUNT LEARNING ACTIVITIES
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM learning_activities
                WHERE teacher_id = %s
                """,
                (teacher_id,)
            )

            activity_count = cur.fetchone()[0]


            # =================================================
            # COUNT ATTENDANCE THIS MONTH
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM attendance
                WHERE teacher_id = %s
                  AND DATE_TRUNC(
                        'month',
                        attendance_date
                      )
                      =
                      DATE_TRUNC(
                        'month',
                        CURRENT_DATE
                      )
                """,
                (teacher_id,)
            )

            attendance_count = cur.fetchone()[0]


            # =================================================
            # COUNT ASSESSMENTS
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM assessments
                WHERE teacher_id = %s
                """,
                (teacher_id,)
            )

            assessment_count = cur.fetchone()[0]


            # =================================================
            # COUNT ASSIGNED CLASSES
            # =================================================

            cur.execute(
                """
                SELECT COUNT(DISTINCT cta.class_id)
                FROM class_teacher_assignments cta
                WHERE cta.teacher_id = %s
                  AND cta.academic_year_id = %s
                """,
                (
                    teacher_id,
                    academic_year_id
                )
            )

            class_count = cur.fetchone()[0]

    finally:

        conn.close()


    # =========================================================
    # SEND DATA TO TEACHER DASHBOARD
    # =========================================================

    return render_template(
        "teacher_dashboard.html",

        teacher_name=teacher_name,

        student_count=student_count,

        activity_count=activity_count,

        attendance_count=attendance_count,

        assessment_count=assessment_count,

        class_count=class_count,

        academic_year_name=academic_year_name
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student/dashboard")
def student_dashboard():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("auth.login")
        )

    # -----------------------------------------------------
    # ONLY STUDENT
    # -----------------------------------------------------

    if session.get("role") != "STUDENT":

        return "Access Denied", 403

    user_id = session["user_id"]

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # 1. GET STUDENT BASIC INFORMATION
            # =================================================

            cur.execute(
                """
                SELECT
                    s.id,
                    s.student_name,
                    s.admission_number,
                    s.gender,
                    s.parent_name,
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

                WHERE s.user_id = %s
                """,
                (user_id,)
            )

            student_data = cur.fetchone()

            if not student_data:

                return (
                    "Student record not found.",
                    404
                )

            (
                student_id,
                student_name,
                admission_number,
                gender,
                parent_name,
                class_name,
                academic_year
            ) = student_data


            # =================================================
            # 2. TOTAL LEARNING ACTIVITIES
            # =================================================

            cur.execute(
                """
                SELECT COUNT(*)
                FROM learning_activities
                WHERE student_id = %s
                """,
                (student_id,)
            )

            activity_count = cur.fetchone()[0]


            # =================================================
            # 3. AVERAGE SCORE
            # =================================================

            cur.execute(
                """
                SELECT COALESCE(
                    ROUND(
                        AVG(
                            CASE
                                WHEN max_score > 0
                                     AND score IS NOT NULL
                                THEN
                                    (score / max_score) * 100
                            END
                        ),
                        2
                    ),
                    0
                )
                FROM learning_activities
                WHERE student_id = %s
                """,
                (student_id,)
            )

            average_score = float(
                cur.fetchone()[0] or 0
            )


            # Keep score between 0 and 100

            average_score = max(
                0,
                min(100, average_score)
            )


            # =================================================
            # 4. TOTAL ATTEMPTS
            # =================================================

            cur.execute(
                """
                SELECT COALESCE(
                    SUM(attempts),
                    0
                )
                FROM learning_activities
                WHERE student_id = %s
                """,
                (student_id,)
            )

            total_attempts = cur.fetchone()[0]


            # =================================================
            # 5. RECENT LEARNING ACTIVITIES
            # =================================================

            cur.execute(
                """
                SELECT
                    activity_name,
                    score,
                    max_score,
                    attempts,
                    time_taken_seconds,
                    activity_date
                FROM learning_activities
                WHERE student_id = %s
                ORDER BY
                    activity_date DESC,
                    id DESC
                LIMIT 5
                """,
                (student_id,)
            )

            recent_activities = cur.fetchall()


            # =================================================
            # 6. STUDENT RECOMMENDATIONS
            # =================================================

            cur.execute(
                """
                SELECT
                    learning_area,
                    recommendation,
                    generated_date
                FROM recommendations
                WHERE student_id = %s
                ORDER BY
                    generated_date DESC,
                    id DESC
                LIMIT 5
                """,
                (student_id,)
            )

            recommendations = cur.fetchall()

    finally:

        conn.close()


    # =========================================================
    # SEND DATA TO STUDENT DASHBOARD
    # =========================================================

    return render_template(
        "student_dashboard.html",

        # Student information

        student_id=student_id,

        student_name=student_name,

        admission_number=admission_number,

        gender=gender,

        parent_name=parent_name,

        class_name=class_name,

        academic_year=academic_year,

        # Statistics

        activity_count=activity_count,

        average_score=average_score,

        total_attempts=total_attempts,

        # Activities

        recent_activities=recent_activities,

        # Recommendations

        recommendations=recommendations
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )