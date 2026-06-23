"""
Points service.

This file contains shared helper functions for calculating point totals
and formatting point-related text.
"""

from app.services.settings_service import get_points_label


def get_earning_transaction_types():
    """
    Return transaction types that count toward total earned.

    Spending, saving, refunds, and negative adjustments should not reduce
    this value.
    """

    return [
        "task_approved",
        "routine_completed",
        "manual_adjustment",
        "admin_adjustment",
        "point_adjustment",
        "allowance",
    ]


def calculate_total_earned(user):
    """
    Calculate total earned points for a user.

    This counts positive earning transactions only.
    It does not subtract spending, wishlist saving, group goal contributions,
    reward requests, refunds, or negative adjustments.
    """

    total = 0

    earning_transaction_types = get_earning_transaction_types()

    for transaction in user.point_transactions:
        if (
            transaction.transaction_type in earning_transaction_types
            and transaction.amount > 0
        ):
            total += transaction.amount

    return total


def format_points(amount):
    """
    Format an amount with the current household points label.

    Examples:
    - 10 points
    - 10 stars
    - 10 tokens
    """

    points_label = get_points_label()

    return f"{amount} {points_label}"
