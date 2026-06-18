"""
Dashboard routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.dashboard stay unchanged.
"""

from flask import render_template
from flask_login import current_user, login_required

from app.models import (
    Notification,
    PointTransaction,
    Reward,
    RewardPurchase,
    Task,
    TaskCompletion,
    User,
    WishlistItem,
)


def register_dashboard_routes(bp):
    """
    Register dashboard routes.
    """

    @bp.route("/dashboard")
    @login_required
    def dashboard():
        """
        Dashboard route.

        Admin users see household-level queues and activity. Standard users see
        their own pending work, balance, wishlist, reward, and activity data.
        """

        if current_user.is_admin():
            pending_tasks = TaskCompletion.query.filter_by(
                status="submitted"
            ).all()

            pending_purchases = RewardPurchase.query.filter_by(
                status="requested"
            ).all()

            active_user_count = User.query.filter_by(
                role="user",
                is_active_account=True
            ).count()

            notifications = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).order_by(
                Notification.created_at.desc()
            ).all()

            recent_activity = PointTransaction.query.order_by(
                PointTransaction.created_at.desc()
            ).limit(8).all()

            return render_template(
                "dashboard.html",
                pending_tasks=pending_tasks,
                pending_purchases=pending_purchases,
                active_user_count=active_user_count,
                notifications=notifications,
                recent_activity=recent_activity
            )

        pending_user_tasks = TaskCompletion.query.filter_by(
            user_id=current_user.id,
            status="submitted"
        ).all()

        pending_user_purchases = RewardPurchase.query.filter_by(
            user_id=current_user.id,
            status="requested"
        ).all()

        available_task_count = Task.query.filter_by(
            is_active=True
        ).count()

        current_balance = current_user.point_balance()

        wishlist_item_count = WishlistItem.query.filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.status.in_(["active", "funded"]),
            WishlistItem.is_active == True
        ).count()

        funded_wishlist_count = WishlistItem.query.filter_by(
            user_id=current_user.id,
            status="funded"
        ).count()

        active_wishlist_items = WishlistItem.query.filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.status.in_(["active", "funded"]),
            WishlistItem.is_active == True
        ).all()

        wishlist_points_saved = 0

        for item in active_wishlist_items:
            wishlist_points_saved += item.total_saved()

        affordable_reward_count = Reward.query.filter(
            Reward.is_active == True,
            Reward.point_cost <= current_balance
        ).count()

        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(
            Notification.created_at.desc()
        ).all()

        recent_activity = PointTransaction.query.filter_by(
            user_id=current_user.id
        ).order_by(
            PointTransaction.created_at.desc()
        ).limit(6).all()

        return render_template(
            "dashboard.html",
            pending_user_tasks=pending_user_tasks,
            pending_user_purchases=pending_user_purchases,
            available_task_count=available_task_count,
            affordable_reward_count=affordable_reward_count,
            current_balance=current_balance,
            notifications=notifications,
            wishlist_item_count=wishlist_item_count,
            funded_wishlist_count=funded_wishlist_count,
            wishlist_points_saved=wishlist_points_saved,
            recent_activity=recent_activity
        )
