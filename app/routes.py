# Import datetime tools so we can record when approvals and reviews happen.
from datetime import datetime, timezone

# Import Flask helpers.
# Blueprint groups routes together.
# render_template loads HTML templates.
# redirect and url_for move users between pages.
# flash shows short messages to the user.
from flask import Blueprint, render_template, redirect, url_for, flash, request

# Import Flask-Login helpers.
# login_required protects pages from users who are not logged in.
# current_user represents the currently logged-in user.
from flask_login import login_required, current_user

# Import the database object so we can add, update, and delete records.
from app import db

# Import all forms used by the app.
from app.forms import (
    TaskForm,
    RewardForm,
    UserForm,
    EditUserForm,
    ChangePasswordForm,
    PointAdjustmentForm,
    AdminCompleteTaskForm,
    RejectionReasonForm,
)

# Import all database models used by the routes.
from app.models import (
    User,
    Task,
    TaskCompletion,
    Reward,
    RewardPurchase,
    PointTransaction,
    TaskCategory,
    RewardCategory,
    Notification,
)

from app.services.settings_service import (
    get_household_settings,
    get_points_label,
)

from app.services.badge_service import check_and_award_badges

from app.services.points_service import format_points

from app.services.task_service import (
    approve_submitted_task_completion,
    admin_complete_task_for_user,
)

from app.services.reward_service import (
    create_reward_reservation,
    approve_reward_purchase_request,
    reject_reward_purchase_request,
    cancel_reward_purchase_request,
)

from app.route_sections.admin_exports import register_admin_export_routes
from app.route_sections.activity import register_activity_routes
from app.route_sections.auth import register_auth_routes
from app.route_sections.categories import register_category_routes
from app.route_sections.dashboard import register_dashboard_routes
from app.route_sections.group_goals import register_group_goal_routes
from app.route_sections.leaderboard import register_leaderboard_routes
from app.route_sections.profiles import register_profile_routes
from app.route_sections.request_archive import register_request_archive_routes
from app.route_sections.settings import register_settings_routes
from app.route_sections.wishlist import register_wishlist_routes

# Create the main blueprint.
# All routes in this file are registered under this blueprint.
bp = Blueprint("main", __name__)

@bp.app_context_processor
def inject_household_settings():
    """
    Make household settings available to all templates.
    """

    settings = get_household_settings()

    return {
        "household_settings": settings
    }


def admin_required():
    """
    Helper function for admin-only pages.

    Returns True if the current user is an admin.
    Returns False if the current user is not allowed.
    """

    # If the user is not logged in or is not an admin, block the action.
    if not current_user.is_authenticated or not current_user.is_admin():
        flash("Admin access required.")
        return False

    return True


register_admin_export_routes(bp, admin_required)
register_activity_routes(bp)
register_auth_routes(bp)
register_category_routes(bp, admin_required)
register_dashboard_routes(bp)
register_group_goal_routes(bp, admin_required)
register_leaderboard_routes(bp)
register_profile_routes(bp)
register_request_archive_routes(bp)
register_settings_routes(bp, admin_required)
register_wishlist_routes(bp, admin_required)


def task_category_choices(include_current=None):
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



def reward_category_choices(include_current=None):
    """
    Build dropdown choices for reward categories.

    Active categories appear in the dropdown.

    If a reward already has a category that has since been removed,
    include it so the edit page does not break.
    """

    categories = RewardCategory.query.filter_by(
        is_active=True
    ).order_by(
        RewardCategory.name
    ).all()

    choices = [("", "No category")]

    for category in categories:
        choices.append((category.name, category.name))

    current_values = [choice[0] for choice in choices]

    if include_current and include_current not in current_values:
        choices.append((include_current, f"{include_current} (removed category)"))

    return choices

def reward_import_choices():
    """
    Build dropdown choices for importing a previous reward.

    Includes active and archived rewards so admins can quickly duplicate
    any reward that has existed before.
    """

    rewards = Reward.query.order_by(
        Reward.name
    ).all()

    choices = [
        (0, "Do not import")
    ]

    for reward in rewards:
        status_label = "Active" if reward.is_active else "Archived"

        choices.append(
            (
                reward.id,
                f"{reward.name} ({status_label})"
            )
        )

    return choices

