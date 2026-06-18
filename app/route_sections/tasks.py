"""
Task routes: task board, creation, submission, management, and admin completion.

Registered onto the existing main blueprint to preserve all endpoint names.
"""

from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from sqlalchemy import or_

from app import db
from app.forms import AdminCompleteTaskForm, TaskForm
from app.models import PointTransaction, Task, TaskCategory, TaskCompletion, User
from app.services.notification_service import create_notification, notify_standard_users
from app.services.points_service import format_points


def _task_category_choices(include_current=None):
    """
    Build dropdown choices for task categories.

    Active categories appear in the dropdown.
    If a task already has a category that has since been removed,
    include it so the edit page does not break.
    """

    categories = TaskCategory.query.filter_by(
        is_active=True
    ).order_by(
        TaskCategory.name
    ).all()

    choices = [("", "No category")]

    for category in categories:
        choices.append((category.name, category.name))

    current_values = [choice[0] for choice in choices]

    if include_current and include_current not in current_values:
        choices.append((include_current, f"{include_current} (removed category)"))

    return choices


def _task_import_choices():
    """
    Build dropdown choices for importing a previous task.

    Includes inactive tasks so admins can quickly duplicate any task
    that has existed before.
    """

    tasks = Task.query.order_by(
        Task.title
    ).all()

    choices = [(0, "Do not import")]

    for task in tasks:
        status_label = "Active" if task.is_active else "Archived"
        choices.append((task.id, f"{task.title} ({status_label})"))

    return choices


