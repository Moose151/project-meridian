"""
Notification service.

This file contains helper functions for creating user, admin,
and standard-user notifications.
"""

from app import db
from app.models import Notification, User


def create_notification(
    user_id,
    title,
    message,
    notification_type="info",
    action_url=None,
    action_label=None
):
    """
    Create a dashboard notification for a user.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_label=action_label,
        is_read=False
    )

    db.session.add(notification)


def notify_admins(
    title,
    message,
    notification_type="info",
    action_url=None,
    action_label=None
):
    """
    Create a dashboard notification for every active admin user.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    admins = User.query.filter_by(
        role="admin",
        is_active_account=True
    ).all()

    for admin in admins:
        create_notification(
            user_id=admin.id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_label=action_label
        )


def notify_standard_users(
    title,
    message,
    notification_type="info",
    action_url=None,
    action_label=None
):
    """
    Create a dashboard notification for every active standard user.

    This function does not commit.
    The calling route or service should commit after calling it.
    """

    users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).all()

    for user in users:
        create_notification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_label=action_label
        )