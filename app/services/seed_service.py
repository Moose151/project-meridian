"""
Seed service.

Creates safe default data for a fresh Project Meridian install.
"""

from sqlalchemy import inspect, text

from app import db
from app.models import User, HouseholdSettings


def run_column_migrations():
    """
    Add missing columns to existing tables.

    db.create_all() creates missing tables but does not add new columns
    to existing tables. This function fills that gap idempotently so
    that production databases that predate a column addition are updated
    automatically on startup.
    """

    inspector = inspect(db.engine)

    # ── tasks table ─────────────────────────────────────────────────
    existing_task_cols = {col["name"] for col in inspector.get_columns("tasks")}

    task_migrations = [
        (
            "assigned_user_id",
            "ALTER TABLE tasks ADD COLUMN assigned_user_id INTEGER REFERENCES users(id)"
        ),
        (
            "assigned_visibility",
            "ALTER TABLE tasks ADD COLUMN assigned_visibility VARCHAR(30) NOT NULL DEFAULT 'all'"
        ),
        (
            "availability_window",
            "ALTER TABLE tasks ADD COLUMN availability_window VARCHAR(30) NOT NULL DEFAULT 'always'"
        ),
        (
            "completion_scope",
            "ALTER TABLE tasks ADD COLUMN completion_scope VARCHAR(30) NOT NULL DEFAULT 'per_user'"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in task_migrations:
            if col_name not in existing_task_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── users table ──────────────────────────────────────────────────
    existing_user_cols = {col["name"] for col in inspector.get_columns("users")}

    with db.engine.connect() as conn:
        if "participation_enabled" not in existing_user_cols:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN participation_enabled BOOLEAN NOT NULL DEFAULT 0"
            ))
        conn.commit()


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
