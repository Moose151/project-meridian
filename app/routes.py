# Import datetime tools so we can record when approvals and reviews happen,
# and so we can create timestamped backup filenames.
from datetime import datetime, timezone

# os lets us build file paths and check whether the database file exists.
import os

# csv and StringIO are used for admin report exports.
import csv
from io import StringIO

# Import Flask helpers.
# Blueprint groups routes together.
# render_template loads HTML templates.
# redirect and url_for move users between pages.
# flash shows short messages to the user.
# send_file lets us send a downloadable file to the browser.
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request, Response

# Import Flask-Login helpers.
# login_user logs a user in.
# logout_user logs a user out.
# login_required protects pages from users who are not logged in.
# current_user represents the currently logged-in user.
from flask_login import login_user, logout_user, login_required, current_user

# Import the database object so we can add, update, and delete records.
from app import db

# Import all forms used by the app.
from app.forms import (
    LoginForm,
    TaskForm,
    RewardForm,
    UserForm,
    EditUserForm,
    ChangePasswordForm,
    PointAdjustmentForm,
    AdminCompleteTaskForm,
    CategoryForm,
    RejectionReasonForm,
    GroupGoalForm,
    GroupGoalContributionForm,
    WishlistRequestForm,
    WishlistApproveForm,
    WishlistAdminItemForm,
    WishlistContributionForm,
    WishlistEditItemForm,
    HouseholdSettingsForm,
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
    GroupGoal,
    GroupGoalContribution,
    WishlistRequest,
    WishlistItem,
    WishlistContribution,
    Badge,
    UserBadge,
    HouseholdSettings,
)


# Create the main blueprint.
# All routes in this file are registered under this blueprint.
bp = Blueprint("main", __name__)


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

def get_household_settings():
    """
    Return the household settings row.

    If it does not exist, create it with defaults.
    """

    settings = HouseholdSettings.query.first()

    if not settings:

        settings = HouseholdSettings(
            household_name="Project Meridian",
            points_label="points",
            wishlist_requests_enabled=True,
            group_goals_enabled=True
        )

        db.session.add(settings)
        db.session.commit()

    return settings

def make_csv_response(filename, rows):
    """
    Create a downloadable CSV response.

    rows should be a list of lists.
    The first row should normally be the header row.
    """

    output = StringIO()
    writer = csv.writer(output)

    for row in rows:
        writer.writerow(row)

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response

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

@bp.app_context_processor
def inject_household_settings():
    """
    Make household settings available to all templates.
    """

    settings = get_household_settings()

    return {
        "household_settings": settings
    }

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

# =========================================================
# BADGE HELPERS
# =========================================================

def seed_badges():
    """
    Create default badges if they do not already exist.
    """

    default_badges = [
        {
            "code": "first_task",
            "name": "First Task",
            "description": "Completed your first approved task.",
            "icon": "✅"
        },
        {
            "code": "five_tasks",
            "name": "Task Starter",
            "description": "Completed 5 approved tasks.",
            "icon": "⭐"
        },
        {
            "code": "ten_tasks",
            "name": "Task Champion",
            "description": "Completed 10 approved tasks.",
            "icon": "🏆"
        },
        {
            "code": "wishlist_saver",
            "name": "Wishlist Saver",
            "description": "Saved points toward a wishlist item.",
            "icon": "🎁"
        },
        {
            "code": "wishlist_funded",
            "name": "Goal Reached",
            "description": "Fully funded a wishlist item.",
            "icon": "🎯"
        },
        {
            "code": "group_contributor",
            "name": "Team Player",
            "description": "Contributed points to a group goal.",
            "icon": "🤝"
        },
        {
            "code": "hundred_points_earned",
            "name": "Big Earner",
            "description": "Earned 100 total points from approved tasks.",
            "icon": "💰"
        },
    ]

    for badge_data in default_badges:

        existing_badge = Badge.query.filter_by(
            code=badge_data["code"]
        ).first()

        if not existing_badge:

            badge = Badge(
                code=badge_data["code"],
                name=badge_data["name"],
                description=badge_data["description"],
                icon=badge_data["icon"]
            )

            db.session.add(badge)


def award_badge(user_id, badge_code):
    """
    Award a badge to a user if they do not already have it.
    """

    badge = Badge.query.filter_by(
        code=badge_code
    ).first()

    if not badge:
        return

    existing_user_badge = UserBadge.query.filter_by(
        user_id=user_id,
        badge_id=badge.id
    ).first()

    if existing_user_badge:
        return

    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge.id
    )

    db.session.add(user_badge)

    create_notification(
        user_id=user_id,
        title="Badge earned",
        message=f"You earned the '{badge.name}' badge.",
        notification_type="success",
        action_url=url_for("main.my_profile"),
        action_label="View Profile"
    )


def check_and_award_badges(user):
    """
    Check badge rules for a user and award any badges they have earned.

    This function does not commit.
    The calling route should commit after calling it.
    """

    seed_badges()

    approved_task_count = TaskCompletion.query.filter_by(
        user_id=user.id,
        status="approved"
    ).count()

    if approved_task_count >= 1:
        award_badge(user.id, "first_task")

    if approved_task_count >= 5:
        award_badge(user.id, "five_tasks")

    if approved_task_count >= 10:
        award_badge(user.id, "ten_tasks")

    wishlist_contribution_count = WishlistContribution.query.filter_by(
        user_id=user.id,
        status="active"
    ).count()

    if wishlist_contribution_count >= 1:
        award_badge(user.id, "wishlist_saver")

    funded_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="funded"
    ).count()

    fulfilled_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="fulfilled"
    ).count()

    if funded_wishlist_count + fulfilled_wishlist_count >= 1:
        award_badge(user.id, "wishlist_funded")

    group_contribution_count = GroupGoalContribution.query.filter_by(
        user_id=user.id,
        status="active"
    ).count()

    if group_contribution_count >= 1:
        award_badge(user.id, "group_contributor")

    total_earned = 0

    for transaction in user.point_transactions:
        if transaction.transaction_type == "task_approved" and transaction.amount > 0:
            total_earned += transaction.amount

    if total_earned >= 100:
        award_badge(user.id, "hundred_points_earned")

# =========================================================
# BASIC ROUTES: HOME, LOGIN, LOGOUT, DASHBOARD
# =========================================================

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

    Instead of typing a username:
    - user selects their avatar
    - user enters their PIN/password
    - app logs in the selected user if the PIN/password is correct
    """

    # If someone already logged in visits /login, send them to dashboard.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Create the login form.
    form = LoginForm()

    # Get active users to display as avatar cards.
    active_users = User.query.filter_by(
        is_active_account=True
    ).order_by(
        User.role,
        User.display_name
    ).all()

    # If the form was submitted and passed validation, process login.
    if form.validate_on_submit():

        # selected_user_id is stored as text in the hidden field.
        # Convert it to an integer safely.
        try:
            selected_user_id = int(form.selected_user_id.data)
        except ValueError:
            flash("Please select a user.")
            return render_template(
                "login.html",
                form=form,
                users=active_users
            )

        # Look up the selected user.
        user = db.session.get(User, selected_user_id)

        # Stop if the selected user does not exist.
        if not user:
            flash("Selected user not found.")
            return render_template(
                "login.html",
                form=form,
                users=active_users
            )

        # Disabled users should not be able to log in.
        if not user.is_active_account:
            flash("This account has been disabled.")
            return render_template(
                "login.html",
                form=form,
                users=active_users
            )

        # Check PIN/password.
        if user.check_password(form.password.data):
            login_user(user)
            flash("Logged in successfully.")
            return redirect(url_for("main.dashboard"))

        # Wrong PIN/password.
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

    Clears the current login session.
    """

    logout_user()
    flash("Logged out.")
    return redirect(url_for("main.login"))

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
        settings.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        flash("Household settings updated.")
        return redirect(url_for("main.household_settings"))

    return render_template(
        "household_settings.html",
        form=form,
        settings=settings
    )

