"""
Household settings service.

This file contains helper functions for reading and creating
household-level settings used across the app.
"""

from datetime import datetime, timezone

from app import db
from app.models import HouseholdSettings


def get_household_settings():
    """
    Return the household settings row.

    If it does not exist, create it with defaults.
    """

    settings = HouseholdSettings.query.first()

    if not settings:
        settings = HouseholdSettings(
            household_name="Project Meridian",
            points_label="points",
            wishlist_requests_enabled=True,
            group_goals_enabled=True,
            updated_at=datetime.now(timezone.utc)
        )

        db.session.add(settings)
        db.session.commit()

    return settings


def get_points_label():
    """
    Return the current household points label.
    """

    settings = get_household_settings()

    return settings.points_label