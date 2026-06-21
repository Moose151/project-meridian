"""
Admin report and backup routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.admin_reports and main.backup_database stay unchanged.
"""

import csv
import json
from datetime import datetime, timedelta
from io import StringIO
import os

from flask import Response, flash, redirect, render_template, send_file, url_for
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import PointTransaction, RoutineCompletion, TaskCompletion, User
from app.services.report_service import (
    build_points_report_rows,
    build_rewards_report_rows,
    build_tasks_report_rows,
    build_users_report_rows,
)


def make_csv_response(filename, rows):
    """
    Create a downloadable CSV response.

    rows should be a list of lists.
    The first row should normally be the header row.
    """

    output = StringIO()
    writer = csv.writer(output)

    for row in rows:
        writer.writerow(row)

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


def register_admin_export_routes(bp, admin_required):
    """
    Register admin reports, CSV exports, and database backup routes.
    """

    @bp.route("/admin/reports")
    @login_required
    def admin_reports():
        """
        Admin-only reports page.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        # Build last-12-weeks chart data.
        today = datetime.utcnow().date()
        weeks = []
        points_per_week = []
        tasks_per_week = []
        routines_per_week = []

        for i in range(11, -1, -1):
            week_start = today - timedelta(weeks=i, days=today.weekday())
            week_end = week_start + timedelta(days=7)
            label = week_start.strftime("%-d %b")
            weeks.append(label)

            pts = db.session.query(func.coalesce(func.sum(PointTransaction.amount), 0)).filter(
                PointTransaction.amount > 0,
                func.date(PointTransaction.created_at) >= week_start,
                func.date(PointTransaction.created_at) < week_end,
            ).scalar() or 0
            points_per_week.append(int(pts))

            tc = TaskCompletion.query.filter(
                TaskCompletion.status == "approved",
                func.date(TaskCompletion.reviewed_at) >= week_start,
                func.date(TaskCompletion.reviewed_at) < week_end,
            ).count()
            tasks_per_week.append(tc)

            rc = RoutineCompletion.query.filter(
                RoutineCompletion.completed_date >= week_start,
                RoutineCompletion.completed_date < week_end,
            ).count()
            routines_per_week.append(rc)

        # Per-user points breakdown for a doughnut chart.
        users = User.query.filter_by(is_active_account=True).all()
        user_labels = [u.display_name for u in users]
        user_balances = [max(u.point_balance(), 0) for u in users]

        return render_template(
            "admin_reports.html",
            chart_weeks=json.dumps(weeks),
            chart_points=json.dumps(points_per_week),
            chart_tasks=json.dumps(tasks_per_week),
            chart_routines=json.dumps(routines_per_week),
            chart_user_labels=json.dumps(user_labels),
            chart_user_balances=json.dumps(user_balances),
        )

    @bp.route("/admin/reports/users.csv")
    @login_required
    def export_users_csv():
        """
        Export user summary data as CSV.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        return make_csv_response(
            "meridian_users_report.csv",
            build_users_report_rows()
        )

    @bp.route("/admin/reports/points.csv")
    @login_required
    def export_points_csv():
        """
        Export the full point transaction ledger as CSV.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        return make_csv_response(
            "meridian_point_history.csv",
            build_points_report_rows()
        )

    @bp.route("/admin/reports/tasks.csv")
    @login_required
    def export_tasks_csv():
        """
        Export task completion activity as CSV.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        return make_csv_response(
            "meridian_task_activity.csv",
            build_tasks_report_rows()
        )

    @bp.route("/admin/reports/rewards.csv")
    @login_required
    def export_rewards_csv():
        """
        Export reward request activity as CSV.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        return make_csv_response(
            "meridian_reward_requests.csv",
            build_rewards_report_rows()
        )

    @bp.route("/admin/backup")
    @login_required
    def backup_database():
        """
        Admin-only database backup route.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "instance",
            "meridian.db"
        )

        if not os.path.exists(db_path):
            flash("Database file not found.")
            return redirect(url_for("main.dashboard"))

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_filename = f"project-meridian-backup-{timestamp}.db"

        return send_file(
            db_path,
            as_attachment=True,
            download_name=backup_filename
        )
