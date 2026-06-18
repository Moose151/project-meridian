"""
Admin category management routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.manage_categories stay unchanged.
"""

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app import db
from app.forms import CategoryForm
from app.models import RewardCategory, TaskCategory


def register_category_routes(bp, admin_required):
    """
    Register task and reward category management routes.
    """

    @bp.route("/admin/categories")
    @login_required
    def manage_categories():
        """
        Admin-only category management page.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        task_form = CategoryForm()
        reward_form = CategoryForm()

        task_categories = TaskCategory.query.order_by(
            TaskCategory.is_active.desc(),
            TaskCategory.name
        ).all()

        reward_categories = RewardCategory.query.order_by(
            RewardCategory.is_active.desc(),
            RewardCategory.name
        ).all()

        return render_template(
            "manage_categories.html",
            task_form=task_form,
            reward_form=reward_form,
            task_categories=task_categories,
            reward_categories=reward_categories
        )

    @bp.route("/admin/categories/task/add", methods=["POST"])
    @login_required
    def add_task_category():
        """
        Add a new task category.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = CategoryForm()

        if form.validate_on_submit():
            name = form.name.data.strip()

            existing = TaskCategory.query.filter_by(
                name=name
            ).first()

            if existing:
                existing.is_active = True
                db.session.commit()
                flash("Task category already existed and has been restored.")
                return redirect(url_for("main.manage_categories"))

            category = TaskCategory(
                name=name,
                is_active=True
            )

            db.session.add(category)
            db.session.commit()

            flash("Task category added.")

        return redirect(url_for("main.manage_categories"))

    @bp.route("/admin/categories/reward/add", methods=["POST"])
    @login_required
    def add_reward_category():
        """
        Add a new reward category.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = CategoryForm()

        if form.validate_on_submit():
            name = form.name.data.strip()

            existing = RewardCategory.query.filter_by(
                name=name
            ).first()

            if existing:
                existing.is_active = True
                db.session.commit()
                flash("Reward category already existed and has been restored.")
                return redirect(url_for("main.manage_categories"))

            category = RewardCategory(
                name=name,
                is_active=True
            )

            db.session.add(category)
            db.session.commit()

            flash("Reward category added.")

        return redirect(url_for("main.manage_categories"))

    @bp.route("/admin/categories/task/<int:category_id>/remove", methods=["POST"])
    @login_required
    def remove_task_category(category_id):
        """
        Remove a task category from dropdowns.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        category = db.session.get(TaskCategory, category_id)

        if not category:
            flash("Task category not found.")
            return redirect(url_for("main.manage_categories"))

        category.is_active = False
        db.session.commit()

        flash("Task category removed from dropdowns.")
        return redirect(url_for("main.manage_categories"))

    @bp.route("/admin/categories/reward/<int:category_id>/remove", methods=["POST"])
    @login_required
    def remove_reward_category(category_id):
        """
        Remove a reward category from dropdowns.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        category = db.session.get(RewardCategory, category_id)

        if not category:
            flash("Reward category not found.")
            return redirect(url_for("main.manage_categories"))

        category.is_active = False
        db.session.commit()

        flash("Reward category removed from dropdowns.")
        return redirect(url_for("main.manage_categories"))

    @bp.route("/admin/categories/task/<int:category_id>/restore", methods=["POST"])
    @login_required
    def restore_task_category(category_id):
        """
        Restore a removed task category.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        category = db.session.get(TaskCategory, category_id)

        if not category:
            flash("Task category not found.")
            return redirect(url_for("main.manage_categories"))

        category.is_active = True
        db.session.commit()

        flash("Task category restored.")
        return redirect(url_for("main.manage_categories"))

    @bp.route("/admin/categories/reward/<int:category_id>/restore", methods=["POST"])
    @login_required
    def restore_reward_category(category_id):
        """
        Restore a removed reward category.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        category = db.session.get(RewardCategory, category_id)

        if not category:
            flash("Reward category not found.")
            return redirect(url_for("main.manage_categories"))

        category.is_active = True
        db.session.commit()

        flash("Reward category restored.")
        return redirect(url_for("main.manage_categories"))
