"""
Task service.

This file contains task workflow helpers used by routes.
Routes should handle request/response flow, while this service handles
task approval and task completion business logic.
"""

from datetime import datetime, timezone

from flask_login import current_user

from app import db
from app.models import TaskCompletion, PointTransaction

from app.services.badge_service import check_and_award_badges
from app.services.notification_service import create_notification
from app.services.points_service import format_points


def approve_submitted_task_completion(completion, review_note=None):
    """
    Approve a submitted task completion.

    This:
    - marks the completion as approved
    - stores an optional admin review note
    - creates a positive point transaction
    - hides one-off tasks after approval
    - notifies the user (includes the note if provided)
    - checks badge eligibility

    This function does not commit.
    The calling route should commit after calling it.
    """

    completion.status = "approved"
    completion.reviewed_at = datetime.now(timezone.utc)
    completion.reviewed_by_id = current_user.id

    if review_note:
        completion.review_note = review_note.strip() or None

    awarded_points = completion.task.total_point_value()

    transaction = PointTransaction(
        user_id=completion.user_id,
        amount=awarded_points,
        transaction_type="task_approved",
        reason=f"Approved task: {completion.task.title}",
        related_task_completion_id=completion.id,
        created_by_id=current_user.id
    )

    db.session.add(transaction)

    if completion.task.completion_behavior == "hide_after_approval":
        completion.task.is_active = False

    note_suffix = f" Note from admin: {review_note.strip()}" if review_note and review_note.strip() else ""
    create_notification(
        user_id=completion.user_id,
        title="Task approved",
        message=f"Your task '{completion.task.title}' was approved. You earned {format_points(awarded_points)}.{note_suffix}",
        notification_type="success"
    )

    check_and_award_badges(completion.user)

    return awarded_points


def admin_complete_task_for_user(user, task):
    """
    Allow an admin to directly complete a task for a user.

    This bypasses the normal submit-then-approve workflow.

    This function:
    - creates an approved TaskCompletion
    - creates a positive point transaction
    - hides one-off tasks after completion
    - notifies the user
    - checks badge eligibility

    This function flushes so the completion gets an ID.
    It does not commit.
    The calling route should commit after calling it.
    """

    completion = TaskCompletion(
        task_id=task.id,
        user_id=user.id,
        status="approved",
        reviewed_at=datetime.now(timezone.utc),
        reviewed_by_id=current_user.id
    )

    db.session.add(completion)
    db.session.flush()

    awarded_points = task.total_point_value()

    transaction = PointTransaction(
        user_id=user.id,
        amount=awarded_points,
        transaction_type="task_approved",
        reason=f"Admin completed task for user: {task.title}",
        related_task_completion_id=completion.id,
        created_by_id=current_user.id
    )

    db.session.add(transaction)

    if task.completion_behavior == "hide_after_approval":
        task.is_active = False

    create_notification(
        user_id=user.id,
        title="Task completed by admin",
        message=f"'{task.title}' was marked complete for you. You earned {format_points(awarded_points)}.",
        notification_type="success"
    )

    check_and_award_badges(user)

    return completion, awarded_points