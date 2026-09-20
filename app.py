from flask import Flask, redirect, url_for, session, render_template

from db import get_connection

from auth import auth
from teacher import teacher
from student import student


app = Flask(__name__)

app.secret_key = "smart-preschool-secret-key"


# =========================================================
# REGISTER BLUEPRINTS
# =========================================================

app.register_blueprint(auth)
app.register_blueprint(teacher)
app.register_blueprint(student)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return redirect(url_for("auth.login"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # Total teachers
            cur.execute("SELECT COUNT(*) FROM teachers")
            teacher_count = cur.fetchone()[0]

            # Total students
            cur.execute("SELECT COUNT(*) FROM students")
            student_count = cur.fetchone()[0]

            # Total classes
            cur.execute("SELECT COUNT(*) FROM classes")
            class_count = cur.fetchone()[0]

            # Total learning activities
            cur.execute("SELECT COUNT(*) FROM learning_activities")
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

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("role") != "TEACHER":
        return "Access Denied", 403

    return render_template("teacher_dashboard.html")


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student/dashboard")
def student_dashboard():

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # CHECK ROLE
    # -----------------------------------------------------

    if session.get("role") != "STUDENT":
        return "Access Denied", 403

    # -----------------------------------------------------
    # GET LOGGED-IN USER ID
    # -----------------------------------------------------

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

            # -------------------------------------------------
            # STUDENT RECORD NOT FOUND
            # -------------------------------------------------

            if not student_data:
                return "Student record not found.", 404

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
                                THEN (score / max_score) * 100
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

            # Convert PostgreSQL Decimal to Python float
            average_score = float(cur.fetchone()[0] or 0)


            # -------------------------------------------------
            # Keep score between 0 and 100
            # -------------------------------------------------

            average_score = max(0, min(100, average_score))


            # =================================================
            # 4. TOTAL ATTEMPTS
            # =================================================

            cur.execute(
                """
                SELECT COALESCE(SUM(attempts), 0)
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
                ORDER BY activity_date DESC, id DESC
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
                ORDER BY generated_date DESC, id DESC
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