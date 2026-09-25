from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection


academic_year = Blueprint("academic_year", __name__)


# =========================================================
# ADMIN - ACADEMIC YEAR LIST
# =========================================================

@academic_year.route("/admin/academic-years")
def academic_year_list():

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    year_name,
                    start_date,
                    end_date,
                    is_current,
                    created_at
                FROM academic_years
                ORDER BY start_date DESC
                """
            )

            academic_years = cur.fetchall()

    finally:

        conn.close()

    return render_template(
        "academic_years.html",
        academic_years=academic_years
    )


# =========================================================
# ADMIN - ADD ACADEMIC YEAR
# =========================================================

@academic_year.route(
    "/admin/academic-years/add",
    methods=["GET", "POST"]
)
def add_academic_year():

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    # -----------------------------------------------------
    # FORM SUBMISSION
    # -----------------------------------------------------

    if request.method == "POST":

        year_name = request.form.get(
            "year_name",
            ""
        ).strip()

        start_date = request.form.get(
            "start_date",
            ""
        ).strip()

        end_date = request.form.get(
            "end_date",
            ""
        ).strip()

        is_current = request.form.get(
            "is_current"
        ) == "on"

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not year_name:
            return "Academic year name is required."

        if not start_date:
            return "Start date is required."

        if not end_date:
            return "End date is required."

        if start_date >= end_date:
            return "End date must be after start date."

        conn = get_connection()

        try:

            with conn.cursor() as cur:

                # -----------------------------------------
                # CHECK DUPLICATE YEAR
                # -----------------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM academic_years
                    WHERE year_name = %s
                    """,
                    (year_name,)
                )

                existing_year = cur.fetchone()

                if existing_year:
                    return "This academic year already exists."

                # -----------------------------------------
                # IF THIS YEAR IS CURRENT,
                # MAKE ALL OTHER YEARS NON-CURRENT
                # -----------------------------------------

                if is_current:

                    cur.execute(
                        """
                        UPDATE academic_years
                        SET is_current = FALSE
                        """
                    )

                # -----------------------------------------
                # INSERT NEW ACADEMIC YEAR
                # -----------------------------------------

                cur.execute(
                    """
                    INSERT INTO academic_years
                    (
                        year_name,
                        start_date,
                        end_date,
                        is_current
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        year_name,
                        start_date,
                        end_date,
                        is_current
                    )
                )

            conn.commit()

        except Exception as e:

            conn.rollback()

            return f"Error creating academic year: {e}"

        finally:

            conn.close()

        return redirect(
            url_for("academic_year.academic_year_list")
        )

    return render_template(
        "add_academic_year.html"
    )


# =========================================================
# ADMIN - EDIT / UPDATE ACADEMIC YEAR
# =========================================================

@academic_year.route(
    "/admin/academic-years/edit/<int:year_id>",
    methods=["GET", "POST"]
)
def edit_academic_year(year_id):

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # GET EXISTING ACADEMIC YEAR
            # =================================================

            cur.execute(
                """
                SELECT
                    id,
                    year_name,
                    start_date,
                    end_date,
                    is_current
                FROM academic_years
                WHERE id = %s
                """,
                (year_id,)
            )

            academic_year_data = cur.fetchone()

            if not academic_year_data:

                return "Academic year not found.", 404

            # =================================================
            # UPDATE
            # =================================================

            if request.method == "POST":

                year_name = request.form.get(
                    "year_name",
                    ""
                ).strip()

                start_date = request.form.get(
                    "start_date",
                    ""
                ).strip()

                end_date = request.form.get(
                    "end_date",
                    ""
                ).strip()

                is_current = request.form.get(
                    "is_current"
                ) == "on"

                # ---------------------------------------------
                # VALIDATION
                # ---------------------------------------------

                if not year_name:
                    return "Academic year name is required."

                if not start_date:
                    return "Start date is required."

                if not end_date:
                    return "End date is required."

                if start_date >= end_date:
                    return "End date must be after start date."

                # ---------------------------------------------
                # CHECK DUPLICATE YEAR NAME
                # ---------------------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM academic_years
                    WHERE year_name = %s
                      AND id != %s
                    """,
                    (
                        year_name,
                        year_id
                    )
                )

                duplicate_year = cur.fetchone()

                if duplicate_year:

                    return (
                        "Another academic year "
                        "with this name already exists."
                    )

                # ---------------------------------------------
                # IF THIS YEAR IS CURRENT,
                # MAKE OTHER YEARS NON-CURRENT
                # ---------------------------------------------

                if is_current:

                    cur.execute(
                        """
                        UPDATE academic_years
                        SET is_current = FALSE
                        WHERE id != %s
                        """,
                        (year_id,)
                    )

                # ---------------------------------------------
                # UPDATE ACADEMIC YEAR
                # ---------------------------------------------

                cur.execute(
                    """
                    UPDATE academic_years
                    SET
                        year_name = %s,
                        start_date = %s,
                        end_date = %s,
                        is_current = %s
                    WHERE id = %s
                    """,
                    (
                        year_name,
                        start_date,
                        end_date,
                        is_current,
                        year_id
                    )
                )

            conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error updating academic year: {e}"

    finally:

        conn.close()

    # =====================================================
    # AFTER UPDATE
    # =====================================================

    if request.method == "POST":

        return redirect(
            url_for(
                "academic_year.academic_year_list"
            )
        )

    # =====================================================
    # SHOW EDIT PAGE
    # =====================================================

    return render_template(
        "edit_academic_year.html",
        academic_year=academic_year_data
    )


# =========================================================
# ADMIN - SET CURRENT ACADEMIC YEAR
# =========================================================

@academic_year.route(
    "/admin/academic-years/set-current/<int:year_id>",
    methods=["POST"]
)
def set_current_academic_year(year_id):

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if session.get("role") != "ADMIN":
        return "Access Denied", 403

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # Make all years non-current

            cur.execute(
                """
                UPDATE academic_years
                SET is_current = FALSE
                """
            )

            # Set selected year as current

            cur.execute(
                """
                UPDATE academic_years
                SET is_current = TRUE
                WHERE id = %s
                """,
                (year_id,)
            )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return f"Error setting current academic year: {e}"

    finally:

        conn.close()

    return redirect(
        url_for(
            "academic_year.academic_year_list"
        )
    )