@bp.route("/admin/reports")
@login_required
def admin_reports():
    """
    Admin-only reports page.

    Provides CSV exports for users, point history, task activity, and reward requests.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    return render_template("admin_reports.html")

@bp.route("/admin/reports/users.csv")
@login_required
def export_users_csv():
    """
    Export user summary data as CSV.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    rows = [
        [
            "User ID",
            "Username",
            "Display Name",
            "Role",
            "Active",
            "Current Balance",
            "Total Earned",
            "Approved Tasks",
            "Reward Requests",
            "Wishlist Saved"
        ]
    ]

    users = User.query.order_by(
        User.display_name
    ).all()

    for user in users:

        total_earned = 0

        for transaction in user.point_transactions:
            if transaction.transaction_type == "task_approved" and transaction.amount > 0:
                total_earned += transaction.amount

        approved_tasks = TaskCompletion.query.filter_by(
            user_id=user.id,
            status="approved"
        ).count()

        reward_requests = RewardPurchase.query.filter_by(
            user_id=user.id
        ).count()

        active_wishlist_items = WishlistItem.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()

        wishlist_saved = 0

        for item in active_wishlist_items:
            wishlist_saved += item.total_saved()

        rows.append(
            [
                user.id,
                user.username,
                user.display_name,
                user.role,
                user.is_active_account,
                user.point_balance(),
                total_earned,
                approved_tasks,
                reward_requests,
                wishlist_saved
            ]
        )

    return make_csv_response(
        "meridian_users_report.csv",
        rows
    )

@bp.route("/admin/reports/points.csv")
@login_required
def export_points_csv():
    """
    Export the full point transaction ledger as CSV.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    rows = [
        [
            "Transaction ID",
            "Date",
            "User",
            "Username",
            "Amount",
            "Transaction Type",
            "Reason",
            "Created By"
        ]
    ]

    transactions = PointTransaction.query.order_by(
        PointTransaction.created_at.desc()
    ).all()

    for transaction in transactions:

        user_name = ""
        username = ""
        created_by_name = ""

        if transaction.user:
            user_name = transaction.user.display_name
            username = transaction.user.username

        if transaction.created_by:
            created_by_name = transaction.created_by.display_name

        rows.append(
            [
                transaction.id,
                transaction.created_at,
                user_name,
                username,
                transaction.amount,
                transaction.transaction_type,
                transaction.reason,
                created_by_name
            ]
        )

    return make_csv_response(
        "meridian_point_history.csv",
        rows
    )

@bp.route("/admin/reports/tasks.csv")
@login_required
def export_tasks_csv():
    """
    Export task completion activity as CSV.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    rows = [
        [
            "Completion ID",
            "User",
            "Username",
            "Task",
            "Category",
            "Status",
            "Task Value",
            "Submitted At",
            "Reviewed At",
            "Reviewed By",
            "Rejection Reason"
        ]
    ]

    completions = TaskCompletion.query.order_by(
        TaskCompletion.submitted_at.desc()
    ).all()

    for completion in completions:

        user_name = ""
        username = ""
        task_title = ""
        task_category = ""
        task_value = ""
        reviewed_by_name = ""

        if completion.user:
            user_name = completion.user.display_name
            username = completion.user.username

        if completion.task:
            task_title = completion.task.title
            task_category = completion.task.category or ""
            task_value = completion.task.point_value

        if completion.reviewed_by:
            reviewed_by_name = completion.reviewed_by.display_name

        rows.append(
            [
                completion.id,
                user_name,
                username,
                task_title,
                task_category,
                completion.status,
                task_value,
                completion.submitted_at,
                completion.reviewed_at,
                reviewed_by_name,
                completion.rejection_reason or ""
            ]
        )

    return make_csv_response(
        "meridian_task_activity.csv",
        rows
    )

