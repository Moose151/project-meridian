"""
Group goal routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.group_goals and main.contribute_group_goal stay unchanged.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import GroupGoalContributionForm, GroupGoalForm
from app.models import GroupGoal, GroupGoalContribution, PointTransaction
from app.services.badge_service import check_and_award_badges
from app.services.notification_service import create_notification, notify_admins
from app.services.points_service import format_points
from app.services.settings_service import get_household_settings, get_points_label


def register_group_goal_routes(bp, admin_required):
    """
    Register group goal routes.
    """

    @bp.route("/group-goals")
    @login_required
    def group_goals():
        """
        Show active and completed group goals.
        """

        active_goals = GroupGoal.query.filter_by(
            is_active=True
        ).order_by(
            GroupGoal.created_at.desc()
        ).all()

        return render_template(
            "group_goals.html",
            goals=active_goals
        )

    @bp.route("/group-goals/create", methods=["GET", "POST"])
    @login_required
    def create_group_goal():
        """
        Admin-only page for creating a group goal.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = GroupGoalForm()

        if form.validate_on_submit():
            goal = GroupGoal(
                title=form.title.data,
                description=form.description.data,
                target_points=form.target_points.data,
                status="active",
                is_active=True
            )

            db.session.add(goal)
            db.session.commit()

            flash("Group goal created.")
            return redirect(url_for("main.group_goals"))

        return render_template(
            "create_group_goal.html",
            form=form
        )

    @bp.route("/group-goals/<int:goal_id>/contribute", methods=["GET", "POST"])
    @login_required
    def contribute_group_goal(goal_id):
        """
        Allow a standard user to contribute points to a group goal.
        """

        if current_user.is_admin():
            flash("Admins do not contribute to group goals.")
            return redirect(url_for("main.group_goals"))

        settings = get_household_settings()

        if not settings.group_goals_enabled:
            flash("Group goal contributions are currently disabled.")
            return redirect(url_for("main.group_goals"))

        goal = db.session.get(GroupGoal, goal_id)

        if not goal or not goal.is_active or goal.status != "active":
            flash("Group goal not found.")
            return redirect(url_for("main.group_goals"))

        form = GroupGoalContributionForm()

        if form.validate_on_submit():
            amount = form.amount.data

            if amount > current_user.point_balance():
                flash(f"You do not have enough {get_points_label()} to contribute that amount.")
                return redirect(url_for("main.contribute_group_goal", goal_id=goal.id))

            if amount > goal.remaining_points():
                flash(f"This goal only needs {format_points(goal.remaining_points())} more.")
                return redirect(url_for("main.contribute_group_goal", goal_id=goal.id))

            contribution = GroupGoalContribution(
                goal_id=goal.id,
                user_id=current_user.id,
                amount=amount,
                status="active"
            )

            db.session.add(contribution)
            db.session.flush()

            transaction = PointTransaction(
                user_id=current_user.id,
                amount=-amount,
                transaction_type="group_goal_contribution",
                reason=f"Contributed to group goal: {goal.title}",
                created_by_id=current_user.id
            )

            db.session.add(transaction)

            if goal.is_funded():
                goal.status = "completed"

                notify_admins(
                    title="Group goal funded",
                    message=f"The group goal '{goal.title}' has reached its {get_points_label()} target and is ready for fulfilment.",
                    notification_type="success",
                    action_url=url_for("main.group_goals"),
                    action_label="Open Group Goals"
                )

            check_and_award_badges(current_user)
            db.session.commit()

            flash("Contribution added.")
            return redirect(url_for("main.group_goals"))

        return render_template(
            "contribute_group_goal.html",
            form=form,
            goal=goal
        )

    @bp.route("/group-goals/<int:goal_id>/fulfil", methods=["POST"])
    @login_required
    def fulfil_group_goal(goal_id):
        """
        Admin-only route for marking a completed group goal as fulfilled.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        goal = db.session.get(GroupGoal, goal_id)

        if not goal or not goal.is_active:
            flash("Group goal not found.")
            return redirect(url_for("main.group_goals"))

        if not goal.is_funded():
            flash("This group goal has not reached its target yet.")
            return redirect(url_for("main.group_goals"))

        goal.status = "fulfilled"

        contributing_user_ids = set()

        for contribution in goal.contributions:
            if contribution.status == "active":
                contributing_user_ids.add(contribution.user_id)

        for user_id in contributing_user_ids:
            create_notification(
                user_id=user_id,
                title="Group goal fulfilled",
                message=f"The group goal '{goal.title}' has been fulfilled.",
                notification_type="success"
            )

        db.session.commit()

        flash("Group goal marked as fulfilled.")
        return redirect(url_for("main.group_goals"))

    @bp.route("/group-goals/<int:goal_id>/cancel", methods=["POST"])
    @login_required
    def cancel_group_goal(goal_id):
        """
        Admin-only route for cancelling a group goal.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        goal = db.session.get(GroupGoal, goal_id)

        if not goal or not goal.is_active:
            flash("Group goal not found.")
            return redirect(url_for("main.group_goals"))

        if goal.status == "fulfilled":
            flash("Fulfilled goals cannot be cancelled.")
            return redirect(url_for("main.group_goals"))

        for contribution in goal.contributions:
            if contribution.status == "active":
                refund = PointTransaction(
                    user_id=contribution.user_id,
                    amount=contribution.amount,
                    transaction_type="group_goal_refund",
                    reason=f"Refunded cancelled group goal: {goal.title}",
                    created_by_id=current_user.id
                )

                db.session.add(refund)

                contribution.status = "refunded"

                create_notification(
                    user_id=contribution.user_id,
                    title="Group goal cancelled",
                    message=f"The group goal '{goal.title}' was cancelled. Your contribution was refunded.",
                    notification_type="warning"
                )

        goal.status = "cancelled"
        goal.is_active = False

        db.session.commit()

        flash("Group goal cancelled and contributions refunded.")
        return redirect(url_for("main.group_goals"))