def create_notification(
    user_id,
    title,
    message,
    notification_type="info",
    action_url=None,
    action_label=None
):
    """
    Create a dashboard notification for a user.

    notification_type controls visual styling:
    - success
    - warning
    - danger
    - info

    action_url and action_label are optional.
    If provided, the dashboard shows an action button.
    """

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_label=action_label,
        is_read=False
    )

    db.session.add(notification)

def notify_admins(
    title,
    message,
    notification_type="info",
    action_url=None,
    action_label=None
):
    """
    Create a dashboard notification for every active admin user.
    """

    admins = User.query.filter_by(
        role="admin",
        is_active_account=True
    ).all()

    for admin in admins:
        create_notification(
            user_id=admin.id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_label=action_label
        )

def notify_standard_users(title, message, notification_type="info", action_url=None, action_label=None):
    """
    Send a notification to every active standard user.
    """

    users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).all()

    for user in users:
        create_notification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_label=action_label
        )


def task_import_choices():
    """
    Build dropdown choices for importing a previous task.

    Includes inactive tasks and active tasks so admins can quickly duplicate
    any task that has existed before.
    """

    tasks = Task.query.order_by(
        Task.title
    ).all()

    choices = [
        (0, "Do not import")
    ]

    for task in tasks:
        status_label = "Active" if task.is_active else "Archived"

        choices.append(
            (
                task.id,
                f"{task.title} ({status_label})"
            )
        )

    return choices


# =========================================================
# TASKS: CREATE, VIEW, SUBMIT
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

    # Get selected filters from the URL query string.
    selected_category = request.args.get("category", "")
    selected_filter = request.args.get("filter", "all")

    # Start with active tasks only.
    task_query = Task.query.filter_by(
        is_active=True
    )

    # Apply category filter if one is selected.
    if selected_category:
        task_query = task_query.filter_by(
            category=selected_category
        )

    # Apply hot-task filter.
    if selected_filter == "hot":
        task_query = task_query.filter_by(
            is_hot=True
        )

    # Hot tasks appear first, then category, then title.
    active_tasks = task_query.order_by(
        Task.is_hot.desc(),
        Task.category,
        Task.title
    ).all()

    # Build the category dropdown from the admin-managed task category list.
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

    Admins can either:
    - create a task manually
    - import details from a previous task and then edit before saving
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Create the task form.
    form = TaskForm()

    # Populate category dropdown.
    form.category.choices = task_category_choices()

    # Populate previous task import dropdown.
    form.import_task_id.choices = task_import_choices()
    # Allow importing from a URL such as:
    # /tasks/create?import_task_id=3
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

    # If admin selected a previous task and clicked Import,
    # pre-fill the form from that task instead of creating a task.
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

        return render_template(
            "create_task.html",
            form=form
        )

    # If form is submitted and valid, create the task.
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

    return render_template(
        "create_task.html",
        form=form
    )

    


@bp.route("/tasks/<int:task_id>/submit", methods=["POST"])
@login_required
def submit_task(task_id):
    """
    Standard user route for submitting a task as complete.

    This creates a TaskCompletion record.
    It does not award points until an admin approves it.
    """

    # Admins should not submit tasks.
    if current_user.is_admin():
        flash("Admins do not submit tasks.")
        return redirect(url_for("main.tasks"))

    # Find the task.
    task = db.session.get(Task, task_id)

    # Stop if task does not exist or is hidden.
    if not task or not task.is_active:
        flash("Task not found.")
        return redirect(url_for("main.tasks"))

    # Prevent duplicate pending submissions for the same task/user.
    existing_submission = TaskCompletion.query.filter_by(
        task_id=task.id,
        user_id=current_user.id,
        status="submitted"
    ).first()

    if existing_submission:
        flash("You already submitted this task and it is waiting for approval.")
        return redirect(url_for("main.tasks"))

    # Create a new task completion submission.
    completion = TaskCompletion(
        task_id=task.id,
        user_id=current_user.id,
        status="submitted"
    )

    # Save the submission.
    db.session.add(completion)
    db.session.commit()

    flash("Task submitted for approval.")
    return redirect(url_for("main.dashboard"))


# =========================================================
# ADMIN APPROVALS: TASKS AND REWARDS
# =========================================================