@bp.route("/admin/reports/rewards.csv")
@login_required
def export_rewards_csv():
    """
    Export reward request activity as CSV.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    rows = [
        [
            "Purchase ID",
            "User",
            "Username",
            "Reward",
            "Category",
            "Status",
            "Cost",
            "Requested At",
            "Reviewed At",
            "Reviewed By",
            "Rejection Reason"
        ]
    ]

    purchases = RewardPurchase.query.order_by(
        RewardPurchase.requested_at.desc()
    ).all()

    for purchase in purchases:

        user_name = ""
        username = ""
        reward_name = ""
        reward_category = ""
        reward_cost = ""
        reviewed_by_name = ""

        if purchase.user:
            user_name = purchase.user.display_name
            username = purchase.user.username

        if purchase.reward:
            reward_name = purchase.reward.name
            reward_category = purchase.reward.category or ""
            reward_cost = purchase.reward.point_cost

        if purchase.reviewed_by:
            reviewed_by_name = purchase.reviewed_by.display_name

        rows.append(
            [
                purchase.id,
                user_name,
                username,
                reward_name,
                reward_category,
                purchase.status,
                reward_cost,
                purchase.requested_at,
                purchase.reviewed_at,
                reviewed_by_name,
                purchase.rejection_reason or ""
            ]
        )

    return make_csv_response(
        "meridian_reward_requests.csv",
        rows
    )


@bp.route("/dashboard")
@login_required
def dashboard():
    """
    Dashboard route.

    The dashboard is the main overview page after login.

    Admin users see:
    - pending task approvals
    - pending reward requests
    - active standard user count
    - quick admin links

    Standard users see:
    - current point balance
    - pending task submissions
    - pending reward requests
    - available task count
    - affordable reward count
    - quick user links
    """

    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================
    if current_user.is_admin():

        # Get all task submissions waiting for admin approval.
        pending_tasks = TaskCompletion.query.filter_by(
            status="submitted"
        ).all()

        # Get all reward purchase requests waiting for admin approval.
        pending_purchases = RewardPurchase.query.filter_by(
            status="requested"
        ).all()

        # Count active standard users.
        # Admin users are not included in this count.
        active_user_count = User.query.filter_by(
            role="user",
            is_active_account=True
        ).count()

        # Get unread dashboard notifications for this admin.
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(
            Notification.created_at.desc()
        ).all()

                # Recent system-wide point activity for admin dashboard.
        recent_activity = PointTransaction.query.order_by(
            PointTransaction.created_at.desc()
        ).limit(8).all()

        # Send admin dashboard data to the template.
        return render_template(
            "dashboard.html",
            pending_tasks=pending_tasks,
            pending_purchases=pending_purchases,
            active_user_count=active_user_count,
            notifications=notifications,
            recent_activity=recent_activity
        )

    # =====================================================
    # STANDARD USER DASHBOARD
    # =====================================================

    # Get this user's submitted tasks waiting for admin approval.
    pending_user_tasks = TaskCompletion.query.filter_by(
        user_id=current_user.id,
        status="submitted"
    ).all()

    # Get this user's reward requests waiting for admin approval.
    pending_user_purchases = RewardPurchase.query.filter_by(
        user_id=current_user.id,
        status="requested"
    ).all()

    # Count all currently active tasks.
    available_task_count = Task.query.filter_by(
        is_active=True
    ).count()

    # Get the user's current point balance.
    current_balance = current_user.point_balance()

        # Count this user's active wishlist items.
    wishlist_item_count = WishlistItem.query.filter(
        WishlistItem.user_id == current_user.id,
        WishlistItem.status.in_(["active", "funded"]),
        WishlistItem.is_active == True
    ).count()

    # Count funded wishlist items waiting for admin fulfilment.
    funded_wishlist_count = WishlistItem.query.filter_by(
        user_id=current_user.id,
        status="funded"
    ).count()

    # Count total points saved across active wishlist items.
    active_wishlist_items = WishlistItem.query.filter(
        WishlistItem.user_id == current_user.id,
        WishlistItem.status.in_(["active", "funded"]),
        WishlistItem.is_active == True
    ).all()

    wishlist_points_saved = 0

    for item in active_wishlist_items:
        wishlist_points_saved += item.total_saved()

    # Count rewards the user can currently afford.
    affordable_reward_count = Reward.query.filter(
        Reward.is_active == True,
        Reward.point_cost <= current_balance
    ).count()

    # Get unread dashboard notifications for this user.
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(
        Notification.created_at.desc()
    ).all()

        # Recent point activity for this user.
    recent_activity = PointTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        PointTransaction.created_at.desc()
    ).limit(6).all()

    # Send standard user dashboard data to the template.
    return render_template(
        "dashboard.html",
        pending_user_tasks=pending_user_tasks,
        pending_user_purchases=pending_user_purchases,
        available_task_count=available_task_count,
        affordable_reward_count=affordable_reward_count,
        current_balance=current_balance,
        notifications=notifications,
        wishlist_item_count=wishlist_item_count,
        funded_wishlist_count=funded_wishlist_count,
        wishlist_points_saved=wishlist_points_saved,
        recent_activity=recent_activity
    )


# =========================================================
# TASKS: CREATE, VIEW, SUBMIT
# =========================================================

@bp.route("/tasks")
@login_required
def tasks():
    """
    Task board page.

    Shows active tasks only.

    Optional filter:
    - category
    """

    # Get selected category from the URL query string.
    selected_category = request.args.get("category", "")

    # Start with active tasks only.
    task_query = Task.query.filter_by(
        is_active=True
    )

    # Apply category filter if one is selected.
    if selected_category:
        task_query = task_query.filter_by(
            category=selected_category
        )

    # Get the filtered task list.
    active_tasks = task_query.order_by(
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
        selected_category=selected_category
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
            is_active=True
        )

        db.session.add(task)
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
    pending_tasks = TaskCompletion.query.filter_by(status="submitted").all()

    # Get reward purchase requests waiting for review.
    pending_purchases = RewardPurchase.query.filter_by(status="requested").all()

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

    When approved:
    - TaskCompletion status becomes approved.
    - A positive PointTransaction is created.
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

    # Mark as approved.
    completion.status = "approved"
    completion.reviewed_at = datetime.now(timezone.utc)
    completion.reviewed_by_id = current_user.id

    # Create a point transaction to award points.
    transaction = PointTransaction(
        user_id=completion.user_id,
        amount=completion.task.point_value,
        transaction_type="task_approved",
        reason=f"Approved task: {completion.task.title}",
        related_task_completion_id=completion.id,
        created_by_id=current_user.id
    )

        # Add the point transaction.
    db.session.add(transaction)

    # If this task is set to hide after approval,
    # hide it from the normal task board now.
    if completion.task.completion_behavior == "hide_after_approval":
        completion.task.is_active = False

    # Notify the user that the task was approved.
    create_notification(
        user_id=completion.user_id,
        title="Task approved",
        message=f"Your task '{completion.task.title}' was approved. You earned {completion.task.point_value} points.",
        notification_type="success"
    )

    # Check whether this approval earned the user any badges.
    check_and_award_badges(completion.user)
    # Save approval, transaction, and possible task visibility change.
    db.session.commit()

    flash("Task approved and points awarded.")
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

    Current behaviour:
    - Points are already reserved when the user requests the reward.
    - Approval does not create another negative transaction.
    - Approval simply marks the request as approved.

    Legacy safety:
    - If an old pending request exists from before point reservation was added,
      and therefore has no reward_requested transaction, this route will deduct
      points at approval time as a fallback.
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

    # Check whether this purchase already has a reservation transaction.
    reservation = PointTransaction.query.filter_by(
        related_reward_purchase_id=purchase.id,
        transaction_type="reward_requested"
    ).first()

    # Legacy fallback:
    # If there is no reservation, this request was probably created before
    # point reservation was added. In that case, check balance and deduct now.
    if not reservation:

        if purchase.user.point_balance() < purchase.reward.point_cost:
            flash("User no longer has enough points for this reward.")
            return redirect(url_for("main.admin_approvals"))

        fallback_transaction = PointTransaction(
            user_id=purchase.user_id,
            amount=-purchase.reward.point_cost,
            transaction_type="reward_approved",
            reason=f"Approved reward: {purchase.reward.name}",
            related_reward_purchase_id=purchase.id,
            created_by_id=current_user.id
        )

        db.session.add(fallback_transaction)

    # Mark purchase as approved.
    purchase.status = "approved"
    purchase.reviewed_at = datetime.now(timezone.utc)
    purchase.reviewed_by_id = current_user.id

    # Notify the user that the reward was approved.
    # This must be outside the legacy fallback block so it happens for all approvals.
    create_notification(
        user_id=purchase.user_id,
        title="Reward approved",
        message=f"Your reward request '{purchase.reward.name}' was approved.",
        notification_type="success"
    )

    # Save approval, possible fallback transaction, and notification.
    db.session.commit()

    flash("Reward approved.")
    return redirect(url_for("main.admin_approvals"))


@bp.route("/admin/rewards/<int:purchase_id>/reject", methods=["GET", "POST"])
@login_required
def reject_reward_purchase(purchase_id):
    """
    Reject a requested reward purchase.

    New behaviour:
    - Admin is shown a rejection form.
    - Admin must enter a short rejection reason.
    - If points were reserved, they are refunded.
    - Reason appears in Reward History.
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

        # Look for the original point reservation.
        reservation = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_requested"
        ).first()

        # Check whether a refund already exists.
        # This prevents accidental double refunds.
        existing_refund = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_refunded"
        ).first()

        # If points were reserved and have not already been refunded,
        # create a positive transaction to return the points.
        if reservation and not existing_refund:
            refund = PointTransaction(
                user_id=purchase.user_id,
                amount=purchase.reward.point_cost,
                transaction_type="reward_refunded",
                reason=f"Refunded rejected reward: {purchase.reward.name}",
                related_reward_purchase_id=purchase.id,
                created_by_id=current_user.id
            )

            db.session.add(refund)

        # Mark purchase as rejected.
        purchase.status = "rejected"
        purchase.reviewed_at = datetime.now(timezone.utc)
        purchase.reviewed_by_id = current_user.id
        purchase.rejection_reason = form.reason.data.strip()

        # Notify the user that the reward was rejected.
        create_notification(
            user_id=purchase.user_id,
            title="Reward rejected",
            message=f"Your reward request '{purchase.reward.name}' was rejected. Reason: {purchase.rejection_reason}. Reserved points were refunded.",
            notification_type="danger"
        )

        db.session.commit()

        flash("Reward request rejected and reserved points refunded.")
        return redirect(url_for("main.admin_approvals"))

    # Show rejection reason form.
    return render_template(
        "reject_reward_purchase.html",
        form=form,
        purchase=purchase
    )


# =========================================================
# POINT HISTORY
# =========================================================

