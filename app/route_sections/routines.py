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
from app.models import HouseholdSettings, PointTransaction, Routine, RoutineCompletion, User
from app.services.badge_service import check_and_award_badges
from app.services.notification_service import create_notification
from app.services.points_service import format_points
from app.services.settings_service import get_household_settings


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
        settings = get_household_settings()
        auto_end = settings.auto_end_streaks

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
                "streak": routine.current_streak_for_user(current_user.id, auto_end=auto_end)
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
            completed_date=today,
            voided=False
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

        check_and_award_badges(current_user)
        db.session.commit()

        settings = get_household_settings()
        streak = routine.current_streak_for_user(current_user.id, auto_end=settings.auto_end_streaks)

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

        settings = get_household_settings()
        auto_end = settings.auto_end_streaks

        # Build per-routine streak summaries for routines the user has done
        routine_ids = list({c.routine_id for c in completions})
        routines_with_streaks = []

        for routine_id in routine_ids:
            routine = db.session.get(Routine, routine_id)
            if routine:
                routines_with_streaks.append({
                    "routine": routine,
                    "streak": routine.current_streak_for_user(current_user.id, auto_end=auto_end),
                    "total_completions": sum(
                        1 for c in completions if c.routine_id == routine_id and not c.voided
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

    # =========================================================
    # ADMIN: ROUTINE COMPLETION HISTORY
    # =========================================================

    @bp.route("/admin/routines/completions")
    @login_required
    def admin_routine_completions():
        """
        Admin-only view of all routine completions across all users.

        Admins can reject a completion (reverse points, notify user) or
        end a user's streak (void all their completions for that routine).
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user_filter = request.args.get("user_id", type=int)
        routine_filter = request.args.get("routine_id", type=int)
        show_voided = request.args.get("show_voided") == "1"

        query = RoutineCompletion.query

        if not show_voided:
            query = query.filter_by(voided=False)

        if user_filter:
            query = query.filter_by(user_id=user_filter)

        if routine_filter:
            query = query.filter_by(routine_id=routine_filter)

        completions = query.order_by(
            RoutineCompletion.completed_date.desc(),
            RoutineCompletion.created_at.desc()
        ).all()

        all_users = User.query.filter_by(
            is_active_account=True, role="user"
        ).order_by(User.display_name).all()

        all_routines = Routine.query.order_by(Routine.title).all()

        return render_template(
            "admin_routine_completions.html",
            completions=completions,
            all_users=all_users,
            all_routines=all_routines,
            user_filter=user_filter,
            routine_filter=routine_filter,
            show_voided=show_voided,
        )

    @bp.route("/admin/routines/completions/<int:completion_id>/reject", methods=["POST"])
    @login_required
    def admin_reject_completion(completion_id):
        """
        Void a routine completion and reverse the points earned.

        Creates a negative PointTransaction and a Notification for the user.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        completion = db.session.get(RoutineCompletion, completion_id)

        if not completion or completion.voided:
            flash("Completion not found or already voided.")
            return redirect(url_for("main.admin_routine_completions"))

        routine = db.session.get(Routine, completion.routine_id)
        user = db.session.get(User, completion.user_id)

        completion.voided = True

        if routine and routine.point_value > 0:
            reversal = PointTransaction(
                user_id=completion.user_id,
                amount=-routine.point_value,
                transaction_type="routine_rejected",
                reason=f"Routine completion rejected by admin: {routine.title} ({completion.completed_date})",
                created_by_id=current_user.id
            )
            db.session.add(reversal)

            if user:
                create_notification(
                    user_id=user.id,
                    title="Routine completion rejected",
                    message=(
                        f"Your '{routine.title}' completion on "
                        f"{completion.completed_date.strftime('%-d %b')} was rejected "
                        f"and {routine.point_value} point(s) have been reversed."
                    ),
                    notification_type="warning",
                    action_url=url_for("main.routine_history"),
                    action_label="View History"
                )

        db.session.commit()

        flash(f"Completion rejected and points reversed for {user.display_name if user else 'user'}.")
        return redirect(url_for("main.admin_routine_completions"))

    @bp.route("/admin/routines/<int:routine_id>/users/<int:user_id>/end-streak", methods=["POST"])
    @login_required
    def admin_end_streak(routine_id, user_id):
        """
        Void all non-voided completions for a user on a specific routine.

        This resets their streak to 0. Used by admins when auto_end_streaks
        is disabled and a manual reset is needed.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        routine = db.session.get(Routine, routine_id)
        user = db.session.get(User, user_id)

        if not routine or not user:
            flash("Routine or user not found.")
            return redirect(url_for("main.admin_routine_completions"))

        active_completions = RoutineCompletion.query.filter_by(
            routine_id=routine_id,
            user_id=user_id,
            voided=False
        ).all()

        for c in active_completions:
            c.voided = True

        create_notification(
            user_id=user_id,
            title="Streak ended",
            message=f"Your streak for '{routine.title}' has been reset by an admin.",
            notification_type="info",
            action_url=url_for("main.routines"),
            action_label="View Routines"
        )

        db.session.commit()

        flash(f"Streak ended for {user.display_name} on '{routine.title}'.")
        return redirect(url_for("main.admin_routine_completions"))