@bp.route("/admin/approvals")
@login_required
def admin_approvals():
    """
    Admin approval queue.

    Shows:
    - submitted task completions
    - requested reward purchases
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Get task submissions waiting for review.
    pending_tasks = TaskCompletion.query.filter_by(
        status="submitted"
    ).all()

    # Get reward purchase requests waiting for review.
    pending_purchases = RewardPurchase.query.filter_by(
        status="requested"
    ).all()

    return render_template(
        "admin_approvals.html",
        pending_tasks=pending_tasks,
        pending_purchases=pending_purchases
    )


@bp.route("/admin/tasks/<int:completion_id>/approve", methods=["POST"])
@login_required
def approve_task_completion(completion_id):
    """
    Approve a submitted task completion.

    The task approval business logic is handled by task_service.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the submitted task completion.
    completion = db.session.get(TaskCompletion, completion_id)

    # Stop if it does not exist or is not pending.
    if not completion or completion.status != "submitted":
        flash("Task completion request not found.")
        return redirect(url_for("main.admin_approvals"))

    # Approve the task, create the point transaction, notify the user,
    # hide one-off tasks if needed, and check badge eligibility.
    awarded_points = approve_submitted_task_completion(completion)

    # Save approval, transaction, notifications, and badge updates.
    db.session.commit()

    flash(f"Task approved and {format_points(awarded_points)} awarded.")
    return redirect(url_for("main.admin_approvals"))


@bp.route("/admin/tasks/<int:completion_id>/reject", methods=["GET", "POST"])
@login_required
def reject_task_completion(completion_id):
    """
    Reject a submitted task completion.

    New behaviour:
    - Admin is shown a rejection form.
    - Admin must enter a short rejection reason.
    - Reason appears in Task History.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the task completion.
    completion = db.session.get(TaskCompletion, completion_id)

    # Stop if it does not exist or is no longer waiting for review.
    if not completion or completion.status != "submitted":
        flash("Task completion request not found.")
        return redirect(url_for("main.admin_approvals"))

    # Create rejection form.
    form = RejectionReasonForm()

    # If the form was submitted and valid, reject the task.
    if form.validate_on_submit():

        completion.status = "rejected"
        completion.reviewed_at = datetime.now(timezone.utc)
        completion.reviewed_by_id = current_user.id
        completion.rejection_reason = form.reason.data.strip()

        # Notify the user that the task was rejected.
        create_notification(
            user_id=completion.user_id,
            title="Task rejected",
            message=f"Your task '{completion.task.title}' was rejected. Reason: {completion.rejection_reason}",
            notification_type="danger"
        )

        db.session.commit()

        flash("Task completion rejected.")
        return redirect(url_for("main.admin_approvals"))

    # Show rejection reason form.
    return render_template(
        "reject_task_completion.html",
        form=form,
        completion=completion
    )


@bp.route("/admin/rewards/<int:purchase_id>/approve", methods=["POST"])
@login_required
def approve_reward_purchase(purchase_id):
    """
    Approve a requested reward purchase.

    The reward approval business logic is handled by reward_service.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the purchase request.
    purchase = db.session.get(RewardPurchase, purchase_id)

    # Stop if it does not exist or is not pending.
    if not purchase or purchase.status != "requested":
        flash("Reward purchase request not found.")
        return redirect(url_for("main.admin_approvals"))

    # Approve the reward request.
    # This returns False if a legacy unreserved request can no longer be afforded.
    approved = approve_reward_purchase_request(purchase)

    if not approved:
        flash(f"User no longer has enough {get_points_label()} for this reward.")
        return redirect(url_for("main.admin_approvals"))

    db.session.commit()

    flash("Reward approved.")
    return redirect(url_for("main.admin_approvals"))


