# Import datetime tools so we can record when records are created or reviewed.
from datetime import datetime, timezone

# UserMixin gives the User model the methods Flask-Login expects.
from flask_login import UserMixin

# Password helpers used to hash and check passwords/PINs.
from werkzeug.security import generate_password_hash, check_password_hash

# Import the database object.
from app import db


class User(UserMixin, db.Model):
    """
    Stores app users.

    Admin users manage the system.
    Standard users submit tasks and request rewards.
    """

    __tablename__ = "users"

    # Primary key: unique ID for each user.
    id = db.Column(db.Integer, primary_key=True)

    # Internal login username.
    # Even though the login screen now uses avatars, username is still useful
    # as a unique account identifier.
    username = db.Column(db.String(80), unique=True, nullable=False)

    # Friendly name shown throughout the app.
    display_name = db.Column(db.String(120), nullable=False)

    # Emoji avatar shown on the login screen.
    avatar_emoji = db.Column(
        db.String(10),
        nullable=False,
        default="🙂"
    )

    # Secure hashed password/PIN.
    password_hash = db.Column(db.String(255), nullable=False)

    # Role controls permissions.
    # Expected values:
    # - "admin"
    # - "user"
    role = db.Column(db.String(20), nullable=False, default="user")

    # Allows admins to disable accounts without deleting history.
    is_active_account = db.Column(db.Boolean, default=True)

    # When the account was created.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship: task completions submitted by this user.
    task_completions = db.relationship(
        "TaskCompletion",
        foreign_keys="TaskCompletion.user_id",
        back_populates="user"
    )

    # Relationship: task completions reviewed by this admin.
    reviewed_task_completions = db.relationship(
        "TaskCompletion",
        foreign_keys="TaskCompletion.reviewed_by_id",
        back_populates="reviewed_by"
    )

    # Relationship: reward purchases requested by this user.
    reward_purchases = db.relationship(
        "RewardPurchase",
        foreign_keys="RewardPurchase.user_id",
        back_populates="user"
    )

    # Relationship: reward purchases reviewed by this admin.
    reviewed_reward_purchases = db.relationship(
        "RewardPurchase",
        foreign_keys="RewardPurchase.reviewed_by_id",
        back_populates="reviewed_by"
    )

    # Relationship: point transactions belonging to this user.
    point_transactions = db.relationship(
        "PointTransaction",
        foreign_keys="PointTransaction.user_id",
        back_populates="user"
    )

    # Relationship: point transactions created by this admin/user.
    created_point_transactions = db.relationship(
        "PointTransaction",
        foreign_keys="PointTransaction.created_by_id",
        back_populates="created_by"
    )

    def set_password(self, password):
        """
        Hash and store a password/PIN.

        The plain password/PIN is never saved directly.
        """

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Check a submitted password/PIN against the stored hash.
        """

        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """
        Return True if this user is an admin.
        """

        return self.role == "admin"

    def point_balance(self):
        """
        Calculate current point balance from point transactions.

        We do not store a separate balance because the transaction ledger
        is the source of truth.
        """

        total = 0

        for transaction in self.point_transactions:
            total += transaction.amount

        return total


class Task(db.Model):
    """
    Stores task definitions.

    Example:
    - Tidy bedroom
    - Feed pets
    - Empty dishwasher
    """

    __tablename__ = "tasks"

    # Primary key: unique ID for each task.
    id = db.Column(db.Integer, primary_key=True)

    # Short task title.
    title = db.Column(db.String(120), nullable=False)

    # Optional longer description.
    description = db.Column(db.Text)

    # How many points the task awards when approved.
    point_value = db.Column(db.Integer, nullable=False, default=0)

    # Optional category such as Bedroom, Kitchen, Pets, School.
    category = db.Column(db.String(80))

    # Controls what happens after an admin approves a task completion.
    #
    # "stay_active":
    # - task remains visible after approval
    #
    # "hide_after_approval":
    # - task is hidden after approval
    completion_behavior = db.Column(
        db.String(30),
        nullable=False,
        default="stay_active"
    )

    # Allows admins to hide/archive tasks without deleting history.
    is_active = db.Column(db.Boolean, default=True)

    # Hot tasks are promoted tasks that appear first on the task board.
    is_hot = db.Column(db.Boolean, default=False)

    # Optional bonus points awarded while the task is hot.
    hot_bonus_points = db.Column(db.Integer, nullable=False, default=0)

    # Optional short label shown on the task card.
    hot_label = db.Column(db.String(120))

    # When the task was created.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def total_point_value(self):
        """
        Return the total points currently available for this task.

        Hot tasks can optionally add bonus points.
        """

        total = self.point_value or 0

        if self.is_hot:
            total += self.hot_bonus_points or 0

        return total

    # Relationship: one task can have many completion records.
    completions = db.relationship(
        "TaskCompletion",
        back_populates="task"
    )


class TaskCompletion(db.Model):
    """
    Stores task completion submissions and review outcomes.

    Status examples:
    - submitted
    - approved
    - rejected
    - cancelled
    """

    __tablename__ = "task_completions"

    # Primary key.
    id = db.Column(db.Integer, primary_key=True)

    # Linked task.
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)

    # User who completed/submitted the task.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Status of the task completion.
    status = db.Column(db.String(30), nullable=False, default="submitted")

    # When the task was submitted.
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # When the task was reviewed or cancelled.
    reviewed_at = db.Column(db.DateTime)

    # Admin who reviewed the task.
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Optional reason for rejection or cancellation.
    rejection_reason = db.Column(db.Text)

    # Relationships.
    task = db.relationship(
        "Task",
        back_populates="completions"
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="task_completions"
    )

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_id],
        back_populates="reviewed_task_completions"
    )

    point_transactions = db.relationship(
        "PointTransaction",
        back_populates="related_task_completion"
    )


class Reward(db.Model):
    """
    Stores shop rewards.

    Example:
    - Screen time
    - Snack
    - Day trip
    """

    __tablename__ = "rewards"

    # Primary key.
    id = db.Column(db.Integer, primary_key=True)

    # Reward name.
    name = db.Column(db.String(120), nullable=False)

    # Optional reward description.
    description = db.Column(db.Text)

    # Optional reward category such as Screen Time, Food, Activities, Toys.
    category = db.Column(db.String(80))

    # Point cost.
    point_cost = db.Column(db.Integer, nullable=False, default=0)

    # Allows admins to hide rewards without deleting history.
    is_active = db.Column(db.Boolean, default=True)

    # When the reward was created.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship: one reward can have many purchase/request records.
    purchases = db.relationship(
        "RewardPurchase",
        back_populates="reward"
    )


class RewardPurchase(db.Model):
    """
    Stores reward requests and review outcomes.

    Status examples:
    - requested
    - approved
    - rejected
    - cancelled
    - fulfilled
    """

    __tablename__ = "reward_purchases"

    # Primary key.
    id = db.Column(db.Integer, primary_key=True)

    # Linked reward.
    reward_id = db.Column(db.Integer, db.ForeignKey("rewards.id"), nullable=False)

    # User who requested the reward.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Request status.
    status = db.Column(db.String(30), nullable=False, default="requested")

    # When the reward was requested.
    requested_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # When the request was reviewed or cancelled.
    reviewed_at = db.Column(db.DateTime)

    # Admin who reviewed the request.
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Optional reason for rejection or cancellation.
    rejection_reason = db.Column(db.Text)

    # Relationships.
    reward = db.relationship(
        "Reward",
        back_populates="purchases"
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="reward_purchases"
    )

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_id],
        back_populates="reviewed_reward_purchases"
    )

    point_transactions = db.relationship(
        "PointTransaction",
        back_populates="related_reward_purchase"
    )


class PointTransaction(db.Model):
    """
    Stores every point change.

    This is the point ledger and should be treated as the source of truth.
    """

    __tablename__ = "point_transactions"

    # Primary key.
    id = db.Column(db.Integer, primary_key=True)

    # User whose points changed.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Positive values add points.
    # Negative values remove/reserve points.
    amount = db.Column(db.Integer, nullable=False)

    # Internal transaction type.
    transaction_type = db.Column(db.String(50), nullable=False)

    # Human-readable reason.
    reason = db.Column(db.String(255), nullable=False)

    # Optional link to a task completion.
    related_task_completion_id = db.Column(
        db.Integer,
        db.ForeignKey("task_completions.id")
    )

    # Optional link to a reward purchase.
    related_reward_purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("reward_purchases.id")
    )

    # Who created this transaction.
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # When the transaction was created.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships.
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="point_transactions"
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_point_transactions"
    )

    related_task_completion = db.relationship(
        "TaskCompletion",
        back_populates="point_transactions"
    )

    related_reward_purchase = db.relationship(
        "RewardPurchase",
        back_populates="point_transactions"
    )

class TaskCategory(db.Model):
    """
    Stores admin-managed task categories.

    These categories appear in:
    - Create Task
    - Edit Task
    - Task Board filter
    """

    __tablename__ = "task_categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(80), unique=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class RewardCategory(db.Model):
    """
    Stores admin-managed reward/shop categories.

    These categories appear in:
    - Create Reward
    - Edit Reward
    - Shop filter
    """

    __tablename__ = "reward_categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(80), unique=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Notification(db.Model):
    """
    Stores dashboard notifications for users.

    Example:
    - Your task was approved.
    - Your reward request was rejected.
    """

    __tablename__ = "notifications"

    # Primary key.
    id = db.Column(db.Integer, primary_key=True)

    # User who should see this notification.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Short notification title.
    title = db.Column(db.String(120), nullable=False)

    # Longer notification message.
    message = db.Column(db.String(255), nullable=False)
        # Optional URL for an action button.
    action_url = db.Column(db.String(255))

    # Optional action button label.
    action_label = db.Column(db.String(80))

    # Notification type controls styling.
    # Examples:
    # - success
    # - warning
    # - danger
    # - info
    notification_type = db.Column(db.String(30), nullable=False, default="info")

    # Whether the user has dismissed/read this notification.
    is_read = db.Column(db.Boolean, default=False)

    # When the notification was created.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to user.
    user = db.relationship("User")

class GroupGoal(db.Model):
    """
    Stores shared group goals.

    Users can contribute points toward these goals.
    """

    __tablename__ = "group_goals"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False)

    description = db.Column(db.Text)

    target_points = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(30), nullable=False, default="active")

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    contributions = db.relationship(
        "GroupGoalContribution",
        back_populates="goal"
    )

    def total_contributed(self):
        """
        Calculate how many points have been contributed to this goal.
        """

        total = 0

        for contribution in self.contributions:
            if contribution.status == "active":
                total += contribution.amount

        return total

    def remaining_points(self):
        """
        Calculate how many more points are needed.
        """

        remaining = self.target_points - self.total_contributed()

        if remaining < 0:
            return 0

        return remaining

    def progress_percentage(self):
        """
        Calculate goal progress as a percentage.
        """

        if self.target_points <= 0:
            return 0

        progress = int((self.total_contributed() / self.target_points) * 100)

        if progress > 100:
            return 100

        return progress

    def is_funded(self):
        """
        Return True if the goal has reached its target.
        """

        return self.total_contributed() >= self.target_points


class GroupGoalContribution(db.Model):
    """
    Stores individual user contributions toward group goals.
    """

    __tablename__ = "group_goal_contributions"

    id = db.Column(db.Integer, primary_key=True)

    goal_id = db.Column(db.Integer, db.ForeignKey("group_goals.id"), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    amount = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(30), nullable=False, default="active")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    goal = db.relationship(
        "GroupGoal",
        back_populates="contributions"
    )

    user = db.relationship("User")

class WishlistRequest(db.Model):
    """
    Stores user requests for items to be added to their wishlist.

    Example:
    - User requests "Lego Star Wars X-Wing"
    - Admin reviews the request
    - Admin approves it and creates a WishlistItem with a point cost
    """

    __tablename__ = "wishlist_requests"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    requested_name = db.Column(db.String(120), nullable=False)

    requested_description = db.Column(db.Text)

    status = db.Column(db.String(30), nullable=False, default="requested")

    rejection_reason = db.Column(db.Text)

    reviewed_at = db.Column(db.DateTime)

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship(
        "User",
        foreign_keys=[user_id]
    )

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_id]
    )


class WishlistItem(db.Model):
    """
    Stores approved wishlist items.

    Wishlist items belong to one user and have an admin-set point cost.
    Users can contribute points toward wishlist items over time.
    """

    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)

    description = db.Column(db.Text)

    point_cost = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(30), nullable=False, default="active")

    is_active = db.Column(db.Boolean, default=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship(
        "User",
        foreign_keys=[user_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    contributions = db.relationship(
        "WishlistContribution",
        back_populates="item"
    )

    def total_saved(self):
        """
        Calculate active points saved toward this wishlist item.
        """

        total = 0

        for contribution in self.contributions:
            if contribution.status == "active":
                total += contribution.amount

        return total

    def remaining_points(self):
        """
        Calculate how many more points are needed.
        """

        remaining = self.point_cost - self.total_saved()

        if remaining < 0:
            return 0

        return remaining

    def progress_percentage(self):
        """
        Calculate wishlist item progress as a percentage.
        """

        if self.point_cost <= 0:
            return 0

        progress = int((self.total_saved() / self.point_cost) * 100)

        if progress > 100:
            return 100

        return progress

    def is_funded(self):
        """
        Return True if this wishlist item has reached its point cost.
        """

        return self.total_saved() >= self.point_cost


class WishlistContribution(db.Model):
    """
    Stores user point contributions toward an approved wishlist item.

    Points are deducted immediately when contributed.
    If the wishlist item is removed, active contributions can be refunded.
    """

    __tablename__ = "wishlist_contributions"

    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey("wishlist_items.id"), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    amount = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(30), nullable=False, default="active")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    item = db.relationship(
        "WishlistItem",
        back_populates="contributions"
    )

    user = db.relationship("User")

class Badge(db.Model):
    """
    Stores available achievement badges.

    Examples:
    - First Task
    - Team Player
    - Wishlist Saver
    """

    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(80), unique=True, nullable=False)

    name = db.Column(db.String(120), nullable=False)

    description = db.Column(db.String(255), nullable=False)

    icon = db.Column(db.String(20), nullable=False, default="🏅")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class UserBadge(db.Model):
    """
    Stores badges earned by users.
    """

    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)

    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")

    badge = db.relationship("Badge")

class HouseholdSettings(db.Model):
    """
    Stores household-level app settings.

    This table should normally only have one row.
    """

    __tablename__ = "household_settings"

    id = db.Column(db.Integer, primary_key=True)

    household_name = db.Column(
        db.String(120),
        nullable=False,
        default="Project Meridian"
    )

    points_label = db.Column(
        db.String(40),
        nullable=False,
        default="points"
    )

    wishlist_requests_enabled = db.Column(
        db.Boolean,
        default=True
    )

    group_goals_enabled = db.Column(
        db.Boolean,
        default=True
    )

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )