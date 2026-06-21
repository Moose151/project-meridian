# Import datetime tools so we can record when records are created or reviewed.
from datetime import date, datetime, timedelta, timezone

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

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)

    display_name = db.Column(db.String(120), nullable=False, index=True)

    avatar_emoji = db.Column(
        db.String(10),
        nullable=False,
        default="🙂"
    )

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="user", index=True)

    is_active_account = db.Column(db.Boolean, default=True, index=True)

    # When True, this admin can submit tasks, earn points, request rewards,
    # contribute to goals and wishlist items, and appear on leaderboards.
    # Has no effect on standard users (they always participate).
    participation_enabled = db.Column(db.Boolean, default=False, nullable=False)

    # When True, this user can log into the kiosk by tapping their card
    # without entering a PIN. Intended for young children.
    kiosk_pin_skip = db.Column(db.Boolean, default=False, nullable=False)

    # Automatic weekly allowance. allowance_day is the day of the week
    # (0=Mon … 6=Sun) on which points are awarded. -1 = disabled.
    allowance_amount = db.Column(db.Integer, default=0, nullable=False)
    allowance_day = db.Column(db.Integer, default=-1, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    task_completions = db.relationship(
        "TaskCompletion",
        foreign_keys="TaskCompletion.user_id",
        back_populates="user"
    )

    reviewed_task_completions = db.relationship(
        "TaskCompletion",
        foreign_keys="TaskCompletion.reviewed_by_id",
        back_populates="reviewed_by"
    )

    reward_purchases = db.relationship(
        "RewardPurchase",
        foreign_keys="RewardPurchase.user_id",
        back_populates="user"
    )

    reviewed_reward_purchases = db.relationship(
        "RewardPurchase",
        foreign_keys="RewardPurchase.reviewed_by_id",
        back_populates="reviewed_by"
    )

    point_transactions = db.relationship(
        "PointTransaction",
        foreign_keys="PointTransaction.user_id",
        back_populates="user"
    )

    created_point_transactions = db.relationship(
        "PointTransaction",
        foreign_keys="PointTransaction.created_by_id",
        back_populates="created_by"
    )

    def set_password(self, password):
        """
        Hash and store a password/PIN.
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

    def can_participate(self):
        """
        Return True if this user can act as a household participant.

        Standard users always can. Admins only can when participation_enabled
        is True.
        """

        if self.role == "user":
            return True

        return bool(self.participation_enabled)

    def point_balance(self):
        """
        Calculate current point balance from point transactions.

        The transaction ledger is the source of truth.
        """

        total = 0

        for transaction in self.point_transactions:
            total += transaction.amount

        return total


class Task(db.Model):
    """
    Stores task definitions.
    """

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.Text)

    point_value = db.Column(db.Integer, nullable=False, default=0)

    category = db.Column(db.String(80), index=True)

    completion_behavior = db.Column(
        db.String(30),
        nullable=False,
        default="stay_active"
    )

    is_active = db.Column(db.Boolean, default=True, index=True)

    is_hot = db.Column(db.Boolean, default=False, index=True)

    hot_bonus_points = db.Column(db.Integer, nullable=False, default=0)

    hot_label = db.Column(db.String(120))

    # Task customisation fields
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    assigned_visibility = db.Column(db.String(30), nullable=False, default="all")
    availability_window = db.Column(db.String(30), nullable=False, default="always")
    completion_scope = db.Column(db.String(30), nullable=False, default="per_user")

    # Comma-separated weekday numbers (0=Mon … 6=Sun) on which this task
    # recurs. When set, completions older than 7 days are ignored so the
    # task becomes available again each week. Empty string = no recurrence.
    recurrence_days = db.Column(db.String(20), nullable=False, default="")

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    def total_point_value(self):
        """
        Return the total points currently available for this task.

        Hot tasks can optionally add bonus points.
        """

        total = self.point_value or 0

        if self.is_hot:
            total += self.hot_bonus_points or 0

        return total

    completions = db.relationship(
        "TaskCompletion",
        back_populates="task"
    )

    assigned_user = db.relationship(
        "User",
        foreign_keys=[assigned_user_id]
    )


class TaskCompletion(db.Model):
    """
    Stores task completion submissions and review outcomes.
    """

    __tablename__ = "task_completions"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="submitted",
        index=True
    )

    submitted_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    reviewed_at = db.Column(db.DateTime, index=True)

    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    rejection_reason = db.Column(db.Text)

    # Optional photo evidence uploaded by the user at submission time.
    # Stores a relative path under app/static/uploads/evidence/.
    evidence_photo = db.Column(db.String(255))

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
    """

    __tablename__ = "rewards"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.Text)

    category = db.Column(db.String(80), index=True)

    point_cost = db.Column(db.Integer, nullable=False, default=0)

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    purchases = db.relationship(
        "RewardPurchase",
        back_populates="reward"
    )


