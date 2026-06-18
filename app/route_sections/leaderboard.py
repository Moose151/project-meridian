"""
Leaderboard routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.leaderboard stay unchanged.
"""

from flask import render_template
from flask_login import login_required

from app.models import TaskCompletion, User
from app.services.points_service import calculate_total_earned


def register_leaderboard_routes(bp):
    """
    Register leaderboard routes.
    """

    @bp.route("/leaderboard")
    @login_required
    def leaderboard():
        """
        Leaderboard page.
        """

        users = User.query.filter_by(
            role="user",
            is_active_account=True
        ).order_by(
            User.display_name
        ).all()

        current_points_leaderboard = []

        for user in users:
            current_points_leaderboard.append({
                "user": user,
                "score": user.point_balance()
            })

        current_points_leaderboard = sorted(
            current_points_leaderboard,
            key=lambda item: item["score"],
            reverse=True
        )

        total_earned_leaderboard = []

        for user in users:
            total_earned = calculate_total_earned(user)

            total_earned_leaderboard.append({
                "user": user,
                "score": total_earned
            })

        total_earned_leaderboard = sorted(
            total_earned_leaderboard,
            key=lambda item: item["score"],
            reverse=True
        )

        tasks_completed_leaderboard = []

        for user in users:
            approved_task_count = TaskCompletion.query.filter_by(
                user_id=user.id,
                status="approved"
            ).count()

            tasks_completed_leaderboard.append({
                "user": user,
                "score": approved_task_count
            })

        tasks_completed_leaderboard = sorted(
            tasks_completed_leaderboard,
            key=lambda item: item["score"],
            reverse=True
        )

        return render_template(
            "leaderboard.html",
            current_points_leaderboard=current_points_leaderboard,
            total_earned_leaderboard=total_earned_leaderboard,
            tasks_completed_leaderboard=tasks_completed_leaderboard
        )