@bp.route("/admin/rewards/<int:purchase_id>/reject", methods=["GET", "POST"])
@login_required
def reject_reward_purchase(purchase_id):
    """
    Reject a requested reward purchase.

    The reward rejection and refund logic is handled by reward_service.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the reward purchase request.
    purchase = db.session.get(RewardPurchase, purchase_id)

    # Stop if it does not exist or is no longer pending.
    if not purchase or purchase.status != "requested":
        flash("Reward purchase request not found.")
        return redirect(url_for("main.admin_approvals"))

    # Create rejection form.
    form = RejectionReasonForm()

    # If the form was submitted and valid, reject the reward request.
    if form.validate_on_submit():

        reject_reward_purchase_request(
            purchase=purchase,
            rejection_reason=form.reason.data.strip()
        )

        db.session.commit()

        flash(f"Reward request rejected and reserved {get_points_label()} refunded.")
        return redirect(url_for("main.admin_approvals"))

    # Show rejection reason form.
    return render_template(
        "reject_reward_purchase.html",
        form=form,
        purchase=purchase
    )


# =========================================================
# SHOP AND REWARDS
# =========================================================

@bp.route("/shop")
@login_required
def shop():
    """
    Reward shop page.

    Shows active rewards only.

    Optional filter:
    - category
    """

    # Get selected category from the URL query string.
    selected_category = request.args.get("category", "")

    # Start with active rewards only.
    reward_query = Reward.query.filter_by(
        is_active=True
    )

    # Apply category filter if one is selected.
    if selected_category:
        reward_query = reward_query.filter_by(
            category=selected_category
        )

    # Get the filtered reward list.
    rewards = reward_query.order_by(
        Reward.category,
        Reward.point_cost,
        Reward.name
    ).all()

    # Build the category dropdown from the admin-managed reward category list.
    categories = [
        category.name
        for category in RewardCategory.query.filter_by(
            is_active=True
        ).order_by(
            RewardCategory.name
        ).all()
    ]

    return render_template(
        "shop.html",
        rewards=rewards,
        categories=categories,
        selected_category=selected_category
    )


@bp.route("/rewards/create", methods=["GET", "POST"])
@login_required
def create_reward():
    """
    Admin-only page for creating a new reward.

    Admins can either:
    - create a reward manually
    - import details from a previous reward and then edit before saving
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Create the reward form.
    form = RewardForm()

    # Populate category dropdown.
    form.category.choices = reward_category_choices()

    # Populate previous reward import dropdown.
    form.import_reward_id.choices = reward_import_choices()
    # Allow importing from a URL such as:
    # /rewards/create?import_reward_id=5
    if request.method == "GET":

        import_reward_id = request.args.get("import_reward_id", type=int)

        if import_reward_id:

            imported_reward = db.session.get(Reward, import_reward_id)

            if imported_reward:
                form.import_reward_id.data = imported_reward.id
                form.name.data = imported_reward.name
                form.description.data = imported_reward.description
                form.point_cost.data = imported_reward.point_cost
                form.category.data = imported_reward.category

                flash("Reward imported. Review the details, then save when ready.")

    # If admin selected a previous reward and clicked Import,
    # pre-fill the form from that reward instead of creating a reward.
    if request.method == "POST" and request.form.get("import_action") == "1":

        imported_reward = db.session.get(Reward, form.import_reward_id.data)

        if not imported_reward:
            flash("Selected reward could not be imported.")
            return redirect(url_for("main.create_reward"))

        form.name.data = imported_reward.name
        form.description.data = imported_reward.description
        form.point_cost.data = imported_reward.point_cost
        form.category.data = imported_reward.category

        flash("Reward imported. Review the details, then save when ready.")

        return render_template(
            "create_reward.html",
            form=form
        )

    # If form is submitted and valid, create the reward.
    if form.validate_on_submit():

        reward = Reward(
            name=form.name.data,
            description=form.description.data,
            point_cost=form.point_cost.data,
            category=form.category.data or None,
            is_active=True
        )

        db.session.add(reward)
        db.session.commit()

        flash("Reward created.")
        return redirect(url_for("main.shop"))

    return render_template(
        "create_reward.html",
        form=form
    )