class RewardPurchase(db.Model):
    """
    Stores reward requests and review outcomes.
    """

    __tablename__ = "reward_purchases"

    id = db.Column(db.Integer, primary_key=True)

    reward_id = db.Column(
        db.Integer,
        db.ForeignKey("rewards.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="requested",
        index=True
    )

    requested_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    reviewed_at = db.Column(db.DateTime, index=True)

    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    rejection_reason = db.Column(db.Text)

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

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    amount = db.Column(db.Integer, nullable=False)

    transaction_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    reason = db.Column(db.String(255), nullable=False)

    related_task_completion_id = db.Column(
        db.Integer,
        db.ForeignKey("task_completions.id"),
        index=True
    )

    related_reward_purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("reward_purchases.id"),
        index=True
    )

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

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
    """

    __tablename__ = "task_categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )


class RewardCategory(db.Model):
    """
    Stores admin-managed reward/shop categories.
    """

    __tablename__ = "reward_categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )


class Notification(db.Model):
    """
    Stores dashboard notifications for users.
    """

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    title = db.Column(db.String(120), nullable=False)

    message = db.Column(db.String(255), nullable=False)

    action_url = db.Column(db.String(255))

    action_label = db.Column(db.String(80))

    notification_type = db.Column(
        db.String(30),
        nullable=False,
        default="info",
        index=True
    )

    is_read = db.Column(db.Boolean, default=False, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    user = db.relationship("User")


class GroupGoal(db.Model):
    """
    Stores shared group goals.

    Users can contribute points toward these goals.
    """

    __tablename__ = "group_goals"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.Text)

    target_points = db.Column(db.Integer, nullable=False)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True
    )

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

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

    goal_id = db.Column(
        db.Integer,
        db.ForeignKey("group_goals.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    amount = db.Column(db.Integer, nullable=False)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    goal = db.relationship(
        "GroupGoal",
        back_populates="contributions"
    )

    user = db.relationship("User")


class WishlistRequest(db.Model):
    """
    Stores user requests for items to be added to their wishlist.
    """

    __tablename__ = "wishlist_requests"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    requested_name = db.Column(db.String(120), nullable=False, index=True)

    requested_description = db.Column(db.Text)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="requested",
        index=True
    )

    rejection_reason = db.Column(db.Text)

    reviewed_at = db.Column(db.DateTime, index=True)

    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

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

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.Text)

    point_cost = db.Column(db.Integer, nullable=False)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True
    )

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

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
    """

    __tablename__ = "wishlist_contributions"

    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(
        db.Integer,
        db.ForeignKey("wishlist_items.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    amount = db.Column(db.Integer, nullable=False)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    item = db.relationship(
        "WishlistItem",
        back_populates="contributions"
    )

    user = db.relationship("User")


class Badge(db.Model):
    """
    Stores available achievement badges.
    """

    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(80), unique=True, nullable=False, index=True)

    name = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.String(255), nullable=False)

    icon = db.Column(db.String(20), nullable=False, default="🏅")

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )


class UserBadge(db.Model):
    """
    Stores badges earned by users.
    """

    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    badge_id = db.Column(
        db.Integer,
        db.ForeignKey("badges.id"),
        nullable=False,
        index=True
    )

    earned_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

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


class Routine(db.Model):
    """
    Stores habit routines created by admins.

    Routines are repeated daily habits (e.g. shower, brush teeth).
    Points are awarded immediately on completion — no approval needed.
    Streak tracking is based on consecutive completion dates.
    """

    __tablename__ = "routines"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False, index=True)

    description = db.Column(db.Text)

    point_value = db.Column(db.Integer, nullable=False, default=1)

    # If set, only this user sees and can complete the routine.
    # If None, all users see the routine.
    assigned_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        index=True
    )

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    assigned_user = db.relationship(
        "User",
        foreign_keys=[assigned_user_id]
    )

    completions = db.relationship(
        "RoutineCompletion",
        back_populates="routine"
    )

    def completed_today_by_user(self, user_id):
        """Return True if the user has already completed this routine today."""
        today = date.today()
        return any(
            c.user_id == user_id and c.completed_date == today
            for c in self.completions
        )

    def current_streak_for_user(self, user_id):
        """Return the current consecutive-day streak count for a user."""
        completion_dates = sorted(
            {c.completed_date for c in self.completions if c.user_id == user_id},
            reverse=True
        )

        if not completion_dates:
            return 0

        today = date.today()

        # Streak is broken if the last completion was more than 1 day ago.
        if completion_dates[0] < today - timedelta(days=1):
            return 0

        streak = 1
        for i in range(1, len(completion_dates)):
            if completion_dates[i] == completion_dates[i - 1] - timedelta(days=1):
                streak += 1
            else:
                break

        return streak


class RoutineCompletion(db.Model):
    """
    Records each time a user completes a routine on a given day.

    One record per user per routine per calendar date.
    """

    __tablename__ = "routine_completions"

    id = db.Column(db.Integer, primary_key=True)

    routine_id = db.Column(
        db.Integer,
        db.ForeignKey("routines.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    completed_date = db.Column(db.Date, nullable=False, index=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    routine = db.relationship(
        "Routine",
        back_populates="completions"
    )

    user = db.relationship("User")