@bp.route("/points")
@login_required
def point_history():
    """
    Point history page.

    Admins see all point transactions.
    Standard users only see their own transactions.
    """

    if current_user.is_admin():

        # Admins see all transactions.
        transactions = PointTransaction.query.order_by(
            PointTransaction.created_at.desc()
        ).all()

    else:

        # Standard users only see their own transactions.
        transactions = PointTransaction.query.filter_by(
            user_id=current_user.id
        ).order_by(
            PointTransaction.created_at.desc()
        ).all()

    return render_template(
        "point_history.html",
        transactions=transactions
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
        flash("You do not have enough points for this reward.")
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
    transaction = PointTransaction(
        user_id=current_user.id,
        amount=-reward.point_cost,
        transaction_type="reward_requested",
        reason=f"Requested reward: {reward.name}",
        related_reward_purchase_id=purchase.id,
        created_by_id=current_user.id
    )

    # Save the point reservation.
    db.session.add(transaction)

    # Commit both:
    # - the reward purchase request
    # - the point reservation transaction
    db.session.commit()

    flash("Reward requested. Points have been reserved pending approval.")
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

        flash("Point adjustment applied.")
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
# BACKUP / EXPORT
# =========================================================

@bp.route("/admin/backup")
@login_required
def backup_database():
    """
    Admin-only database backup route.

    This sends the SQLite database file to the browser as a download.

    The database file contains:
    - users
    - tasks
    - task completions
    - rewards
    - reward purchases
    - point transactions

    For this local MVP, downloading the SQLite file is the simplest backup method.
    """

    # Block non-admin users from downloading the database.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Build the path to the SQLite database.
    # app.root_path points to the /app folder, so we move one folder up
    # to the project folder, then into /instance/meridian.db.
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "instance",
        "meridian.db"
    )

    # If the database file does not exist, show an error instead of crashing.
    if not os.path.exists(db_path):
        flash("Database file not found.")
        return redirect(url_for("main.dashboard"))

    # Create a timestamp for the backup filename.
    # Example: 20260529-231500
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Create the filename the browser will download.
    backup_filename = f"project-meridian-backup-{timestamp}.db"

    # Send the database file to the browser as a downloadable attachment.
    return send_file(
        db_path,
        as_attachment=True,
        download_name=backup_filename
    )


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
    

                # Update task fields from the form.
        task.title = form.title.data
        task.description = form.description.data
        task.point_value = form.point_value.data
        task.category = form.category.data or None
        task.completion_behavior = form.completion_behavior.data

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
# TASK AND REWARD HISTORY
# =========================================================

@bp.route("/history/tasks")
@login_required
def task_history():
    """
    Task history page.

    Admin users:
    - See all task completion records for all users.

    Standard users:
    - See only their own task completion records.

    This helps users and admins review:
    - submitted tasks
    - approved tasks
    - rejected tasks
    """

    # Admins see all task completion records.
    if current_user.is_admin():
        completions = TaskCompletion.query.order_by(
            TaskCompletion.submitted_at.desc()
        ).all()

    # Standard users only see their own task completion records.
    else:
        completions = TaskCompletion.query.filter_by(
            user_id=current_user.id
        ).order_by(
            TaskCompletion.submitted_at.desc()
        ).all()

    # Send the records to the template.
    return render_template(
        "task_history.html",
        completions=completions
    )


@bp.route("/history/rewards")
@login_required
def reward_history():
    """
    Reward history page.

    Admin users:
    - See all reward purchase records for all users.

    Standard users:
    - See only their own reward purchase records.

    This helps users and admins review:
    - requested rewards
    - approved rewards
    - rejected rewards
    """

    # Admins see all reward purchase records.
    if current_user.is_admin():
        purchases = RewardPurchase.query.order_by(
            RewardPurchase.requested_at.desc()
        ).all()

    # Standard users only see their own reward purchase records.
    else:
        purchases = RewardPurchase.query.filter_by(
            user_id=current_user.id
        ).order_by(
            RewardPurchase.requested_at.desc()
        ).all()

    # Send the records to the template.
    return render_template(
        "reward_history.html",
        purchases=purchases
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

    flash("Reward request cancelled and reserved points refunded.")
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
        (task.id, f"{task.title} ({task.point_value} points)")
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

        # Create a point transaction for the selected user.
        transaction = PointTransaction(
            user_id=user.id,
            amount=task.point_value,
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
            message=f"'{task.title}' was marked complete for you. You earned {task.point_value} points.",
            notification_type="success"
        )

        # Save the completion, point transaction, and possible task visibility change.
        db.session.commit()

        flash(f"Task completed for {user.display_name}. Points awarded.")
        return redirect(url_for("main.admin_home"))

    return render_template(
        "admin_complete_task.html",
        form=form,
        active_users=active_users,
        active_tasks=active_tasks
    )

# =========================================================
# LEADERBOARD
# =========================================================

@bp.route("/leaderboard")
@login_required
def leaderboard():
    """
    Leaderboard page.

    Shows rankings for active standard users.

    Current Points:
    - calculated from the user's current point balance

    Total Points Earned:
    - calculated from positive task_approved transactions only
    - spending points does not reduce this score

    Tasks Completed:
    - calculated from approved task completion records
    """

    # Get active standard users only.
    users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).order_by(
        User.display_name
    ).all()

    # -----------------------------------------------------
    # Current points leaderboard
    # -----------------------------------------------------

    current_points_leaderboard = []

    for user in users:
        current_points_leaderboard.append({
            "user": user,
            "score": user.point_balance()
        })

    current_points_leaderboard = sorted(
        current_points_leaderboard,
        key=lambda item: item["score"],
        reverse=True
    )

    # -----------------------------------------------------
    # Total points earned leaderboard
    # -----------------------------------------------------

    total_earned_leaderboard = []

    for user in users:

        # Count positive earning transactions.
        # This includes approved tasks and positive admin adjustments.
        # Spending, saving, refunds, and negative adjustments do not reduce this score.
        total_earned = 0

        earning_transaction_types = [
            "task_approved",
            "manual_adjustment",
            "admin_adjustment",
            "point_adjustment"
        ]

        for transaction in user.point_transactions:
            if (
                transaction.transaction_type in earning_transaction_types
                and transaction.amount > 0
            ):
                total_earned += transaction.amount

        total_earned_leaderboard.append({
            "user": user,
            "score": total_earned
        })

    total_earned_leaderboard = sorted(
        total_earned_leaderboard,
        key=lambda item: item["score"],
        reverse=True
    )

    # -----------------------------------------------------
    # Tasks completed leaderboard
    # -----------------------------------------------------

    tasks_completed_leaderboard = []

    for user in users:

        approved_task_count = TaskCompletion.query.filter_by(
            user_id=user.id,
            status="approved"
        ).count()

        tasks_completed_leaderboard.append({
            "user": user,
            "score": approved_task_count
        })

    tasks_completed_leaderboard = sorted(
        tasks_completed_leaderboard,
        key=lambda item: item["score"],
        reverse=True
    )

    return render_template(
        "leaderboard.html",
        current_points_leaderboard=current_points_leaderboard,
        total_earned_leaderboard=total_earned_leaderboard,
        tasks_completed_leaderboard=tasks_completed_leaderboard
    )

# =========================================================
# CATEGORY MANAGEMENT
# =========================================================

