"""
Routine routes: habit tracking for users and admin management.

Points are awarded immediately on completion — no approval needed.
Streaks are tracked via consecutive RoutineCompletion dates.
"""

from datetime import date, datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.forms import RoutineForm
from app.models import PointTransaction, Routine, RoutineCompletion, User
from app.services.points_service import format_points


def _routine_user_choices():
    """
    Build user dropdown choices for routine assignment.

    Includes only active standard users. Returns a list starting with
    the "all users" option (value 0).
    """

    users = User.query.filter_by(
        is_active_account=True,
        role="user"
    ).order_by(
        User.display_name
    ).all()

    choices = [(0, "All users (no specific assignment)")]

    for user in users:
        choices.append((user.id, f"{user.avatar_emoji} {user.display_name}"))

    return choices


def register_routine_routes(bp, admin_required):
    """
    Register routine routes for user completion and admin management.
    """

    # =========================================================
    # USER: VIEW AND COMPLETE ROUTINES
    # =========================================================

    @bp.route("/routines")
    @login_required
    def routines():
        """
        Routines page for participating users.

        Shows active routines assigned to the current user or all users,
        along with today's completion status and streak.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to view routines.")
            return redirect(url_for("main.dashboard"))

        today = date.today()

        active_routines = Routine.query.filter_by(
            is_active=True
        ).filter(
            or_(
                Routine.assigned_user_id == None,
                Routine.assigned_user_id == current_user.id
            )
        ).order_by(
            Routine.title
        ).all()

        routine_data = []
        for routine in active_routines:
            routine_data.append({
                "routine": routine,
                "completed_today": routine.completed_today_by_user(current_user.id),
                "streak": routine.current_streak_for_user(current_user.id)
            })

        return render_template(
            "routines.html",
            routine_data=routine_data,
            today=today
        )

    @bp.route("/routines/<int:routine_id>/complete", methods=["POST"])
    @login_required
    def complete_routine(routine_id):
        """
        Mark a routine as complete for today.

        Awards points immediately without admin approval.
        Limited to once per day per user per routine.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to complete routines.")
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)

        if not routine or not routine.is_active:
            flash("Routine not found.")
            return redirect(url_for("main.routines"))

        if routine.assigned_user_id and routine.assigned_user_id != current_user.id:
            flash("This routine is assigned to another user.")
            return redirect(url_for("main.routines"))

        today = date.today()

        existing = RoutineCompletion.query.filter_by(
            routine_id=routine.id,
            user_id=current_user.id,
            completed_date=today
        ).first()

        if existing:
            flash(f"You already completed '{routine.title}' today.")
            return redirect(url_for("main.routines"))

        completion = RoutineCompletion(
            routine_id=routine.id,
            user_id=current_user.id,
            completed_date=today
        )

        db.session.add(completion)
        db.session.flush()

        if routine.point_value > 0:
            transaction = PointTransaction(
                user_id=current_user.id,
                amount=routine.point_value,
                transaction_type="routine_completed",
                reason=f"Routine completed: {routine.title}",
                created_by_id=current_user.id
            )
            db.session.add(transaction)

        db.session.commit()

        streak = routine.current_streak_for_user(current_user.id)

        msg = f"'{routine.title}' completed!"
        if routine.point_value > 0:
            msg += f" You earned {format_points(routine.point_value)}."
        if streak > 1:
            msg += f" {streak}-day streak!"

        flash(msg)
        return redirect(url_for("main.routines"))

    @bp.route("/routines/history")
    @login_required
    def routine_history():
        """
        User routine history page.

        Shows recent completions and streak information.
        """

        if not current_user.can_participate():
            return redirect(url_for("main.dashboard"))

        completions = RoutineCompletion.query.filter_by(
            user_id=current_user.id
        ).order_by(
            RoutineCompletion.completed_date.desc(),
            RoutineCompletion.created_at.desc()
        ).limit(90).all()

        # Build per-routine streak summaries for routines the user has done
        routine_ids = list({c.routine_id for c in completions})
        routines_with_streaks = []

        for routine_id in routine_ids:
            routine = db.session.get(Routine, routine_id)
            if routine:
                routines_with_streaks.append({
                    "routine": routine,
                    "streak": routine.current_streak_for_user(current_user.id),
                    "total_completions": sum(
                        1 for c in completions if c.routine_id == routine_id
                    )
                })

        routines_with_streaks.sort(key=lambda r: r["streak"], reverse=True)

        return render_template(
            "routine_history.html",
            completions=completions,
            routines_with_streaks=routines_with_streaks
        )

    # =========================================================
    # ADMIN: MANAGE ROUTINES
    # =========================================================

    @bp.route("/admin/routines")
    @login_required
    def manage_routines():
        """
        Admin-only routine management page.

        Shows all active and hidden routines.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        all_routines = Routine.query.order_by(Routine.created_at.desc()).all()

        return render_template("manage_routines.html", routines=all_routines)

    @bp.route("/admin/routines/create", methods=["GET", "POST"])
    @login_required
    def create_routine():
        """
        Admin-only page for creating a new routine.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = RoutineForm()
        form.assigned_user_id.choices = _routine_user_choices()

        if form.validate_on_submit():
            assigned_user_id = form.assigned_user_id.data
            if assigned_user_id == 0:
                assigned_user_id = None

            routine = Routine(
                title=form.title.data,
                description=form.description.data,
                point_value=form.point_value.data,
                assigned_user_id=assigned_user_id,
                is_active=True
            )

            db.session.add(routine)
            db.session.commit()

            flash("Routine created.")
            return redirect(url_for("main.manage_routines"))

        return render_template("create_routine.html", form=form)

    @bp.route("/admin/routines/<int:routine_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_routine(routine_id):
        """
        Admin-only page for editing an existing routine.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)

        if not routine:
            flash("Routine not found.")
            return redirect(url_for("main.manage_routines"))

        form = RoutineForm(obj=routine)
        form.assigned_user_id.choices = _routine_user_choices()

        if request.method == "GET":
            form.assigned_user_id.data = routine.assigned_user_id or 0

        if form.validate_on_submit():
            assigned_user_id = form.assigned_user_id.data
            if assigned_user_id == 0:
                assigned_user_id = None

            routine.title = form.title.data
            routine.description = form.description.data
            routine.point_value = form.point_value.data
            routine.assigned_user_id = assigned_user_id

            db.session.commit()

            flash("Routine updated.")
            return redirect(url_for("main.manage_routines"))

        return render_template("edit_routine.html", form=form, routine=routine)

    @bp.route("/admin/routines/<int:routine_id>/hide", methods=["POST"])
    @login_required
    def hide_routine(routine_id):
        """
        Hide an active routine.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)

        if not routine:
            flash("Routine not found.")
            return redirect(url_for("main.manage_routines"))

        routine.is_active = False
        db.session.commit()

        flash("Routine hidden.")
        return redirect(url_for("main.manage_routines"))

    @bp.route("/admin/routines/<int:routine_id>/restore", methods=["POST"])
    @login_required
    def restore_routine(routine_id):
        """
        Restore a hidden routine.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)

        if not routine:
            flash("Routine not found.")
            return redirect(url_for("main.manage_routines"))

        routine.is_active = True
        db.session.commit()

        flash("Routine restored.")
        return redirect(url_for("main.manage_routines"))

    @bp.route("/admin/routines/<int:routine_id>/delete", methods=["POST"])
    @login_required
    def delete_routine(routine_id):
        """
        Delete a routine if it has no completion history.

        If it has history, hide it instead.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)

        if not routine:
            flash("Routine not found.")
            return redirect(url_for("main.manage_routines"))

        if routine.completions:
            routine.is_active = False
            db.session.commit()
            flash("This routine has history and cannot be deleted. It has been hidden instead.")
            return redirect(url_for("main.manage_routines"))

        db.session.delete(routine)
        db.session.commit()

        flash("Routine deleted.")
        return redirect(url_for("main.manage_routines"))