@bp.route("/shop/<int:reward_id>/request", methods=["POST"])
@login_required
def request_reward(reward_id):
    """
    Standard user route for requesting a reward.

    New behaviour:
    - Points are reserved immediately when the reward is requested.
    - This prevents users from requesting more rewards than they can afford.
    - If the request is cancelled or rejected, the points are refunded.
    - If the request is approved, no further deduction is needed.
    """

    # Admins should not request rewards.
    if current_user.is_admin():
        flash("Admins do not request rewards.")
        return redirect(url_for("main.shop"))

    # Find the reward being requested.
    reward = db.session.get(Reward, reward_id)

    # Stop if the reward does not exist or is hidden.
    if not reward or not reward.is_active:
        flash("Reward not found.")
        return redirect(url_for("main.shop"))

    # Optional spam protection:
    # Prevent the same user from having multiple pending requests
    # for the exact same reward.
    existing_request = RewardPurchase.query.filter_by(
        reward_id=reward.id,
        user_id=current_user.id,
        status="requested"
    ).first()

    if existing_request:
        flash("You already have a pending request for this reward.")
        return redirect(url_for("main.shop"))

    # Check whether the user can afford the reward using their current balance.
    # Because pending requests now create negative point transactions,
    # this balance already accounts for reserved points.
    if current_user.point_balance() < reward.point_cost:
        flash(f"You do not have enough {get_points_label()} for this reward.")
        return redirect(url_for("main.shop"))

    # Create the reward purchase request.
    purchase = RewardPurchase(
        reward_id=reward.id,
        user_id=current_user.id,
        status="requested"
    )

    # Add the purchase first.
    db.session.add(purchase)

    # Flush sends the new purchase to the database session and gives it an ID
    # without committing the whole transaction yet.
    # We need purchase.id so the point transaction can link to it.
    db.session.flush()

    # Create a negative point transaction immediately.
    # This reserves/deducts the points while the request is pending.
    # Reserve/deduct the reward cost while the request is pending.
    create_reward_reservation(purchase)

    # Commit both:
    # - the reward purchase request
    # - the point reservation transaction
    db.session.commit()

    flash(f"Reward requested. {get_points_label().capitalize()} have been reserved pending approval.")
    return redirect(url_for("main.dashboard"))


# =========================================================
# USER MANAGEMENT
# =========================================================

@bp.route("/admin/users")
@login_required
def users():
    """
    Admin-only user list page.

    Shows all users.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Get all users.
    all_users = User.query.order_by(
        User.role,
        User.display_name
    ).all()

    return render_template(
        "users.html",
        users=all_users
    )


@bp.route("/admin/users/create", methods=["GET", "POST"])
@login_required
def create_user():
    """
    Admin-only page for creating a new user.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Create user form.
    form = UserForm()

    # If form submitted and valid, create user.
    if form.validate_on_submit():

        # Check username is not already used.
        existing_user = User.query.filter_by(
            username=form.username.data
        ).first()

        if existing_user:
            flash("Username already exists.")
            return render_template(
                "create_user.html",
                form=form
            )

        # Create user.
        new_user = User(
            username=form.username.data,
            display_name=form.display_name.data,
            avatar_emoji=form.avatar_emoji.data,
            role=form.role.data,
            is_active_account=True
        )

        # Hash password/PIN before saving.
        new_user.set_password(form.password.data)

        db.session.add(new_user)
        db.session.commit()

        flash("User created.")
        return redirect(url_for("main.users"))

    return render_template(
        "create_user.html",
        form=form
    )


@bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    """
    Admin-only page for editing an existing user.

    Admins can change:
    - username
    - display name
    - role
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.users"))

    # Pre-fill form with current user details.
    form = EditUserForm(obj=user)

    # If submitted and valid, save changes.
    if form.validate_on_submit():

        # Check if another user already has this username.
        existing_user = User.query.filter_by(
            username=form.username.data
        ).first()

        if existing_user and existing_user.id != user.id:
            flash("Username already exists.")
            return render_template(
                "edit_user.html",
                form=form,
                user=user
            )

        # Update user fields.
        user.username = form.username.data
        user.display_name = form.display_name.data
        user.avatar_emoji = form.avatar_emoji.data
        user.role = form.role.data

        db.session.commit()

        flash("User updated.")
        return redirect(url_for("main.users"))

    return render_template(
        "edit_user.html",
        form=form,
        user=user
    )


@bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
@login_required
def change_user_password(user_id):
    """
    Admin-only page for resetting a user's PIN/password.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the selected user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.users"))

    form = ChangePasswordForm()

    if form.validate_on_submit():

        # Update the user's password/PIN using the model helper.
        user.set_password(form.password.data)

        # Notify the user that an admin changed their PIN/password.
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
        return redirect(
            url_for(
                "main.user_profile",
                user_id=user.id
            )
        )

    return render_template(
        "change_user_password.html",
        form=form,
        user=user
    )

