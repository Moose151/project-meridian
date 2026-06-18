"""
Admin approval routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.admin_approvals stay unchanged.
"""

from datetime import datetime, timezone

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import RejectionReasonForm
from app.models import RewardPurchase, TaskCompletion
from app.services.notification_service import create_notification
from app.services.points_service import format_points
from app.services.reward_service import (
    approve_reward_purchase_request,
    reject_reward_purchase_request,
)
from app.services.settings_service import get_points_label
from app.services.task_service import approve_submitted_task_completion


def register_approval_routes(bp, admin_required):
    """
    Register admin task and reward approval routes.
    """

    @bp.route("/admin/approvals")
    @login_required
    def admin_approvals():
        """
        Admin approval queue.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        pending_tasks = TaskCompletion.query.filter_by(
            status="submitted"
        ).all()

        pending_purchases = RewardPurchase.query.filter_by(
            status="requested"
        ).all()

        return render_template(
            "admin_approvals.html",
            pending_tasks=pending_tasks,
            pending_purchases=pending_purchases
        )

    @bp.route("/admin/tasks/<int:completion_id>/approve", methods=["POST"])
    @login_required
    def approve_task_completion(completion_id):
        """
        Approve a submitted task completion.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        completion = db.session.get(TaskCompletion, completion_id)

        if not completion or completion.status != "submitted":
            flash("Task completion request not found.")
            return redirect(url_for("main.admin_approvals"))

        awarded_points = approve_submitted_task_completion(completion)

        db.session.commit()

        flash(f"Task approved and {format_points(awarded_points)} awarded.")
        return redirect(url_for("main.admin_approvals"))

    @bp.route("/admin/tasks/<int:completion_id>/reject", methods=["GET", "POST"])
    @login_required
    def reject_task_completion(completion_id):
        """
        Reject a submitted task completion.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        completion = db.session.get(TaskCompletion, completion_id)

        if not completion or completion.status != "submitted":
            flash("Task completion request not found.")
            return redirect(url_for("main.admin_approvals"))

        form = RejectionReasonForm()

        if form.validate_on_submit():
            completion.status = "rejected"
            completion.reviewed_at = datetime.now(timezone.utc)
            completion.reviewed_by_id = current_user.id
            completion.rejection_reason = form.reason.data.strip()

            create_notification(
                user_id=completion.user_id,
                title="Task rejected",
                message=f"Your task '{completion.task.title}' was rejected. Reason: {completion.rejection_reason}",
                notification_type="danger"
            )

            db.session.commit()

            flash("Task completion rejected.")
            return redirect(url_for("main.admin_approvals"))

        return render_template(
            "reject_task_completion.html",
            form=form,
            completion=completion
        )

    @bp.route("/admin/rewards/<int:purchase_id>/approve", methods=["POST"])
    @login_required
    def approve_reward_purchase(purchase_id):
        """
        Approve a requested reward purchase.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        purchase = db.session.get(RewardPurchase, purchase_id)

        if not purchase or purchase.status != "requested":
            flash("Reward purchase request not found.")
            return redirect(url_for("main.admin_approvals"))

        approved = approve_reward_purchase_request(purchase)

        if not approved:
            flash(f"User no longer has enough {get_points_label()} for this reward.")
            return redirect(url_for("main.admin_approvals"))

        db.session.commit()

        flash("Reward approved.")
        return redirect(url_for("main.admin_approvals"))

    @bp.route("/admin/rewards/<int:purchase_id>/reject", methods=["GET", "POST"])
    @login_required
    def reject_reward_purchase(purchase_id):
        """
        Reject a requested reward purchase.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        purchase = db.session.get(RewardPurchase, purchase_id)

        if not purchase or purchase.status != "requested":
            flash("Reward purchase request not found.")
            return redirect(url_for("main.admin_approvals"))

        form = RejectionReasonForm()

        if form.validate_on_submit():
            reject_reward_purchase_request(
                purchase=purchase,
                rejection_reason=form.reason.data.strip()
            )

            db.session.commit()

            flash(f"Reward request rejected and reserved {get_points_label()} refunded.")
            return redirect(url_for("main.admin_approvals"))

        return render_template(
            "reject_reward_purchase.html",
            form=form,
            purchase=purchase
        )