@bp.route("/admin/categories")
@login_required
def manage_categories():
    """
    Admin-only category management page.

    Admins can manage:
    - task categories
    - reward categories
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

    This does not erase old tasks using that category.
    It only hides the category from future selection/filter lists.
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

    This does not erase old rewards using that category.
    It only hides the category from future selection/filter lists.
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

# =========================================================
# USER NOTIFICATIONS
# =========================================================

@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    """
    Mark a dashboard notification as read/dismissed.

    Users can only dismiss their own notifications.
    """

    notification = db.session.get(Notification, notification_id)

    if not notification:
        flash("Notification not found.")
        return redirect(url_for("main.dashboard"))

    if notification.user_id != current_user.id:
        flash("You can only dismiss your own notifications.")
        return redirect(url_for("main.dashboard"))

    notification.is_read = True
    db.session.commit()

    flash("Notification dismissed.")
    return redirect(url_for("main.dashboard"))

# =========================================================
# USER PROFILES
# =========================================================

@bp.route("/profile")
@login_required
def my_profile():
    """
    Redirect the current user to the full user profile page.

    This avoids having two separate profile implementations.
    """

    return redirect(
        url_for(
            "main.user_profile",
            user_id=current_user.id
        )
    )


@bp.route("/users/<int:user_id>/profile")
@login_required
def user_profile(user_id):
    """
    User profile page.

    Standard users:
    - can only view their own profile.

    Admin users:
    - can view any user's profile.

    The profile shows:
    - point summary
    - task summary
    - reward summary
    - group goal activity
    - wishlist activity
    - recent transactions
    """

    # Find the requested user.
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.")
        return redirect(url_for("main.dashboard"))

    # Standard users can only view their own profile.
    if not current_user.is_admin() and current_user.id != user.id:
        flash("You can only view your own profile.")
        return redirect(url_for("main.dashboard"))

    # -----------------------------------------------------
    # Core profile summary statistics
    # -----------------------------------------------------

    # Current point balance comes from the point transaction ledger.
    current_points = user.point_balance()

    # Total earned only counts approved task point transactions.
    # This means users are not penalised for spending points.
    total_earned = 0

    earning_transaction_types = [
        "task_approved",
        "manual_adjustment",
        "admin_adjustment",
        "point_adjustment"
    ]

    for transaction in user.point_transactions:
        if (
            transaction.transaction_type in earning_transaction_types
            and transaction.amount > 0
        ):
            total_earned += transaction.amount

    # Count approved task completions.
    tasks_completed = TaskCompletion.query.filter_by(
        user_id=user.id,
        status="approved"
    ).count()

    # Count all reward requests made by this user.
    rewards_requested = RewardPurchase.query.filter_by(
        user_id=user.id
    ).count()

    # Count approved reward requests.
    rewards_approved = RewardPurchase.query.filter_by(
        user_id=user.id,
        status="approved"
    ).count()

    # -----------------------------------------------------
    # Group goal summary statistics
    # -----------------------------------------------------

    # Count active group goal contributions.
    active_group_contributions = GroupGoalContribution.query.filter_by(
        user_id=user.id,
        status="active"
    ).all()

    # Total points contributed to active group goals.
    total_group_contributed = 0

    for contribution in active_group_contributions:
        total_group_contributed += contribution.amount

    # Count how many active group goal contribution records this user has.
    active_group_goal_count = len(active_group_contributions)

    # -----------------------------------------------------
    # Wishlist summary statistics
    # -----------------------------------------------------

    # Get active wishlist items for this user.
    active_wishlist_items = WishlistItem.query.filter_by(
        user_id=user.id,
        is_active=True
    ).all()

    # Count active wishlist items.
    wishlist_item_count = len(active_wishlist_items)

    # Count wishlist items that are fully funded but not yet fulfilled.
    funded_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="funded"
    ).count()

    # Count fulfilled wishlist items.
    fulfilled_wishlist_count = WishlistItem.query.filter_by(
        user_id=user.id,
        status="fulfilled"
    ).count()

    # Count saved points across active wishlist items.
    wishlist_points_saved = 0

    for item in active_wishlist_items:
        wishlist_points_saved += item.total_saved()

    # Count all wishlist requests made by this user.
    wishlist_request_count = WishlistRequest.query.filter_by(
        user_id=user.id
    ).count()

    # -----------------------------------------------------
    # Recent activity
    # -----------------------------------------------------

    # Recent task completions.
    recent_task_completions = TaskCompletion.query.filter_by(
        user_id=user.id
    ).order_by(
        TaskCompletion.submitted_at.desc()
    ).limit(5).all()

    # Recent reward purchases.
    recent_reward_purchases = RewardPurchase.query.filter_by(
        user_id=user.id
    ).order_by(
        RewardPurchase.requested_at.desc()
    ).limit(5).all()

    # Recent point transactions.
    recent_point_transactions = PointTransaction.query.filter_by(
        user_id=user.id
    ).order_by(
        PointTransaction.created_at.desc()
    ).limit(5).all()

    # Recent group goal contributions.
    recent_group_contributions = GroupGoalContribution.query.filter_by(
        user_id=user.id
    ).order_by(
        GroupGoalContribution.created_at.desc()
    ).limit(5).all()

    # Recent wishlist items.
    recent_wishlist_items = WishlistItem.query.filter_by(
        user_id=user.id
    ).order_by(
        WishlistItem.created_at.desc()
    ).limit(5).all()

    # Recent wishlist requests.
    recent_wishlist_requests = WishlistRequest.query.filter_by(
        user_id=user.id
    ).order_by(
        WishlistRequest.created_at.desc()
    ).limit(5).all()

    # Recent wishlist contributions.
    recent_wishlist_contributions = WishlistContribution.query.filter_by(
        user_id=user.id
    ).order_by(
        WishlistContribution.created_at.desc()
    ).limit(5).all()

        # Make sure badges are up to date when viewing the profile.
    check_and_award_badges(user)
    db.session.commit()

    earned_badges = UserBadge.query.filter_by(
        user_id=user.id
    ).order_by(
        UserBadge.earned_at.desc()
    ).all()
    # Load badges earned by this user.
    earned_badges = UserBadge.query.filter_by(
        user_id=user.id
    ).order_by(
        UserBadge.earned_at.desc()
    ).all()
    return render_template(
        "user_profile.html",
        user=user,
        current_points=current_points,
        total_earned=total_earned,
        tasks_completed=tasks_completed,
        rewards_requested=rewards_requested,
        rewards_approved=rewards_approved,
        total_group_contributed=total_group_contributed,
        active_group_goal_count=active_group_goal_count,
        wishlist_item_count=wishlist_item_count,
        funded_wishlist_count=funded_wishlist_count,
        fulfilled_wishlist_count=fulfilled_wishlist_count,
        wishlist_points_saved=wishlist_points_saved,
        wishlist_request_count=wishlist_request_count,
        recent_task_completions=recent_task_completions,
        recent_reward_purchases=recent_reward_purchases,
        recent_point_transactions=recent_point_transactions,
        recent_group_contributions=recent_group_contributions,
        recent_wishlist_items=recent_wishlist_items,
        recent_wishlist_requests=recent_wishlist_requests,
        recent_wishlist_contributions=recent_wishlist_contributions,
        earned_badges=earned_badges,
    )

# =========================================================
# GROUP GOALS
# =========================================================

@bp.route("/group-goals")
@login_required
def group_goals():
    """
    Show active and completed group goals.

    Standard users can contribute to active goals.
    Admins can create, fulfil, or cancel goals.
    """

    active_goals = GroupGoal.query.filter_by(
        is_active=True
    ).order_by(
        GroupGoal.created_at.desc()
    ).all()

    return render_template(
        "group_goals.html",
        goals=active_goals
    )


@bp.route("/group-goals/create", methods=["GET", "POST"])
@login_required
def create_group_goal():
    """
    Admin-only page for creating a group goal.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    form = GroupGoalForm()

    if form.validate_on_submit():

        goal = GroupGoal(
            title=form.title.data,
            description=form.description.data,
            target_points=form.target_points.data,
            status="active",
            is_active=True
        )

        db.session.add(goal)
        db.session.commit()

        flash("Group goal created.")
        return redirect(url_for("main.group_goals"))

    return render_template(
        "create_group_goal.html",
        form=form
    )


