"""
Household settings routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.household_settings stay unchanged.
"""

from datetime import datetime, timezone

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app import db
from app.forms import HouseholdSettingsForm
from app.services.settings_service import get_household_settings


def register_settings_routes(bp, admin_required):
    """
    Register household settings routes.
    """

    @bp.route("/admin/settings", methods=["GET", "POST"])
    @login_required
    def household_settings():
        """
        Admin-only page for editing household-level app settings.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        settings = get_household_settings()

        form = HouseholdSettingsForm(obj=settings)

        if form.validate_on_submit():
            settings.household_name = form.household_name.data
            settings.points_label = form.points_label.data
            settings.wishlist_requests_enabled = form.wishlist_requests_enabled.data
            settings.group_goals_enabled = form.group_goals_enabled.data
            settings.auto_end_streaks = form.auto_end_streaks.data
            settings.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            flash("Household settings updated.")
            return redirect(url_for("main.household_settings"))

        return render_template(
            "household_settings.html",
            form=form,
            settings=settings
        )