def register_task_routes(bp, admin_required):
    """
    Register task board, submission, management, and admin completion routes.
    """

    # =========================================================
    # TASK BOARD AND SUBMISSION
    # =========================================================

    @bp.route("/tasks")
    @login_required
    def tasks():
        """
        Task board page.

        Shows active tasks only.

        Optional filters:
        - category
        - hot
        """

        selected_category = request.args.get("category", "")
        selected_filter = request.args.get("filter", "all")

        task_query = Task.query.filter_by(is_active=True)

        if selected_category:
            task_query = task_query.filter_by(category=selected_category)

        if selected_filter == "hot":
            task_query = task_query.filter_by(is_hot=True)

        active_tasks = task_query.order_by(
            Task.is_hot.desc(),
            Task.category,
            Task.title
        ).all()

        categories = [
            category.name
            for category in TaskCategory.query.filter_by(
                is_active=True
            ).order_by(
                TaskCategory.name
            ).all()
        ]

        return render_template(
            "tasks.html",
            tasks=active_tasks,
            categories=categories,
            selected_category=selected_category,
            selected_filter=selected_filter
        )

    @bp.route("/tasks/create", methods=["GET", "POST"])
    @login_required
    def create_task():
        """
        Admin-only page for creating a new task.

        Admins can either create a task manually or import details from a
        previous task and then edit before saving.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = TaskForm()
        form.category.choices = _task_category_choices()
        form.import_task_id.choices = _task_import_choices()

        # Allow importing from a URL such as /tasks/create?import_task_id=3
        if request.method == "GET":
            import_task_id = request.args.get("import_task_id", type=int)

            if import_task_id:
                imported_task = db.session.get(Task, import_task_id)

                if imported_task:
                    form.import_task_id.data = imported_task.id
                    form.title.data = imported_task.title
                    form.description.data = imported_task.description
                    form.point_value.data = imported_task.point_value
                    form.category.data = imported_task.category
                    form.completion_behavior.data = imported_task.completion_behavior
                    form.is_hot.data = imported_task.is_hot
                    form.hot_bonus_points.data = imported_task.hot_bonus_points
                    form.hot_label.data = imported_task.hot_label

                    flash("Task imported. Review the details, then save when ready.")

        # If admin clicked the Import button, pre-fill form and re-render.
        if request.method == "POST" and request.form.get("import_action") == "1":
            imported_task = db.session.get(Task, form.import_task_id.data)

            if not imported_task:
                flash("Selected task could not be imported.")
                return redirect(url_for("main.create_task"))

            form.title.data = imported_task.title
            form.description.data = imported_task.description
            form.point_value.data = imported_task.point_value
            form.category.data = imported_task.category
            form.completion_behavior.data = imported_task.completion_behavior
            form.is_hot.data = imported_task.is_hot
            form.hot_bonus_points.data = imported_task.hot_bonus_points
            form.hot_label.data = imported_task.hot_label

            flash("Task imported. Review the details, then save when ready.")

            return render_template("create_task.html", form=form)

        if form.validate_on_submit():
            task = Task(
                title=form.title.data,
                description=form.description.data,
                point_value=form.point_value.data,
                category=form.category.data or None,
                completion_behavior=form.completion_behavior.data,
                is_hot=form.is_hot.data,
                hot_bonus_points=form.hot_bonus_points.data or 0,
                hot_label=form.hot_label.data or None,
                is_active=True
            )

            db.session.add(task)

            if task.is_hot:
                notify_standard_users(
                    title="Hot task available",
                    message=f"'{task.title}' is now a hot task.",
                    notification_type="info",
                    action_url=url_for("main.tasks", filter="hot"),
                    action_label="View Hot Tasks"
                )

            db.session.commit()

            flash("Task created.")
            return redirect(url_for("main.tasks"))

        return render_template("create_task.html", form=form)

    @bp.route("/tasks/<int:task_id>/submit", methods=["POST"])
    @login_required
    def submit_task(task_id):
        """
        Standard user route for submitting a task as complete.

        Creates a TaskCompletion record.
        Points are not awarded until an admin approves it.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to submit tasks.")
            return redirect(url_for("main.tasks"))

        task = db.session.get(Task, task_id)

        if not task or not task.is_active:
            flash("Task not found.")
            return redirect(url_for("main.tasks"))

        existing_submission = TaskCompletion.query.filter_by(
            task_id=task.id,
            user_id=current_user.id,
            status="submitted"
        ).first()

        if existing_submission:
            flash("You already submitted this task and it is waiting for approval.")
            return redirect(url_for("main.tasks"))

        completion = TaskCompletion(
            task_id=task.id,
            user_id=current_user.id,
            status="submitted"
        )

        db.session.add(completion)
        db.session.commit()

        flash("Task submitted for approval.")
        return redirect(url_for("main.dashboard"))

    @bp.route("/tasks/submissions/<int:completion_id>/cancel", methods=["POST"])
    @login_required
    def cancel_task_submission(completion_id):
        """
        Allow a standard user to cancel their own pending task submission.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to manage task submissions.")
            return redirect(url_for("main.task_history"))

        completion = db.session.get(TaskCompletion, completion_id)

        if not completion:
            flash("Task submission not found.")
            return redirect(url_for("main.task_history"))

        if completion.user_id != current_user.id:
            flash("You can only cancel your own task submissions.")
            return redirect(url_for("main.task_history"))

        if completion.status != "submitted":
            flash("This task submission can no longer be cancelled.")
            return redirect(url_for("main.task_history"))

        completion.status = "cancelled"
        completion.reviewed_at = datetime.now(timezone.utc)
        completion.rejection_reason = "Cancelled by user."

        db.session.commit()

        flash("Task submission cancelled.")
        return redirect(url_for("main.task_history"))

    # =========================================================
    # TASK MANAGEMENT: CREATE, EDIT, HIDE, RESTORE, DELETE
    # =========================================================

    @bp.route("/admin/tasks/manage")
    @login_required
    def manage_tasks():
        """
        Admin-only task management page.

        Shows active and hidden tasks.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        all_tasks = Task.query.order_by(Task.created_at.desc()).all()

        return render_template("manage_tasks.html", tasks=all_tasks)

    @bp.route("/admin/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        """
        Admin-only page for editing an existing task.

        Changing the point value only affects future approvals.
        Existing PointTransaction records are not changed.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        task = db.session.get(Task, task_id)

        if not task:
            flash("Task not found.")
            return redirect(url_for("main.manage_tasks"))

        form = TaskForm(obj=task)
        form.category.choices = _task_category_choices(task.category)

        if form.validate_on_submit():
            was_hot = task.is_hot

            task.title = form.title.data
            task.description = form.description.data
            task.point_value = form.point_value.data
            task.category = form.category.data or None
            task.completion_behavior = form.completion_behavior.data
            task.is_hot = form.is_hot.data
            task.hot_bonus_points = form.hot_bonus_points.data or 0
            task.hot_label = form.hot_label.data or None

            # Notify users only when a task becomes hot.
            if not was_hot and task.is_hot:
                notify_standard_users(
                    title="Hot task available",
                    message=f"'{task.title}' is now a hot task.",
                    notification_type="info",
                    action_url=url_for("main.tasks", filter="hot"),
                    action_label="View Hot Tasks"
                )

            db.session.commit()

            flash("Task updated.")
            return redirect(url_for("main.manage_tasks"))

        return render_template("edit_task.html", form=form, task=task)

    @bp.route("/admin/tasks/<int:task_id>/hide", methods=["POST"])
    @login_required
    def hide_task(task_id):
        """
        Hide an active task.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        task = db.session.get(Task, task_id)

        if not task:
            flash("Task not found.")
            return redirect(url_for("main.manage_tasks"))

        task.is_active = False
        db.session.commit()

        flash("Task hidden.")
        return redirect(url_for("main.manage_tasks"))

    @bp.route("/admin/tasks/<int:task_id>/restore", methods=["POST"])
    @login_required
    def restore_task(task_id):
        """
        Restore a hidden task.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        task = db.session.get(Task, task_id)

        if not task:
            flash("Task not found.")
            return redirect(url_for("main.manage_tasks"))

        task.is_active = True
        db.session.commit()

        flash("Task restored.")
        return redirect(url_for("main.manage_tasks"))

    @bp.route("/admin/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task(task_id):
        """
        Delete a task only if it has no completion history.

        If it has history, hide it instead.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        task = db.session.get(Task, task_id)

        if not task:
            flash("Task not found.")
            return redirect(url_for("main.manage_tasks"))

        if task.completions:
            task.is_active = False
            db.session.commit()

            flash("This task has history, so it cannot be deleted. It has been hidden instead.")
            return redirect(url_for("main.manage_tasks"))

        db.session.delete(task)
        db.session.commit()

        flash("Unused task deleted.")
        return redirect(url_for("main.manage_tasks"))

    # =========================================================
    # ADMIN TASK COMPLETION
    # =========================================================

    @bp.route("/admin/tasks/complete", methods=["GET", "POST"])
    @login_required
    def admin_complete_task():
        """
        Admin-only page for marking a task complete for a user.

        Bypasses the normal submit-then-approve workflow.
        Useful when a user completed a task but did not log in to submit it.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = AdminCompleteTaskForm()

        # Include standard users and participating admins.
        active_users = User.query.filter(
            User.is_active_account == True,
            or_(
                User.role == "user",
                (User.role == "admin") & (User.participation_enabled == True)
            )
        ).order_by(
            User.display_name
        ).all()

        active_tasks = Task.query.filter_by(
            is_active=True
        ).order_by(
            Task.title
        ).all()

        form.user_id.choices = [
            (user.id, f"{user.avatar_emoji} {user.display_name}")
            for user in active_users
        ]

        form.task_id.choices = [
            (task.id, f"{task.title} ({format_points(task.total_point_value())})")
            for task in active_tasks
        ]

        if form.validate_on_submit():
            user = db.session.get(User, form.user_id.data)
            task = db.session.get(Task, form.task_id.data)

            if not user or not task:
                flash("Selected user or task not found.")
                return redirect(url_for("main.admin_complete_task"))

            if not user.can_participate() or not user.is_active_account:
                flash("Selected user is not an active participating user.")
                return redirect(url_for("main.admin_complete_task"))

            if not task.is_active:
                flash("Selected task is not active.")
                return redirect(url_for("main.admin_complete_task"))

            completion = TaskCompletion(
                task_id=task.id,
                user_id=user.id,
                status="approved",
                reviewed_at=datetime.now(timezone.utc),
                reviewed_by_id=current_user.id
            )

            db.session.add(completion)
            db.session.flush()

            awarded_points = task.total_point_value()

            transaction = PointTransaction(
                user_id=user.id,
                amount=awarded_points,
                transaction_type="task_approved",
                reason=f"Admin completed task for user: {task.title}",
                related_task_completion_id=completion.id,
                created_by_id=current_user.id
            )

            db.session.add(transaction)

            if task.completion_behavior == "hide_after_approval":
                task.is_active = False

            create_notification(
                user_id=user.id,
                title="Task completed by admin",
                message=f"'{task.title}' was marked complete for you. You earned {format_points(awarded_points)}.",
                notification_type="success"
            )

            db.session.commit()

            flash(f"Task completed for {user.display_name}. {format_points(awarded_points)} awarded.")
            return redirect(url_for("main.admin_home"))

        return render_template(
            "admin_complete_task.html",
            form=form,
            active_users=active_users,
            active_tasks=active_tasks
        )
