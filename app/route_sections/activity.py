"""
Activity, history, and notification routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.point_history and main.task_history stay unchanged.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    Notification,
    PointTransaction,
    RewardPurchase,
    TaskCompletion,
)


def register_activity_routes(bp):
    """
    Register point history, task history, reward history, and notification
    routes.
    """

    @bp.route("/points")
    @login_required
    def point_history():
        """
        Point history page.

        Admins see all point transactions.
        Standard users only see their own transactions.
        """

        if current_user.is_admin():
            transactions = PointTransaction.query.order_by(
                PointTransaction.created_at.desc()
            ).all()
        else:
            transactions = PointTransaction.query.filter_by(
                user_id=current_user.id
            ).order_by(
                PointTransaction.created_at.desc()
            ).all()

        return render_template(
            "point_history.html",
            transactions=transactions
        )

    @bp.route("/history/tasks")
    @login_required
    def task_history():
        """
        Task history page.

        Admin users see all task completion records. Standard users see only
        their own task completion records.
        """

        if current_user.is_admin():
            completions = TaskCompletion.query.order_by(
                TaskCompletion.submitted_at.desc()
            ).all()
        else:
            completions = TaskCompletion.query.filter_by(
                user_id=current_user.id
            ).order_by(
                TaskCompletion.submitted_at.desc()
            ).all()

        return render_template(
            "task_history.html",
            completions=completions
        )

    @bp.route("/history/rewards")
    @login_required
    def reward_history():
        """
        Reward history page.

        Admin users see all reward purchase records. Standard users see only
        their own reward purchase records.
        """

        if current_user.is_admin():
            purchases = RewardPurchase.query.order_by(
                RewardPurchase.requested_at.desc()
            ).all()
        else:
            purchases = RewardPurchase.query.filter_by(
                user_id=current_user.id
            ).order_by(
                RewardPurchase.requested_at.desc()
            ).all()

        return render_template(
            "reward_history.html",
            purchases=purchases
        )

    @bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
    @login_required
    def mark_notification_read(notification_id):
        """
        Mark a dashboard notification as read/dismissed.

        Users can only dismiss their own notifications.
        """

        notification = db.session.get(Notification, notification_id)

        if not notification:
            flash("Notification not found.")
            return redirect(url_for("main.dashboard"))

        if notification.user_id != current_user.id:
            flash("You can only dismiss your own notifications.")
            return redirect(url_for("main.dashboard"))

        notification.is_read = True
        db.session.commit()

        flash("Notification dismissed.")
        return redirect(url_for("main.dashboard"))
