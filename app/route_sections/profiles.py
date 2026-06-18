"""
User profile routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.my_profile and main.user_profile stay unchanged.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    GroupGoalContribution,
    PointTransaction,
    RewardPurchase,
    TaskCompletion,
    User,
    UserBadge,
    WishlistContribution,
    WishlistItem,
    WishlistRequest,
)
from app.services.badge_service import check_and_award_badges
from app.services.points_service import calculate_total_earned


def register_profile_routes(bp, admin_required=None):
    """
    Register profile routes.
    """

    @bp.route("/profile")
    @login_required
    def my_profile():
        """
        Redirect the current user to the full user profile page.
        """

        return redirect(
            url_for(
                "main.user_profile",
                user_id=current_user.id
            )
        )

    @bp.route("/users/<int:user_id>/profile")
    @login_required
    def user_profile(user_id):
        """
        User profile page.
        """

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.dashboard"))

        if not current_user.is_admin() and current_user.id != user.id:
            flash("You can only view your own profile.")
            return redirect(url_for("main.dashboard"))

        current_points = user.point_balance()
        total_earned = calculate_total_earned(user)

        tasks_completed = TaskCompletion.query.filter_by(
            user_id=user.id,
            status="approved"
        ).count()

        rewards_requested = RewardPurchase.query.filter_by(
            user_id=user.id
        ).count()

        rewards_approved = RewardPurchase.query.filter_by(
            user_id=user.id,
            status="approved"
        ).count()

        active_group_contributions = GroupGoalContribution.query.filter_by(
            user_id=user.id,
            status="active"
        ).all()

        total_group_contributed = 0

        for contribution in active_group_contributions:
            total_group_contributed += contribution.amount

        active_group_goal_count = len(active_group_contributions)

        active_wishlist_items = WishlistItem.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()

        wishlist_item_count = len(active_wishlist_items)

        funded_wishlist_count = WishlistItem.query.filter_by(
            user_id=user.id,
            status="funded"
        ).count()

        fulfilled_wishlist_count = WishlistItem.query.filter_by(
            user_id=user.id,
            status="fulfilled"
        ).count()

        wishlist_points_saved = 0

        for item in active_wishlist_items:
            wishlist_points_saved += item.total_saved()

        wishlist_request_count = WishlistRequest.query.filter_by(
            user_id=user.id
        ).count()

        recent_task_completions = TaskCompletion.query.filter_by(
            user_id=user.id
        ).order_by(
            TaskCompletion.submitted_at.desc()
        ).limit(5).all()

        recent_reward_purchases = RewardPurchase.query.filter_by(
            user_id=user.id
        ).order_by(
            RewardPurchase.requested_at.desc()
        ).limit(5).all()

        recent_point_transactions = PointTransaction.query.filter_by(
            user_id=user.id
        ).order_by(
            PointTransaction.created_at.desc()
        ).limit(5).all()

        recent_group_contributions = GroupGoalContribution.query.filter_by(
            user_id=user.id
        ).order_by(
            GroupGoalContribution.created_at.desc()
        ).limit(5).all()

        recent_wishlist_items = WishlistItem.query.filter_by(
            user_id=user.id
        ).order_by(
            WishlistItem.created_at.desc()
        ).limit(5).all()

        recent_wishlist_requests = WishlistRequest.query.filter_by(
            user_id=user.id
        ).order_by(
            WishlistRequest.created_at.desc()
        ).limit(5).all()

        recent_wishlist_contributions = WishlistContribution.query.filter_by(
            user_id=user.id
        ).order_by(
            WishlistContribution.created_at.desc()
        ).limit(5).all()

        check_and_award_badges(user)
        db.session.commit()

        earned_badges = UserBadge.query.filter_by(
            user_id=user.id
        ).order_by(
            UserBadge.earned_at.desc()
        ).all()

        return render_template(
            "user_profile.html",
            user=user,
            current_points=current_points,
            total_earned=total_earned,
            tasks_completed=tasks_completed,
            rewards_requested=rewards_requested,
            rewards_approved=rewards_approved,
            total_group_contributed=total_group_contributed,
            active_group_goal_count=active_group_goal_count,
            wishlist_item_count=wishlist_item_count,
            funded_wishlist_count=funded_wishlist_count,
            fulfilled_wishlist_count=fulfilled_wishlist_count,
            wishlist_points_saved=wishlist_points_saved,
            wishlist_request_count=wishlist_request_count,
            recent_task_completions=recent_task_completions,
            recent_reward_purchases=recent_reward_purchases,
            recent_point_transactions=recent_point_transactions,
            recent_group_contributions=recent_group_contributions,
            recent_wishlist_items=recent_wishlist_items,
            recent_wishlist_requests=recent_wishlist_requests,
            recent_wishlist_contributions=recent_wishlist_contributions,
            earned_badges=earned_badges,
        )

    @bp.route("/admin/participation/toggle", methods=["POST"])
    @login_required
    def toggle_participation():
        """
        Admin-only route to toggle the current admin's household participation mode.

        When enabled, the admin can submit tasks, earn points, request rewards,
        contribute to group goals and wishlist items, and appear on leaderboards.
        """

        if not current_user.is_admin():
            flash("Only admins have a participation mode to toggle.")
            return redirect(url_for("main.dashboard"))

        current_user.participation_enabled = not current_user.participation_enabled
        db.session.commit()

        if current_user.participation_enabled:
            flash("Participation mode enabled. You can now earn points and join leaderboards.")
        else:
            flash("Participation mode disabled. You are back to admin-only mode.")

        return redirect(url_for("main.admin_home"))
