"""
Authentication routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.login and main.logout stay unchanged.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.forms import LoginForm
from app.models import User


def register_auth_routes(bp):
    """
    Register index, login, and logout routes.
    """

    @bp.route("/")
    def index():
        """
        Home route.

        If already logged in, go to dashboard.
        If not logged in, go to login.
        """

        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        return redirect(url_for("main.login"))

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        """
        Avatar login page.
        """

        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        form = LoginForm()

        active_users = User.query.filter_by(
            is_active_account=True
        ).order_by(
            User.role,
            User.display_name
        ).all()

        if form.validate_on_submit():
            try:
                selected_user_id = int(form.selected_user_id.data)
            except ValueError:
                flash("Please select a user.")
                return render_template(
                    "login.html",
                    form=form,
                    users=active_users
                )

            user = db.session.get(User, selected_user_id)

            if not user:
                flash("Selected user not found.")
                return render_template(
                    "login.html",
                    form=form,
                    users=active_users
                )

            if not user.is_active_account:
                flash("This account has been disabled.")
                return render_template(
                    "login.html",
                    form=form,
                    users=active_users
                )

            if user.check_password(form.password.data):
                login_user(user)
                flash("Logged in successfully.")
                return redirect(url_for("main.dashboard"))

            flash("Invalid PIN.")

        return render_template(
            "login.html",
            form=form,
            users=active_users
        )

    @bp.route("/logout")
    @login_required
    def logout():
        """
        Logout route.
        """

        logout_user()
        flash("Logged out.")
        return redirect(url_for("main.login"))
