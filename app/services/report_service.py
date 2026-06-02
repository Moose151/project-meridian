"""
Report service.

This file contains helper functions for building CSV report rows.
Routes should only call these helpers and return the CSV response.
"""

from app.models import (
    User,
    TaskCompletion,
    RewardPurchase,
    PointTransaction,
    WishlistItem,
)

from app.services.points_service import calculate_total_earned


def build_users_report_rows():
    """
    Build user summary report rows.
    """

    rows = [
        [
            "User ID",
            "Username",
            "Display Name",
            "Role",
            "Active",
            "Current Balance",
            "Total Earned",
            "Approved Tasks",
            "Reward Requests",
            "Wishlist Saved"
        ]
    ]

    users = User.query.order_by(
        User.display_name
    ).all()

    for user in users:
        approved_tasks = TaskCompletion.query.filter_by(
            user_id=user.id,
            status="approved"
        ).count()

        reward_requests = RewardPurchase.query.filter_by(
            user_id=user.id
        ).count()

        active_wishlist_items = WishlistItem.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()

        wishlist_saved = 0

        for item in active_wishlist_items:
            wishlist_saved += item.total_saved()

        rows.append(
            [
                user.id,
                user.username,
                user.display_name,
                user.role,
                user.is_active_account,
                user.point_balance(),
                calculate_total_earned(user),
                approved_tasks,
                reward_requests,
                wishlist_saved
            ]
        )

    return rows


def build_points_report_rows():
    """
    Build full point transaction report rows.
    """

    rows = [
        [
            "Transaction ID",
            "Date",
            "User",
            "Username",
            "Amount",
            "Transaction Type",
            "Reason",
            "Created By"
        ]
    ]

    transactions = PointTransaction.query.order_by(
        PointTransaction.created_at.desc()
    ).all()

    for transaction in transactions:
        user_name = ""
        username = ""
        created_by_name = ""

        if transaction.user:
            user_name = transaction.user.display_name
            username = transaction.user.username

        if transaction.created_by:
            created_by_name = transaction.created_by.display_name

        rows.append(
            [
                transaction.id,
                transaction.created_at,
                user_name,
                username,
                transaction.amount,
                transaction.transaction_type,
                transaction.reason,
                created_by_name
            ]
        )

    return rows


def build_tasks_report_rows():
    """
    Build task completion activity report rows.
    """

    rows = [
        [
            "Completion ID",
            "User",
            "Username",
            "Task",
            "Category",
            "Status",
            "Task Value",
            "Submitted At",
            "Reviewed At",
            "Reviewed By",
            "Rejection Reason"
        ]
    ]

    completions = TaskCompletion.query.order_by(
        TaskCompletion.submitted_at.desc()
    ).all()

    for completion in completions:
        user_name = ""
        username = ""
        task_title = ""
        task_category = ""
        task_value = ""
        reviewed_by_name = ""

        if completion.user:
            user_name = completion.user.display_name
            username = completion.user.username

        if completion.task:
            task_title = completion.task.title
            task_category = completion.task.category or ""
            task_value = completion.task.point_value

        if completion.reviewed_by:
            reviewed_by_name = completion.reviewed_by.display_name

        rows.append(
            [
                completion.id,
                user_name,
                username,
                task_title,
                task_category,
                completion.status,
                task_value,
                completion.submitted_at,
                completion.reviewed_at,
                reviewed_by_name,
                completion.rejection_reason or ""
            ]
        )

    return rows


def build_rewards_report_rows():
    """
    Build reward request activity report rows.
    """

    rows = [
        [
            "Purchase ID",
            "User",
            "Username",
            "Reward",
            "Category",
            "Status",
            "Cost",
            "Requested At",
            "Reviewed At",
            "Reviewed By",
            "Rejection Reason"
        ]
    ]

    purchases = RewardPurchase.query.order_by(
        RewardPurchase.requested_at.desc()
    ).all()

    for purchase in purchases:
        user_name = ""
        username = ""
        reward_name = ""
        reward_category = ""
        reward_cost = ""
        reviewed_by_name = ""

        if purchase.user:
            user_name = purchase.user.display_name
            username = purchase.user.username

        if purchase.reward:
            reward_name = purchase.reward.name
            reward_category = purchase.reward.category or ""
            reward_cost = purchase.reward.point_cost

        if purchase.reviewed_by:
            reviewed_by_name = purchase.reviewed_by.display_name

        rows.append(
            [
                purchase.id,
                user_name,
                username,
                reward_name,
                reward_category,
                purchase.status,
                reward_cost,
                purchase.requested_at,
                purchase.reviewed_at,
                reviewed_by_name,
                purchase.rejection_reason or ""
            ]
        )

    return rows