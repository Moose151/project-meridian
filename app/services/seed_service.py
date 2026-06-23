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

    # ── tasks table (recurrence + archive) ──────────────────────────
    # Refresh after first batch so new cols appear.
    existing_task_cols = {col["name"] for col in inspector.get_columns("tasks")}

    task_migrations_2 = [
        (
            "recurrence_days",
            "ALTER TABLE tasks ADD COLUMN recurrence_days VARCHAR(20) NOT NULL DEFAULT ''"
        ),
        (
            "is_archived",
            "ALTER TABLE tasks ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in task_migrations_2:
            if col_name not in existing_task_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── task_completions table ───────────────────────────────────────
    existing_tc_cols = {col["name"] for col in inspector.get_columns("task_completions")}

    tc_migrations = [
        (
            "evidence_photo",
            "ALTER TABLE task_completions ADD COLUMN evidence_photo VARCHAR(255)"
        ),
        (
            "review_note",
            "ALTER TABLE task_completions ADD COLUMN review_note TEXT"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in tc_migrations:
            if col_name not in existing_tc_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── rewards table ───────────────────────────────────────────────
    existing_reward_cols = {col["name"] for col in inspector.get_columns("rewards")}

    reward_migrations = [
        (
            "is_archived",
            "ALTER TABLE rewards ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"
        ),
        (
            "quantity",
            "ALTER TABLE rewards ADD COLUMN quantity INTEGER"
        ),
        (
            "allow_multiple_in_cart",
            "ALTER TABLE rewards ADD COLUMN allow_multiple_in_cart BOOLEAN NOT NULL DEFAULT 0"
        ),
        (
            "disappear_when_empty",
            "ALTER TABLE rewards ADD COLUMN disappear_when_empty BOOLEAN NOT NULL DEFAULT 1"
        ),
        (
            "daily_limit_per_user",
            "ALTER TABLE rewards ADD COLUMN daily_limit_per_user INTEGER"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in reward_migrations:
            if col_name not in existing_reward_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── rewards table (extra info) ───────────────────────────────────
    existing_reward_cols = {col["name"] for col in inspector.get_columns("rewards")}

    reward_extra_migrations = [
        (
            "price_estimate",
            "ALTER TABLE rewards ADD COLUMN price_estimate VARCHAR(60)"
        ),
        (
            "store_url",
            "ALTER TABLE rewards ADD COLUMN store_url VARCHAR(500)"
        ),
        (
            "image_url",
            "ALTER TABLE rewards ADD COLUMN image_url VARCHAR(500)"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in reward_extra_migrations:
            if col_name not in existing_reward_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── group_goals table ─────────────────────────────────────────────
    existing_gg_cols = {col["name"] for col in inspector.get_columns("group_goals")}

    gg_migrations = [
        (
            "price_estimate",
            "ALTER TABLE group_goals ADD COLUMN price_estimate VARCHAR(60)"
        ),
        (
            "store_url",
            "ALTER TABLE group_goals ADD COLUMN store_url VARCHAR(500)"
        ),
        (
            "image_url",
            "ALTER TABLE group_goals ADD COLUMN image_url VARCHAR(500)"
        ),
        (
            "image_filename",
            "ALTER TABLE group_goals ADD COLUMN image_filename VARCHAR(255)"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in gg_migrations:
            if col_name not in existing_gg_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── wishlist_items table ──────────────────────────────────────────
    existing_wi_cols = {col["name"] for col in inspector.get_columns("wishlist_items")}

    wi_migrations = [
        (
            "price_estimate",
            "ALTER TABLE wishlist_items ADD COLUMN price_estimate VARCHAR(60)"
        ),
        (
            "store_url",
            "ALTER TABLE wishlist_items ADD COLUMN store_url VARCHAR(500)"
        ),
        (
            "image_url",
            "ALTER TABLE wishlist_items ADD COLUMN image_url VARCHAR(500)"
        ),
        (
            "image_filename",
            "ALTER TABLE wishlist_items ADD COLUMN image_filename VARCHAR(255)"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in wi_migrations:
            if col_name not in existing_wi_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── household_settings table ─────────────────────────────────────
    existing_hs_cols = {col["name"] for col in inspector.get_columns("household_settings")}

    hs_migrations = [
        (
            "auto_end_streaks",
            "ALTER TABLE household_settings ADD COLUMN auto_end_streaks BOOLEAN NOT NULL DEFAULT 0"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in hs_migrations:
            if col_name not in existing_hs_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── routine_completions table ─────────────────────────────────────
    existing_rc_cols = {col["name"] for col in inspector.get_columns("routine_completions")}

    rc_migrations = [
        (
            "voided",
            "ALTER TABLE routine_completions ADD COLUMN voided BOOLEAN NOT NULL DEFAULT 0"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in rc_migrations:
            if col_name not in existing_rc_cols:
                conn.execute(text(sql))
        conn.commit()

    # ── users table ──────────────────────────────────────────────────
    existing_user_cols = {col["name"] for col in inspector.get_columns("users")}

    user_migrations = [
        (
            "participation_enabled",
            "ALTER TABLE users ADD COLUMN participation_enabled BOOLEAN NOT NULL DEFAULT 0"
        ),
        (
            "kiosk_pin_skip",
            "ALTER TABLE users ADD COLUMN kiosk_pin_skip BOOLEAN NOT NULL DEFAULT 0"
        ),
        (
            "allowance_amount",
            "ALTER TABLE users ADD COLUMN allowance_amount INTEGER NOT NULL DEFAULT 0"
        ),
        (
            "allowance_day",
            "ALTER TABLE users ADD COLUMN allowance_day INTEGER NOT NULL DEFAULT -1"
        ),
    ]

    with db.engine.connect() as conn:
        for col_name, sql in user_migrations:
            if col_name not in existing_user_cols:
                conn.execute(text(sql))
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