@bp.route("/admin/users/<int:user_id>/disable", methods=["POST"])
@login_required
def disable_user(user_id):
    """
    Disable a user account.

    Disabled users cannot log in.
    History is kept.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.users"))

    # Prevent disabling own account.
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

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find user.
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

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.users"))

    # Prevent deleting own account.
    if user.id == current_user.id:
        flash("You cannot delete your own account.")
        return redirect(url_for("main.users"))

    # Check for linked history.
    has_history = (
        user.task_completions
        or user.reward_purchases
        or user.point_transactions
    )

    # If history exists, disable instead of deleting.
    if has_history:
        user.is_active_account = False
        db.session.commit()

        flash("This user has history, so they cannot be deleted. The account has been disabled instead.")
        return redirect(url_for("main.users"))

    # If no history exists, delete.
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

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.users"))

    # Create adjustment form.
    form = PointAdjustmentForm()

    # If submitted and valid, create point transaction.
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

    return render_template(
        "adjust_points.html",
        form=form,
        user=user
    )


# =========================================================
# TASK MANAGEMENT: HIDE, RESTORE, DELETE UNUSED
# =========================================================

@bp.route("/admin/tasks/manage")
@login_required
def manage_tasks():
    """
    Admin-only task management page.

    Shows active and hidden tasks.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Get all tasks, newest first.
    all_tasks = Task.query.order_by(
        Task.created_at.desc()
    ).all()

    return render_template(
        "manage_tasks.html",
        tasks=all_tasks
    )


@bp.route("/admin/tasks/<int:task_id>/hide", methods=["POST"])
@login_required
def hide_task(task_id):
    """
    Hide an active task.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find task.
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

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find task.
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

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find task.
    task = db.session.get(Task, task_id)

    if not task:
        flash("Task not found.")
        return redirect(url_for("main.manage_tasks"))

    # If task has completions, hide instead of deleting.
    if task.completions:
        task.is_active = False
        db.session.commit()

        flash("This task has history, so it cannot be deleted. It has been hidden instead.")
        return redirect(url_for("main.manage_tasks"))

    # If no completions, delete.
    db.session.delete(task)
    db.session.commit()

    flash("Unused task deleted.")
    return redirect(url_for("main.manage_tasks"))


# =========================================================
# REWARD MANAGEMENT: HIDE, RESTORE, DELETE UNUSED
# =========================================================

@bp.route("/admin/rewards/manage")
@login_required
def manage_rewards():
    """
    Admin-only reward management page.

    Shows active and hidden rewards.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Get all rewards, newest first.
    all_rewards = Reward.query.order_by(
        Reward.created_at.desc()
    ).all()

    return render_template(
        "manage_rewards.html",
        rewards=all_rewards
    )


@bp.route("/admin/rewards/<int:reward_id>/hide", methods=["POST"])
@login_required
def hide_reward(reward_id):
    """
    Hide an active reward.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find reward.
    reward = db.session.get(Reward, reward_id)

    if not reward:
        flash("Reward not found.")
        return redirect(url_for("main.manage_rewards"))

    reward.is_active = False
    db.session.commit()

    flash("Reward hidden.")
    return redirect(url_for("main.manage_rewards"))


@bp.route("/admin/rewards/<int:reward_id>/restore", methods=["POST"])
@login_required
def restore_reward(reward_id):
    """
    Restore a hidden reward.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find reward.
    reward = db.session.get(Reward, reward_id)

    if not reward:
        flash("Reward not found.")
        return redirect(url_for("main.manage_rewards"))

    reward.is_active = True
    db.session.commit()

    flash("Reward restored.")
    return redirect(url_for("main.manage_rewards"))


@bp.route("/admin/rewards/<int:reward_id>/delete", methods=["POST"])
@login_required
def delete_reward(reward_id):
    """
    Delete a reward only if it has no purchase history.

    If it has history, hide it instead.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find reward.
    reward = db.session.get(Reward, reward_id)

    if not reward:
        flash("Reward not found.")
        return redirect(url_for("main.manage_rewards"))

    # If reward has purchases, hide instead of deleting.
    if reward.purchases:
        reward.is_active = False
        db.session.commit()

        flash("This reward has history, so it cannot be deleted. It has been hidden instead.")
        return redirect(url_for("main.manage_rewards"))

    # If no purchases, delete.
    db.session.delete(reward)
    db.session.commit()

    flash("Unused reward deleted.")
    return redirect(url_for("main.manage_rewards"))


# =========================================================
# EDIT TASKS AND REWARDS
# =========================================================

@bp.route("/admin/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    """
    Admin-only page for editing an existing task.

    Admins can change:
    - title
    - description
    - point value
    - category

    Important:
    Changing the point value only affects future approvals.
    Existing PointTransaction records are not changed.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the task being edited.
    task = db.session.get(Task, task_id)

    if not task:
        flash("Task not found.")
        return redirect(url_for("main.manage_tasks"))

    # Pre-fill the existing task details into the form.
    form = TaskForm(obj=task)
    form.category.choices = task_category_choices(task.category)

    # If the form was submitted and is valid, save the changes.
    if form.validate_on_submit():

        # Track whether this edit changes the task from normal to hot.
        was_hot = task.is_hot

        # Update task fields from the form.
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

        # Save changes to the database.
        db.session.commit()

        flash("Task updated.")
        return redirect(url_for("main.manage_tasks"))

    # For a normal GET request, show the edit form.
    return render_template(
        "edit_task.html",
        form=form,
        task=task
    )


