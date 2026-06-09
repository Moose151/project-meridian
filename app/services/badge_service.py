"""
Badge service.

This file contains helper functions for creating default badges,
awarding badges, and checking whether users qualify for badges.
"""

from flask import url_for

from app import db
from app.models import (
    Badge,
    UserBadge,
    TaskCompletion,
    WishlistContribution,
    WishlistItem,
    GroupGoalContribution,
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