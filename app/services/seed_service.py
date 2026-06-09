"""
Seed service.

Creates safe default data for a fresh Project Meridian install.
"""

from app import db
from app.models import User, HouseholdSettings


def seed_default_data():
    """
    Seed required default records.

    This function is idempotent:
    - it creates household settings only if missing
    - it creates the default admin only if there are no users at all
    """

    changed = False

    # Ensure household settings exists.
    settings = HouseholdSettings.query.first()

    if not settings:
        settings = HouseholdSettings(
            household_name="Project Meridian",
            points_label="points",
            wishlist_requests_enabled=True,
            group_goals_enabled=True,
        )
        db.session.add(settings)
        changed = True

    # Only create the default admin for a completely fresh install.
    existing_user_count = User.query.count()

    if existing_user_count == 0:
        default_admin = User(
            username="admin",
            display_name="Admin",
            avatar_emoji="🛡️",
            role="admin",
            is_active_account=True,
        )

        # Default first-login PIN/password.
        # Users should change this immediately after first login.
        default_admin.set_password("1234")

        db.session.add(default_admin)
        changed = True

    if changed:
        db.session.commit()