@bp.route("/admin/rewards/<int:reward_id>/edit", methods=["GET", "POST"])
@login_required
def edit_reward(reward_id):
    """
    Admin-only page for editing an existing reward.

    Admins can change:
    - name
    - description
    - category
    - point cost
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the reward being edited.
    reward = db.session.get(Reward, reward_id)

    if not reward:
        flash("Reward not found.")
        return redirect(url_for("main.manage_rewards"))

    # Pre-fill the existing reward details into the form.
    form = RewardForm(obj=reward)

    # Populate reward category dropdown.
    # If this reward has an old/removed category, include it so the page does not break.
    form.category.choices = reward_category_choices(reward.category)

    # If the form was submitted and is valid, save the changes.
    if form.validate_on_submit():

        reward.name = form.name.data
        reward.description = form.description.data
        reward.category = form.category.data or None
        reward.point_cost = form.point_cost.data

        db.session.commit()

        flash("Reward updated.")
        return redirect(url_for("main.manage_rewards"))

    return render_template(
        "edit_reward.html",
        form=form,
        reward=reward
    )

# =========================================================
# ADMIN HOME PAGE
# =========================================================

@bp.route("/admin")
@login_required
def admin_home():
    """
    Admin home page.

    This page acts as a central menu for admin tools.

    Instead of putting every admin action in the top navbar,
    we link to this one Admin page and put the admin tools there.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    return render_template("admin_home.html")

# =========================================================
# USER CANCELLATION / RESCIND REQUESTS
# =========================================================

@bp.route("/tasks/submissions/<int:completion_id>/cancel", methods=["POST"])
@login_required
def cancel_task_submission(completion_id):
    """
    Allow a standard user to cancel their own task submission.

    This is only allowed while the task completion is still waiting
    for admin approval.

    Users cannot cancel after approval or rejection.
    """

    # Admins do not need this action.
    if current_user.is_admin():
        flash("Admins do not cancel task submissions.")
        return redirect(url_for("main.task_history"))

    # Find the submitted task completion.
    completion = db.session.get(TaskCompletion, completion_id)

    # Stop if the record does not exist.
    if not completion:
        flash("Task submission not found.")
        return redirect(url_for("main.task_history"))

    # Users can only cancel their own submissions.
    if completion.user_id != current_user.id:
        flash("You can only cancel your own task submissions.")
        return redirect(url_for("main.task_history"))

    # Only pending submissions can be cancelled.
    if completion.status != "submitted":
        flash("This task submission can no longer be cancelled.")
        return redirect(url_for("main.task_history"))

    # Mark the submission as cancelled.
    completion.status = "cancelled"
    completion.reviewed_at = datetime.now(timezone.utc)
    completion.rejection_reason = "Cancelled by user."

    # Save the change.
    db.session.commit()

    flash("Task submission cancelled.")
    return redirect(url_for("main.task_history"))


