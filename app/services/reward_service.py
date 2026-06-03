"""
Reward service.

This file contains reward workflow helpers used by routes.
Routes should handle request/response flow, while this service handles
reward reservation, approval, rejection, cancellation, and refund logic.
"""

from datetime import datetime, timezone

from flask_login import current_user

from app import db
from app.models import PointTransaction

from app.services.notification_service import create_notification
from app.services.points_service import format_points

def create_reward_reservation(purchase):
    """
    Reserve points for a pending reward request.

    This creates a negative point transaction linked to the purchase.

    This function does not commit.
    The calling route should commit after calling it.
    """

    transaction = PointTransaction(
        user_id=purchase.user_id,
        amount=-purchase.reward.point_cost,
        transaction_type="reward_requested",
        reason=f"Requested reward: {purchase.reward.name}",
        related_reward_purchase_id=purchase.id,
        created_by_id=current_user.id
    )

    db.session.add(transaction)

    return transaction


def approve_reward_purchase_request(purchase):
    """
    Approve a requested reward purchase.

    Current behaviour:
    - If points were already reserved at request time, no extra deduction happens.
    - If no reservation exists, a legacy fallback deduction is created.

    This function does not commit.
    The calling route should commit after calling it.
    """

    reservation = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type="reward_requested"
    ).first()

    if not reservation:
        if purchase.user.point_balance() < purchase.reward.point_cost:
            return False

        fallback_transaction = PointTransaction(
            user_id=purchase.user_id,
            amount=-purchase.reward.point_cost,
            transaction_type="reward_approved",
            reason=f"Approved reward: {purchase.reward.name}",
            related_reward_purchase_id=purchase.id,
            created_by_id=current_user.id
        )

        db.session.add(fallback_transaction)

    purchase.status = "approved"
    purchase.reviewed_at = datetime.now(timezone.utc)
    purchase.reviewed_by_id = current_user.id

    create_notification(
        user_id=purchase.user_id,
        title="Reward approved",
        message=f"Your reward request '{purchase.reward.name}' was approved.",
        notification_type="success"
    )

    return True


def reject_reward_purchase_request(purchase, rejection_reason):
    """
    Reject a reward purchase request and refund reserved points if required.

    This function does not commit.
    The calling route should commit after calling it.
    """

    refund_reserved_reward_points(
        purchase=purchase,
        transaction_type="reward_refunded",
        reason=f"Refunded rejected reward: {purchase.reward.name}"
    )

    purchase.status = "rejected"
    purchase.reviewed_at = datetime.now(timezone.utc)
    purchase.reviewed_by_id = current_user.id
    purchase.rejection_reason = rejection_reason

    create_notification(
        user_id=purchase.user_id,
        title="Reward rejected",
        message=(
            f"Your reward request '{purchase.reward.name}' was rejected. "
            f"Reason: {purchase.rejection_reason}. "
            f"Reserved {format_points(purchase.reward.point_cost)} were refunded."
        ),
        notification_type="danger"
    )


def cancel_reward_purchase_request(purchase):
    """
    Cancel a pending reward request and refund reserved points if required.

    This function does not commit.
    The calling route should commit after calling it.
    """

    refund_reserved_reward_points(
        purchase=purchase,
        transaction_type="reward_cancelled_refund",
        reason=f"Refunded cancelled reward request: {purchase.reward.name}"
    )

    purchase.status = "cancelled"
    purchase.reviewed_at = datetime.now(timezone.utc)
    purchase.rejection_reason = "Cancelled by user."


def refund_reserved_reward_points(purchase, transaction_type, reason):
    """
    Refund reserved reward points if they were reserved and not already refunded.

    This prevents double refunds.
    """

    reservation = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type="reward_requested"
    ).first()

    existing_refund = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type=transaction_type
    ).first()

    if reservation and not existing_refund:
        refund = PointTransaction(
            user_id=purchase.user_id,
            amount=purchase.reward.point_cost,
            transaction_type=transaction_type,
            reason=reason,
            related_reward_purchase_id=purchase.id,
            created_by_id=current_user.id
        )

        db.session.add(refund)

        return refund

    return None