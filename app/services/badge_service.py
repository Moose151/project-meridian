"""
Badge service.

This file contains helper functions for creating default badges,
awarding badges, and checking whether users qualify for badges.
"""

from flask import url_for

from datetime import date
import calendar

from app import db
from app.models import (
    Badge,
    UserBadge,
    TaskCompletion,
    WishlistContribution,
    WishlistItem,
    GroupGoalContribution,
    Routine,
    RoutineCompletion,
    HouseholdSettings,
)

from app.services.notification_service import create_notification
from app.services.points_service import calculate_total_earned


def seed_badges():
    """
    Create default badges if they do not already exist.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    default_badges = [
        {
            "code": "first_task",
            "name": "First Task",
            "description": "Completed your first approved task.",
            "icon": "✅"
        },
        {
            "code": "five_tasks",
            "name": "Task Starter",
            "description": "Completed 5 approved tasks.",
            "icon": "⭐"
        },
        {
            "code": "ten_tasks",
            "name": "Task Champion",
            "description": "Completed 10 approved tasks.",
            "icon": "🏆"
        },
        {
            "code": "wishlist_saver",
            "name": "Wishlist Saver",
            "description": "Saved toward a wishlist item.",
            "icon": "🎁"
        },
        {
            "code": "wishlist_funded",
            "name": "Goal Reached",
            "description": "Fully funded a wishlist item.",
            "icon": "🎯"
        },
        {
            "code": "group_contributor",
            "name": "Team Player",
            "description": "Contributed to a group goal.",
            "icon": "🤝"
        },
        {
            "code": "hundred_points_earned",
            "name": "Big Earner",
            "description": "Reached an earning milestone.",
            "icon": "💰"
        },
        {
            "code": "routine_streak_3",
            "name": "Getting Started",
            "description": "Completed a routine 3 days in a row (or 3 total with auto-end off).",
            "icon": "🔥"
        },
        {
            "code": "routine_streak_7",
            "name": "Week Warrior",
            "description": "Completed a routine 7 days in a row (or 7 total with auto-end off).",
            "icon": "⚡"
        },
        {
            "code": "routine_streak_28",
            "name": "Dedicated",
            "description": "Completed a routine 28 days in a row (or 28 total with auto-end off).",
            "icon": "💪"
        },
        {
            "code": "routine_streak_30",
            "name": "Monthly Champion",
            "description": "Completed a routine 30 days in a row (or 30 total with auto-end off).",
            "icon": "🏅"
        },
        {
            "code": "routine_perfect_month",
            "name": "Perfect Month",
            "description": "Completed at least one routine every single day of a calendar month.",
            "icon": "📅"
        },
        {
            "code": "routine_10",
            "name": "Habit Forming",
            "description": "Completed routines 10 times total.",
            "icon": "🌱"
        },
        {
            "code": "routine_50",
            "name": "Routine Pro",
            "description": "Completed routines 50 times total.",
            "icon": "🌟"
        },
        {
            "code": "routine_100",
            "name": "Routine Master",
            "description": "Completed routines 100 times total.",
            "icon": "👑"
        },
    ]

    for badge_data in default_badges:
        existing_badge = Badge.query.filter_by(
            code=badge_data["code"]
        ).first()

        if not existing_badge:
            badge = Badge(
                code=badge_data["code"],
                name=badge_data["name"],
                description=badge_data["description"],
                icon=badge_data["icon"]
            )

            db.session.add(badge)


def award_badge(user_id, badge_code):
    """
    Award a badge to a user if they do not already have it.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    badge = Badge.query.filter_by(
        code=badge_code
    ).first()

    if not badge:
        return

    existing_user_badge = UserBadge.query.filter_by(
        user_id=user_id,
        badge_id=badge.id
    ).first()

    if existing_user_badge:
        return

    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge.id
    )

    db.session.add(user_badge)

    create_notification(
        user_id=user_id,
        title="Badge earned",
        message=f"You earned the '{badge.name}' badge.",
        notification_type="success",
        action_url=url_for("main.my_profile"),
        action_label="View Profile"
    )


def check_and_award_badges(user):
    """
    Check badge rules for a user and award any badges they have earned.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    seed_badges()

    approved_task_count = TaskCompletion.query.filter_by(
        user_id=user.id,
        status="approved"
    ).count()

    if approved_task_count >= 1:
        award_badge(user.id, "first_task")

    if approved_task_count >= 5:
        award_badge(user.id, "five_tasks")

    if approved_task_count >= 10:
        award_badge(user.id, "ten_tasks")

    wishlist_contribution_count = WishlistContribution.query.filter_by(
        user_id=user.id,
        status="active"
    ).count()

    if wishlist_contribution_count >= 1:
        award_badge(user.id, "wishlist_saver")

    funded_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="funded"
    ).count()

    fulfilled_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="fulfilled"
    ).count()

    if funded_wishlist_count + fulfilled_wishlist_count >= 1:
        award_badge(user.id, "wishlist_funded")

    group_contribution_count = GroupGoalContribution.query.filter_by(
        user_id=user.id,
        status="active"
    ).count()

    if group_contribution_count >= 1:
        award_badge(user.id, "group_contributor")

    total_earned = calculate_total_earned(user)

    if total_earned >= 100:
        award_badge(user.id, "hundred_points_earned")

    # ── Routine badges ───────────────────────────────────────────────
    settings = HouseholdSettings.query.first()
    auto_end = settings.auto_end_streaks if settings else True

    all_routines = Routine.query.filter_by(is_active=True).all()

    max_streak = 0
    for routine in all_routines:
        streak = routine.current_streak_for_user(user.id, auto_end=auto_end)
        if streak > max_streak:
            max_streak = streak

    if max_streak >= 3:
        award_badge(user.id, "routine_streak_3")
    if max_streak >= 7:
        award_badge(user.id, "routine_streak_7")
    if max_streak >= 28:
        award_badge(user.id, "routine_streak_28")
    if max_streak >= 30:
        award_badge(user.id, "routine_streak_30")

    # Total non-voided routine completions
    total_routine_completions = RoutineCompletion.query.filter_by(
        user_id=user.id,
        voided=False
    ).count()

    if total_routine_completions >= 10:
        award_badge(user.id, "routine_10")
    if total_routine_completions >= 50:
        award_badge(user.id, "routine_50")
    if total_routine_completions >= 100:
        award_badge(user.id, "routine_100")

    # Perfect month: at least one completion every day of any calendar month
    all_completion_dates = {
        c.completed_date
        for c in RoutineCompletion.query.filter_by(user_id=user.id, voided=False).all()
    }

    if all_completion_dates:
        months_seen = {(d.year, d.month) for d in all_completion_dates}
        for year, month in months_seen:
            days_in_month = calendar.monthrange(year, month)[1]
            days_completed = sum(
                1 for d in all_completion_dates
                if d.year == year and d.month == month
            )
            if days_completed >= days_in_month:
                award_badge(user.id, "routine_perfect_month")
                break