@bp.route("/group-goals/<int:goal_id>/contribute", methods=["GET", "POST"])
@login_required
def contribute_group_goal(goal_id):
    """
    Allow a standard user to contribute points to a group goal.

    Points are deducted immediately and stored in the point ledger.
    """

    if current_user.is_admin():
        flash("Admins do not contribute points to group goals.")
        return redirect(url_for("main.group_goals"))

    settings = get_household_settings()

    if not settings.group_goals_enabled:
        flash("Group goal contributions are currently disabled.")
        return redirect(url_for("main.group_goals"))

    goal = db.session.get(GroupGoal, goal_id)

    if not goal or not goal.is_active or goal.status != "active":
        flash("Group goal not found.")
        return redirect(url_for("main.group_goals"))

    form = GroupGoalContributionForm()

    if form.validate_on_submit():

        amount = form.amount.data

        if amount > current_user.point_balance():
            flash("You do not have enough points to contribute that amount.")
            return redirect(url_for("main.contribute_group_goal", goal_id=goal.id))

        if amount > goal.remaining_points():
            flash(f"This goal only needs {goal.remaining_points()} more point(s).")
            return redirect(url_for("main.contribute_group_goal", goal_id=goal.id))

        contribution = GroupGoalContribution(
            goal_id=goal.id,
            user_id=current_user.id,
            amount=amount,
            status="active"
        )

        db.session.add(contribution)
        db.session.flush()

        transaction = PointTransaction(
            user_id=current_user.id,
            amount=-amount,
            transaction_type="group_goal_contribution",
            reason=f"Contributed to group goal: {goal.title}",
            created_by_id=current_user.id
        )

        db.session.add(transaction)

        if goal.is_funded():
            goal.status = "completed"

            notify_admins(
                title="Group goal funded",
                message=f"The group goal '{goal.title}' has reached its point target and is ready for fulfilment.",
                notification_type="success",
                action_url=url_for("main.group_goals"),
                action_label="Open Group Goals"
            )
        # Check whether this group goal contribution earned the user any badges.
        check_and_award_badges(current_user)
        db.session.commit()

        flash("Contribution added.")
        return redirect(url_for("main.group_goals"))

    return render_template(
        "contribute_group_goal.html",
        form=form,
        goal=goal
    )


@bp.route("/group-goals/<int:goal_id>/fulfil", methods=["POST"])
@login_required
def fulfil_group_goal(goal_id):
    """
    Admin-only route for marking a completed group goal as fulfilled.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    goal = db.session.get(GroupGoal, goal_id)

    if not goal or not goal.is_active:
        flash("Group goal not found.")
        return redirect(url_for("main.group_goals"))

    if not goal.is_funded():
        flash("This group goal has not reached its target yet.")
        return redirect(url_for("main.group_goals"))

    goal.status = "fulfilled"

    # Notify all users who contributed.
    contributing_user_ids = set()

    for contribution in goal.contributions:
        if contribution.status == "active":
            contributing_user_ids.add(contribution.user_id)

    for user_id in contributing_user_ids:
        create_notification(
            user_id=user_id,
            title="Group goal fulfilled",
            message=f"The group goal '{goal.title}' has been fulfilled.",
            notification_type="success"
        )

    db.session.commit()

    flash("Group goal marked as fulfilled.")
    return redirect(url_for("main.group_goals"))


@bp.route("/group-goals/<int:goal_id>/cancel", methods=["POST"])
@login_required
def cancel_group_goal(goal_id):
    """
    Admin-only route for cancelling a group goal.

    Active contributions are refunded.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    goal = db.session.get(GroupGoal, goal_id)

    if not goal or not goal.is_active:
        flash("Group goal not found.")
        return redirect(url_for("main.group_goals"))

    if goal.status == "fulfilled":
        flash("Fulfilled goals cannot be cancelled.")
        return redirect(url_for("main.group_goals"))

    for contribution in goal.contributions:

        if contribution.status == "active":

            refund = PointTransaction(
                user_id=contribution.user_id,
                amount=contribution.amount,
                transaction_type="group_goal_refund",
                reason=f"Refunded cancelled group goal: {goal.title}",
                created_by_id=current_user.id
            )

            db.session.add(refund)

            contribution.status = "refunded"

            create_notification(
                user_id=contribution.user_id,
                title="Group goal cancelled",
                message=f"The group goal '{goal.title}' was cancelled. Your contribution was refunded.",
                notification_type="warning"
            )

    goal.status = "cancelled"
    goal.is_active = False

    db.session.commit()

    flash("Group goal cancelled and contributions refunded.")
    return redirect(url_for("main.group_goals"))

# =========================================================
# WISHLIST
# =========================================================

@bp.route("/wishlist")
@login_required
def wishlist():
    """
    Wishlist page.

    Standard users:
    - see their own active/funded wishlist items
    - see their own recent wishlist requests

    Admin users:
    - see all active/funded wishlist items
    - see recent wishlist requests

    Fulfilled and removed wishlist items are kept in the database,
    but hidden from the main Wishlist page so old/test items do not clutter it.
    """

    # Only these wishlist item statuses appear on the main Wishlist page.
    visible_item_statuses = [
        "active",
        "funded"
    ]

    # Wishlist requests are limited so the page does not become too long.
    visible_request_statuses = [
        "requested"
    ]

    if current_user.is_admin():

        # Admins see all active/funded wishlist items for all users.
        wishlist_items = WishlistItem.query.filter(
            WishlistItem.status.in_(visible_item_statuses),
            WishlistItem.is_active == True
        ).order_by(
            WishlistItem.created_at.desc()
        ).all()

        # Admins see recent wishlist requests across all users.
        wishlist_requests = WishlistRequest.query.filter(
            WishlistRequest.status.in_(visible_request_statuses)
        ).order_by(
            WishlistRequest.created_at.desc()
        ).limit(20).all()

    else:

        # Standard users see only their own active/funded wishlist items.
        wishlist_items = WishlistItem.query.filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.status.in_(visible_item_statuses),
            WishlistItem.is_active == True
        ).order_by(
            WishlistItem.created_at.desc()
        ).all()

        # Standard users see only their own recent wishlist requests.
        wishlist_requests = WishlistRequest.query.filter(
            WishlistRequest.user_id == current_user.id,
            WishlistRequest.status.in_(visible_request_statuses)
        ).order_by(
            WishlistRequest.created_at.desc()
        ).limit(10).all()

    return render_template(
        "wishlist.html",
        wishlist_items=wishlist_items,
        wishlist_requests=wishlist_requests
    )


@bp.route("/wishlist/request", methods=["GET", "POST"])
@login_required
def request_wishlist_item():
    """
    Standard-user page for requesting a wishlist item.

    Admins should add wishlist items directly from the admin page.
    """

    if current_user.is_admin():
        flash("Admins can add wishlist items directly.")
        return redirect(url_for("main.admin_add_wishlist_item"))

    form = WishlistRequestForm()

    settings = get_household_settings()

    if not settings.wishlist_requests_enabled:
        flash("Wishlist requests are currently disabled.")
        return redirect(url_for("main.wishlist"))

    if form.validate_on_submit():

        wishlist_request = WishlistRequest(
            user_id=current_user.id,
            requested_name=form.requested_name.data,
            requested_description=form.requested_description.data,
            status="requested"
        )

        db.session.add(wishlist_request)

        # Notify admins that a user has submitted a new wishlist request.
        notify_admins(
            title="New wishlist request",
            message=f"{current_user.display_name} requested '{wishlist_request.requested_name}' to be added to their wishlist.",
            notification_type="info",
            action_url=url_for("main.wishlist"),
            action_label="Review Wishlist"
        )

        db.session.commit()

        flash("Wishlist request submitted.")
        return redirect(url_for("main.wishlist"))

    return render_template(
        "request_wishlist_item.html",
        form=form
    )


