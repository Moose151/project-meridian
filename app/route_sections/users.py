"""
User management routes: list, create, edit, disable, restore, delete, adjust points.

Registered onto the existing main blueprint to preserve all endpoint names.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import ChangePasswordForm, EditUserForm, PointAdjustmentForm, UserForm
from app.models import PointTransaction, User
from app.services.notification_service import create_notification
from app.services.settings_service import get_points_label


def register_user_routes(bp, admin_required):
    """
    Register admin user management routes.
    """

    @bp.route("/admin/users")
    @login_required
    def users():
        """
        Admin-only user list page.

        Shows all users.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        all_users = User.query.order_by(
            User.role,
            User.display_name
        ).all()

        return render_template("users.html", users=all_users)

    @bp.route("/admin/users/create", methods=["GET", "POST"])
    @login_required
    def create_user():
        """
        Admin-only page for creating a new user.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = UserForm()

        if form.validate_on_submit():
            existing_user = User.query.filter_by(username=form.username.data).first()

            if existing_user:
                flash("Username already exists.")
                return render_template("create_user.html", form=form)

            new_user = User(
                username=form.username.data,
                display_name=form.display_name.data,
                avatar_emoji=form.avatar_emoji.data,
                role=form.role.data,
                is_active_account=True
            )

            new_user.set_password(form.password.data)

            db.session.add(new_user)
            db.session.commit()

            flash("User created.")
            return redirect(url_for("main.users"))

        return render_template("create_user.html", form=form)

    @bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_user(user_id):
        """
        Admin-only page for editing an existing user.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        form = EditUserForm(obj=user)

        if form.validate_on_submit():
            existing_user = User.query.filter_by(username=form.username.data).first()

            if existing_user and existing_user.id != user.id:
                flash("Username already exists.")
                return render_template("edit_user.html", form=form, user=user)

            user.username = form.username.data
            user.display_name = form.display_name.data
            user.avatar_emoji = form.avatar_emoji.data
            user.role = form.role.data
            user.kiosk_pin_skip = form.kiosk_pin_skip.data
            user.allowance_amount = form.allowance_amount.data or 0
            user.allowance_day = form.allowance_day.data

            db.session.commit()

            flash("User updated.")
            return redirect(url_for("main.users"))

        return render_template("edit_user.html", form=form, user=user)

    @bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
    @login_required
    def change_user_password(user_id):
        """
        Admin-only page for resetting a user's PIN/password.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        form = ChangePasswordForm()

        if form.validate_on_submit():
            user.set_password(form.password.data)

            create_notification(
                user_id=user.id,
                title="PIN/password updated",
                message="Your PIN/password was updated by an admin.",
                notification_type="info",
                action_url=url_for("main.my_profile"),
                action_label="View Profile"
            )

            db.session.commit()

            flash(f"PIN/password updated for {user.display_name}.")
            return redirect(url_for("main.user_profile", user_id=user.id))

        return render_template("change_user_password.html", form=form, user=user)

    @bp.route("/admin/users/<int:user_id>/disable", methods=["POST"])
    @login_required
    def disable_user(user_id):
        """
        Disable a user account.

        Disabled users cannot log in. History is kept.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        if user.id == current_user.id:
            flash("You cannot disable your own account.")
            return redirect(url_for("main.users"))

        user.is_active_account = False
        db.session.commit()

        flash("User disabled.")
        return redirect(url_for("main.users"))

    @bp.route("/admin/users/<int:user_id>/restore", methods=["POST"])
    @login_required
    def restore_user(user_id):
        """
        Restore a disabled user account.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        user.is_active_account = True
        db.session.commit()

        flash("User restored.")
        return redirect(url_for("main.users"))

    @bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    def delete_user(user_id):
        """
        Delete a user only if they have no history.

        If the user has history, disable instead.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        if user.id == current_user.id:
            flash("You cannot delete your own account.")
            return redirect(url_for("main.users"))

        has_history = (
            user.task_completions
            or user.reward_purchases
            or user.point_transactions
        )

        if has_history:
            user.is_active_account = False
            db.session.commit()

            flash("This user has history, so they cannot be deleted. The account has been disabled instead.")
            return redirect(url_for("main.users"))

        db.session.delete(user)
        db.session.commit()

        flash("Unused user deleted.")
        return redirect(url_for("main.users"))

    @bp.route("/admin/users/<int:user_id>/adjust-points", methods=["GET", "POST"])
    @login_required
    def adjust_points(user_id):
        """
        Admin-only page for manually adding or removing points.

        Creates a PointTransaction rather than directly changing a balance.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        user = db.session.get(User, user_id)

        if not user:
            flash("User not found.")
            return redirect(url_for("main.users"))

        form = PointAdjustmentForm()

        if form.validate_on_submit():
            transaction = PointTransaction(
                user_id=user.id,
                amount=form.amount.data,
                transaction_type="manual_adjustment",
                reason=form.reason.data,
                created_by_id=current_user.id
            )

            db.session.add(transaction)
            db.session.commit()

            flash(f"{get_points_label().capitalize()} adjustment applied.")
            return redirect(url_for("main.users"))

        return render_template("adjust_points.html", form=form, user=user)
