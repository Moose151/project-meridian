"""
Admin home routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.admin_home stay unchanged.
"""

from flask import redirect, render_template, url_for
from flask_login import login_required


def register_admin_home_routes(bp, admin_required):
    """
    Register admin home routes.
    """

    @bp.route("/admin")
    @login_required
    def admin_home():
        """
        Admin home page.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        return render_template("admin_home.html")