@bp.route("/wishlist/requests/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_wishlist_request(request_id):
    """
    Allow a standard user to cancel their own pending wishlist request.
    """

    wishlist_request = db.session.get(WishlistRequest, request_id)

    if not wishlist_request:
        flash("Wishlist request not found.")
        return redirect(url_for("main.wishlist"))

    if wishlist_request.user_id != current_user.id:
        flash("You can only cancel your own wishlist requests.")
        return redirect(url_for("main.wishlist"))

    if wishlist_request.status != "requested":
        flash("Only pending wishlist requests can be cancelled.")
        return redirect(url_for("main.wishlist"))

    wishlist_request.status = "cancelled"
    db.session.commit()

    flash("Wishlist request cancelled.")
    return redirect(url_for("main.wishlist"))


@bp.route("/admin/wishlist/add", methods=["GET", "POST"])
@login_required
def admin_add_wishlist_item():
    """
    Admin-only page for directly adding a wishlist item to a user.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    form = WishlistAdminItemForm()

    active_users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).order_by(
        User.display_name
    ).all()

    form.user_id.choices = [
        (user.id, f"{user.avatar_emoji} {user.display_name}")
        for user in active_users
    ]

    if form.validate_on_submit():

        user = db.session.get(User, form.user_id.data)

        if not user:
            flash("Selected user not found.")
            return redirect(url_for("main.admin_add_wishlist_item"))

        item = WishlistItem(
            user_id=user.id,
            name=form.name.data,
            description=form.description.data,
            point_cost=form.point_cost.data,
            status="active",
            is_active=True,
            created_by_id=current_user.id
        )

        db.session.add(item)

        create_notification(
            user_id=user.id,
            title="Wishlist item added",
            message=f"'{item.name}' was added to your wishlist for {item.point_cost} points.",
            notification_type="success"
        )

        db.session.commit()

        flash("Wishlist item added.")
        return redirect(url_for("main.wishlist"))

    return render_template(
        "admin_add_wishlist_item.html",
        form=form
    )


@bp.route("/admin/wishlist/requests/<int:request_id>/approve", methods=["GET", "POST"])
@login_required
def approve_wishlist_request(request_id):
    """
    Admin-only page for approving a wishlist request.

    Admin sets the final point cost.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    wishlist_request = db.session.get(WishlistRequest, request_id)

    if not wishlist_request or wishlist_request.status != "requested":
        flash("Wishlist request not found.")
        return redirect(url_for("main.wishlist"))

    form = WishlistApproveForm()

    if request.method == "GET":
        form.name.data = wishlist_request.requested_name
        form.description.data = wishlist_request.requested_description

    if form.validate_on_submit():

        item = WishlistItem(
            user_id=wishlist_request.user_id,
            name=form.name.data,
            description=form.description.data,
            point_cost=form.point_cost.data,
            status="active",
            is_active=True,
            created_by_id=current_user.id
        )

        db.session.add(item)

        wishlist_request.status = "approved"
        wishlist_request.reviewed_at = datetime.now(timezone.utc)
        wishlist_request.reviewed_by_id = current_user.id

        create_notification(
            user_id=wishlist_request.user_id,
            title="Wishlist request approved",
            message=f"'{item.name}' was added to your wishlist for {item.point_cost} points.",
            notification_type="success"
        )

        db.session.commit()

        flash("Wishlist request approved and item added.")
        return redirect(url_for("main.wishlist"))

    return render_template(
        "approve_wishlist_request.html",
        form=form,
        wishlist_request=wishlist_request
    )


@bp.route("/admin/wishlist/requests/<int:request_id>/reject", methods=["GET", "POST"])
@login_required
def reject_wishlist_request(request_id):
    """
    Admin-only page for rejecting a wishlist request with a reason.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    wishlist_request = db.session.get(WishlistRequest, request_id)

    if not wishlist_request or wishlist_request.status != "requested":
        flash("Wishlist request not found.")
        return redirect(url_for("main.wishlist"))

    form = RejectionReasonForm()

    if form.validate_on_submit():

        wishlist_request.status = "rejected"
        wishlist_request.rejection_reason = form.reason.data.strip()
        wishlist_request.reviewed_at = datetime.now(timezone.utc)
        wishlist_request.reviewed_by_id = current_user.id

        create_notification(
            user_id=wishlist_request.user_id,
            title="Wishlist request rejected",
            message=f"Your wishlist request '{wishlist_request.requested_name}' was rejected. Reason: {wishlist_request.rejection_reason}",
            notification_type="danger"
        )

        db.session.commit()

        flash("Wishlist request rejected.")
        return redirect(url_for("main.wishlist"))

    return render_template(
        "reject_wishlist_request.html",
        form=form,
        wishlist_request=wishlist_request
    )


@bp.route("/admin/wishlist/items/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_wishlist_item(item_id):
    """
    Admin-only route for removing a wishlist item.

    This archives the item and refunds any active saved contributions.
    """

    if not admin_required():
        return redirect(url_for("main.dashboard"))

    item = db.session.get(WishlistItem, item_id)

    if not item:
        flash("Wishlist item not found.")
        return redirect(url_for("main.wishlist"))

    for contribution in item.contributions:

        if contribution.status == "active":

            refund = PointTransaction(
                user_id=contribution.user_id,
                amount=contribution.amount,
                transaction_type="wishlist_refund",
                reason=f"Refunded removed wishlist item: {item.name}",
                created_by_id=current_user.id
            )

            db.session.add(refund)

            contribution.status = "refunded"

    item.status = "removed"
    item.is_active = False

    create_notification(
        user_id=item.user_id,
        title="Wishlist item removed",
        message=f"'{item.name}' was removed from your wishlist. Any saved points were refunded.",
        notification_type="warning"
    )

    db.session.commit()

    flash("Wishlist item removed and saved points refunded.")
    return redirect(url_for("main.wishlist"))

@bp.route("/wishlist/items/<int:item_id>/contribute", methods=["GET", "POST"])
@login_required
def contribute_wishlist_item(item_id):
    """
    Allow a standard user to contribute points toward one of their wishlist items.

    Points are deducted immediately and recorded in Point History.
    """

    if current_user.is_admin():
        flash("Admins cannot contribute points to wishlist items.")
        return redirect(url_for("main.wishlist"))

    item = db.session.get(WishlistItem, item_id)

    if not item or item.user_id != current_user.id:
        flash("Wishlist item not found.")
        return redirect(url_for("main.wishlist"))

    if not item.is_active or item.status != "active":
        flash("This wishlist item is not active.")
        return redirect(url_for("main.wishlist"))

    form = WishlistContributionForm()

    if form.validate_on_submit():

        amount = form.amount.data

        if amount > current_user.point_balance():
            flash("You do not have enough points to contribute that amount.")
            return redirect(url_for("main.contribute_wishlist_item", item_id=item.id))

        if amount > item.remaining_points():
            flash(f"This wishlist item only needs {item.remaining_points()} more point(s).")
            return redirect(url_for("main.contribute_wishlist_item", item_id=item.id))

        contribution = WishlistContribution(
            item_id=item.id,
            user_id=current_user.id,
            amount=amount,
            status="active"
        )

        db.session.add(contribution)
        db.session.flush()

        transaction = PointTransaction(
            user_id=current_user.id,
            amount=-amount,
            transaction_type="wishlist_contribution",
            reason=f"Saved points toward wishlist item: {item.name}",
            created_by_id=current_user.id
        )

        db.session.add(transaction)

        if item.is_funded():
            item.status = "funded"

            create_notification(
                user_id=current_user.id,
                title="Wishlist item funded",
                message=f"Your wishlist item '{item.name}' has reached its point target.",
                notification_type="success"
            )

            notify_admins(
                title="Wishlist item funded",
                message=f"{current_user.display_name}'s wishlist item '{item.name}' is now fully funded and ready for fulfilment.",
                notification_type="success",
                action_url=url_for("main.wishlist"),
                action_label="Open Wishlist"
            )
            # Check whether this wishlist contribution earned the user any badges.
            check_and_award_badges(current_user)

            db.session.commit()

            flash("Points added to wishlist item.")

        return redirect(url_for("main.wishlist"))

    return render_template(
        "contribute_wishlist_item.html",
        form=form,
        item=item
    )

@bp.route("/admin/wishlist/items/<int:item_id>/fulfil", methods=["POST"])
@login_required
def fulfil_wishlist_item(item_id):
    """
    Admin-only route for marking a funded wishlist item as fulfilled.

    This is used after the user has saved enough points toward the item
    and the admin has provided/approved the real-world reward.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the wishlist item.
    item = db.session.get(WishlistItem, item_id)

    if not item:
        flash("Wishlist item not found.")
        return redirect(url_for("main.wishlist"))

    # Removed items cannot be fulfilled.
    if not item.is_active or item.status == "removed":
        flash("Removed wishlist items cannot be fulfilled.")
        return redirect(url_for("main.wishlist"))

    # Only funded items should be fulfilled.
    if not item.is_funded():
        flash("This wishlist item has not reached its point target yet.")
        return redirect(url_for("main.wishlist"))

    # Mark the item as fulfilled and close it.
    item.status = "fulfilled"
    item.is_active = False

    # Notify the user.
    create_notification(
        user_id=item.user_id,
        title="Wishlist item fulfilled",
        message=f"Your wishlist item '{item.name}' has been fulfilled.",
        notification_type="success"
    )

    db.session.commit()

    flash("Wishlist item marked as fulfilled.")
    return redirect(url_for("main.wishlist"))

@bp.route("/admin/wishlist/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_wishlist_item(item_id):
    """
    Admin-only page for editing an existing wishlist item.

    Admins can change:
    - assigned user
    - item name
    - description
    - point cost

    If the edited point cost is now fully covered by existing saved points,
    the item is marked as funded.
    """

    # Block non-admin users.
    if not admin_required():
        return redirect(url_for("main.dashboard"))

    # Find the wishlist item.
    item = db.session.get(WishlistItem, item_id)

    if not item:
        flash("Wishlist item not found.")
        return redirect(url_for("main.wishlist"))

    # Removed or fulfilled items should not be edited.
    if item.status in ["removed", "fulfilled"]:
        flash("Removed or fulfilled wishlist items cannot be edited.")
        return redirect(url_for("main.wishlist"))

    # Create edit form and populate the user dropdown.
    form = WishlistEditItemForm(obj=item)

    active_users = User.query.filter_by(
        role="user",
        is_active_account=True
    ).order_by(
        User.display_name
    ).all()

    form.user_id.choices = [
        (user.id, f"{user.avatar_emoji} {user.display_name}")
        for user in active_users
    ]

    # Pre-fill selected user on first load.
    if request.method == "GET":
        form.user_id.data = item.user_id
        form.name.data = item.name
        form.description.data = item.description
        form.point_cost.data = item.point_cost

    if form.validate_on_submit():

        old_user_id = item.user_id
        old_point_cost = item.point_cost

        new_user = db.session.get(User, form.user_id.data)

        if not new_user:
            flash("Selected user not found.")
            return redirect(url_for("main.edit_wishlist_item", item_id=item.id))

        item.user_id = new_user.id
        item.name = form.name.data
        item.description = form.description.data
        item.point_cost = form.point_cost.data

        # If existing saved points now meet the new target, mark as funded.
        if item.is_funded():
            item.status = "funded"
        else:
            item.status = "active"

        # Notify the current owner.
        create_notification(
            user_id=item.user_id,
            title="Wishlist item updated",
            message=f"Your wishlist item '{item.name}' was updated by an admin.",
            notification_type="info",
            action_url=url_for("main.wishlist"),
            action_label="Open Wishlist"
        )

        # If ownership changed, notify the previous owner too.
        if old_user_id != item.user_id:
            create_notification(
                user_id=old_user_id,
                title="Wishlist item reassigned",
                message=f"The wishlist item '{item.name}' was moved to another user.",
                notification_type="warning"
            )

        # If the point cost changed, add clearer notification detail.
        if old_point_cost != item.point_cost:
            create_notification(
                user_id=item.user_id,
                title="Wishlist point cost changed",
                message=f"'{item.name}' changed from {old_point_cost} points to {item.point_cost} points.",
                notification_type="info",
                action_url=url_for("main.wishlist"),
                action_label="Open Wishlist"
            )

        db.session.commit()

        flash("Wishlist item updated.")
        return redirect(url_for("main.wishlist"))

    return render_template(
        "edit_wishlist_item.html",
        form=form,
        item=item
    )

@bp.route("/wishlist/archive")
@login_required
def wishlist_archive():
    """
    Wishlist archive page.

    Standard users:
    - see their own fulfilled/removed wishlist items.

    Admin users:
    - see fulfilled/removed wishlist items for all users.

    This keeps the main Wishlist page focused on active/funded items.
    """

    archived_statuses = [
        "fulfilled",
        "removed"
    ]

    if current_user.is_admin():

        archived_items = WishlistItem.query.filter(
            WishlistItem.status.in_(archived_statuses)
        ).order_by(
            WishlistItem.created_at.desc()
        ).all()

    else:

        archived_items = WishlistItem.query.filter(
            WishlistItem.user_id == current_user.id,
            WishlistItem.status.in_(archived_statuses)
        ).order_by(
            WishlistItem.created_at.desc()
        ).all()

    return render_template(
        "wishlist_archive.html",
        archived_items=archived_items
    )

# =========================================================
# REQUEST ARCHIVE
# =========================================================

@bp.route("/requests/archive")
@login_required
def request_archive():
    """
    Request archive page.

    Standard users:
    - see their own completed/rejected/cancelled task submissions
    - see their own approved/rejected/cancelled reward requests
    - see their own approved/rejected/cancelled wishlist requests

    Admin users:
    - see archived requests for all users

    This keeps main task, reward, and wishlist pages focused on current/pending items.
    """

    # These are considered archived task completion statuses.
    archived_task_statuses = [
        "approved",
        "rejected",
        "cancelled"
    ]

    # These are considered archived reward request statuses.
    archived_reward_statuses = [
        "approved",
        "rejected",
        "cancelled",
        "fulfilled"
    ]

    # These are considered archived wishlist request statuses.
    archived_wishlist_statuses = [
        "approved",
        "rejected",
        "cancelled"
    ]

    if current_user.is_admin():

        archived_task_requests = TaskCompletion.query.filter(
            TaskCompletion.status.in_(archived_task_statuses)
        ).order_by(
            TaskCompletion.submitted_at.desc()
        ).limit(30).all()

        archived_reward_requests = RewardPurchase.query.filter(
            RewardPurchase.status.in_(archived_reward_statuses)
        ).order_by(
            RewardPurchase.requested_at.desc()
        ).limit(30).all()

        archived_wishlist_requests = WishlistRequest.query.filter(
            WishlistRequest.status.in_(archived_wishlist_statuses)
        ).order_by(
            WishlistRequest.created_at.desc()
        ).limit(30).all()

    else:

        archived_task_requests = TaskCompletion.query.filter(
            TaskCompletion.user_id == current_user.id,
            TaskCompletion.status.in_(archived_task_statuses)
        ).order_by(
            TaskCompletion.submitted_at.desc()
        ).limit(20).all()

        archived_reward_requests = RewardPurchase.query.filter(
            RewardPurchase.user_id == current_user.id,
            RewardPurchase.status.in_(archived_reward_statuses)
        ).order_by(
            RewardPurchase.requested_at.desc()
        ).limit(20).all()

        archived_wishlist_requests = WishlistRequest.query.filter(
            WishlistRequest.user_id == current_user.id,
            WishlistRequest.status.in_(archived_wishlist_statuses)
        ).order_by(
            WishlistRequest.created_at.desc()
        ).limit(20).all()

    return render_template(
        "request_archive.html",
        archived_task_requests=archived_task_requests,
        archived_reward_requests=archived_reward_requests,
        archived_wishlist_requests=archived_wishlist_requests
    )