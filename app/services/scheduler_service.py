"""
Scheduler service.

Runs background jobs via APScheduler:
  - Daily SQLite database backup (kept for 7 days).
  - Daily allowance award for users who have a configured allowance.
"""

import os
import shutil
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def _backup_database(app):
    """Copy the SQLite database file to instance/backups/."""
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")

        # Only handle sqlite:/// URIs.
        if not db_url.startswith("sqlite:///"):
            return

        db_path = db_url.removeprefix("sqlite:///")

        # Resolve relative path relative to the instance folder.
        if not os.path.isabs(db_path):
            db_path = os.path.join(app.instance_path, db_path)

        if not os.path.exists(db_path):
            app.logger.warning("Backup: database file not found at %s", db_path)
            return

        backup_dir = os.path.join(app.instance_path, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(backup_dir, f"meridian_{stamp}.db")
        shutil.copy2(db_path, dest)
        app.logger.info("Database backed up to %s", dest)

        # Remove backups older than 7 days.
        cutoff = 7
        all_backups = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith(".db")],
            reverse=True
        )
        for old in all_backups[cutoff:]:
            try:
                os.remove(os.path.join(backup_dir, old))
                app.logger.info("Removed old backup: %s", old)
            except OSError:
                pass


def _award_allowances(app):
    """Award weekly allowance points to eligible users."""
    with app.app_context():
        from app import db
        from app.models import PointTransaction, User
        from app.services.settings_service import get_points_label

        today_weekday = date.today().weekday()  # 0=Mon … 6=Sun

        eligible = User.query.filter(
            User.is_active_account == True,
            User.allowance_amount > 0,
            User.allowance_day == today_weekday,
        ).all()

        for user in eligible:
            transaction = PointTransaction(
                user_id=user.id,
                amount=user.allowance_amount,
                transaction_type="allowance",
                reason=f"Weekly allowance",
                created_by_id=user.id,
            )
            db.session.add(transaction)
            app.logger.info(
                "Awarded %d %s allowance to %s",
                user.allowance_amount,
                get_points_label(),
                user.display_name,
            )

        if eligible:
            db.session.commit()


def start_scheduler(app):
    """
    Create and start the background scheduler.

    Called once from create_app() after the app context is fully configured.
    Jobs are skipped in testing mode (TESTING=True) or when explicitly
    disabled (SCHEDULER_ENABLED=False).
    """
    if app.config.get("TESTING") or not app.config.get("SCHEDULER_ENABLED", True):
        return

    scheduler = BackgroundScheduler()

    # Daily DB backup at 02:00.
    scheduler.add_job(
        func=_backup_database,
        args=[app],
        trigger=CronTrigger(hour=2, minute=0),
        id="db_backup",
        replace_existing=True,
    )

    # Daily allowance check at 06:00.
    scheduler.add_job(
        func=_award_allowances,
        args=[app],
        trigger=CronTrigger(hour=6, minute=0),
        id="allowance_award",
        replace_existing=True,
    )

    scheduler.start()
    app.logger.info("Background scheduler started.")