@bp.route("/shop/requests/<int:purchase_id>/cancel", methods=["POST"])
@login_required
def cancel_reward_request(purchase_id):
    """
    Allow a standard user to cancel their own reward request.

    New behaviour:
    - This is only allowed while the request is still pending.
    - If points were reserved, they are refunded.
    """

    # Admins do not need this action.
    if current_user.is_admin():
        flash("Admins do not cancel reward requests.")
        return redirect(url_for("main.reward_history"))

    # Find the reward purchase request.
    purchase = db.session.get(RewardPurchase, purchase_id)

    # Stop if the record does not exist.
    if not purchase:
        flash("Reward request not found.")
        return redirect(url_for("main.reward_history"))

    # Users can only cancel their own reward requests.
    if purchase.user_id != current_user.id:
        flash("You can only cancel your own reward requests.")
        return redirect(url_for("main.reward_history"))

    # Only pending reward requests can be cancelled.
    if purchase.status != "requested":
        flash("This reward request can no longer be cancelled.")
        return redirect(url_for("main.reward_history"))

    # Look for the original point reservation.
    reservation = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type="reward_requested"
    ).first()

    # Check whether a cancellation refund already exists.
    # This prevents accidental double refunds.
    existing_refund = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type="reward_cancelled_refund"
    ).first()

    # If points were reserved and have not already been refunded,
    # create a positive transaction to return the points.
    if reservation and not existing_refund:
        refund = PointTransaction(
            user_id=purchase.user_id,
            amount=purchase.reward.point_cost,
            transaction_type="reward_cancelled_refund",
            reason=f"Refunded cancelled reward request: {purchase.reward.name}",
            related_reward_purchase_id=purchase.id,
            created_by_id=current_user.id
        )

        db.session.add(refund)

    # Mark the reward request as cancelled.
    purchase.status = "cancelled"
    purchase.reviewed_at = datetime.now(timezone.utc)
    purchase.rejection_reason = "Cancelled by user."

    # Save cancellation and possible refund.
    db.session.commit()

    flash("Reward request cancelled and reserved balance refunded.")
    return redirect(url_for("main.reward_history"))

# =========================================================
# ADMIN TASK COMPLETION
# =========================================================

@bp.route("/admin/tasks/complete", methods=["GET", "POST"])
@login_required
def admin_complete_task():
    """
    Admin-only page for marking a task complete for a user.

    This bypasses the normal workflow:
    - User submits task
    - Admin approves task

    Instead, the admin directly records:
    - an approved TaskCompletion
    - a positive PointTransaction

    This is useful when a user completed a task but did not log in to submit it.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Create the form.
    form = AdminCompleteTaskForm()

    # Get active standard users only.
    # Admins should not normally receive task points.
    active_users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).order_by(
        User.display_name
    ).all()

    # Get active tasks only.
    active_tasks = Task.query.filter_by(
        is_active=True
    ).order_by(
        Task.title
    ).all()

    # Populate the user dropdown.
    form.user_id.choices = [
        (user.id, f"{user.avatar_emoji} {user.display_name}")
        for user in active_users
    ]

    # Populate the task dropdown.
    form.task_id.choices = [
        (task.id, f"{task.title} ({format_points(task.total_point_value())})")
        for task in active_tasks
    ]

    # If the form was submitted and is valid, complete the task.
    if form.validate_on_submit():

        # Find the selected user and task.
        user = db.session.get(User, form.user_id.data)
        task = db.session.get(Task, form.task_id.data)

        # Safety check: user and task must exist.
        if not user or not task:
            flash("Selected user or task not found.")
            return redirect(url_for("main.admin_complete_task"))

        # Safety check: user must be an active standard user.
        if user.role != "user" or not user.is_active_account:
            flash("Selected user is not an active standard user.")
            return redirect(url_for("main.admin_complete_task"))

        # Safety check: task must still be active.
        if not task.is_active:
            flash("Selected task is not active.")
            return redirect(url_for("main.admin_complete_task"))

        # Create an approved task completion record.
        completion = TaskCompletion(
            task_id=task.id,
            user_id=user.id,
            status="approved",
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by_id=current_user.id
        )

        # Add the completion first so it receives an ID.
        db.session.add(completion)
        db.session.flush()

    # Calculate awarded points.
        # Hot tasks include their bonus while they are marked hot.
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

        # If the task is one-off, hide it after completion.
        if task.completion_behavior == "hide_after_approval":
            task.is_active = False

        # Notify the user that an admin completed a task for them.
        create_notification(
            user_id=user.id,
            title="Task completed by admin",
            message=f"'{task.title}' was marked complete for you. You earned {format_points(awarded_points)}.",
            notification_type="success"
        )

        # Save the completion, point transaction, and possible task visibility change.
        db.session.commit()

        flash(f"Task completed for {user.display_name}. {format_points(awarded_points)} awarded.")
        return redirect(url_for("main.admin_home"))

    return render_template(
        "admin_complete_task.html",
        form=form,
        active_users=active_users,
        active_tasks=active_tasks
    )
