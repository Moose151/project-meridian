"""
Unified request archive routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.request_archive stay unchanged.
"""

from flask import render_template
from flask_login import current_user, login_required

from app.models import RewardPurchase, TaskCompletion, WishlistRequest


def register_request_archive_routes(bp):
    """
    Register request archive routes.
    """

    @bp.route("/requests/archive")
    @login_required
    def request_archive():
        """
        Request archive page.

        Admin users see archived requests for all users. Standard users see
        their own archived requests.
        """

        archived_task_statuses = [
            "approved",
            "rejected",
            "cancelled"
        ]

        archived_reward_statuses = [
            "approved",
            "rejected",
            "cancelled",
            "fulfilled"
        ]

        archived_wishlist_statuses = [
            "approved",
            "rejected",
            "cancelled"
        ]

        if current_user.is_admin():
            archived_task_requests = TaskCompletion.query.filter(
                TaskCompletion.status.in_(archived_task_statuses)
            ).order_by(
                TaskCompletion.submitted_at.desc()
            ).limit(30).all()

            archived_reward_requests = RewardPurchase.query.filter(
                RewardPurchase.status.in_(archived_reward_statuses)
            ).order_by(
                RewardPurchase.requested_at.desc()
            ).limit(30).all()

            archived_wishlist_requests = WishlistRequest.query.filter(
                WishlistRequest.status.in_(archived_wishlist_statuses)
            ).order_by(
                WishlistRequest.created_at.desc()
            ).limit(30).all()
        else:
            archived_task_requests = TaskCompletion.query.filter(
                TaskCompletion.user_id == current_user.id,
                TaskCompletion.status.in_(archived_task_statuses)
            ).order_by(
                TaskCompletion.submitted_at.desc()
            ).limit(20).all()

            archived_reward_requests = RewardPurchase.query.filter(
                RewardPurchase.user_id == current_user.id,
                RewardPurchase.status.in_(archived_reward_statuses)
            ).order_by(
                RewardPurchase.requested_at.desc()
            ).limit(20).all()

            archived_wishlist_requests = WishlistRequest.query.filter(
                WishlistRequest.user_id == current_user.id,
                WishlistRequest.status.in_(archived_wishlist_statuses)
            ).order_by(
                WishlistRequest.created_at.desc()
            ).limit(20).all()

        return render_template(
            "request_archive.html",
            archived_task_requests=archived_task_requests,
            archived_reward_requests=archived_reward_requests,
            archived_wishlist_requests=archived_wishlist_requests
        )
