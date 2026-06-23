# FlaskForm is the base class for forms in Flask-WTF.
from flask_wtf import FlaskForm

# Field types used by the app.
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    IntegerField,
    TextAreaField,
    SelectField,
    HiddenField,
    BooleanField
)

# Validators check form input before the app uses it.
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    EqualTo
)
# =========================================================
# SHARED AVATAR CHOICES
# =========================================================

AVATAR_CHOICES = [
    ("🙂", "🙂 Smile"),
    ("🦊", "🦊 Fox"),
    ("🐼", "🐼 Panda"),
    ("🐸", "🐸 Frog"),
    ("🦁", "🦁 Lion"),
    ("🐯", "🐯 Tiger"),
    ("🐨", "🐨 Koala"),
    ("🐧", "🐧 Penguin"),
    ("🐢", "🐢 Turtle"),
    ("🦖", "🦖 Dinosaur"),
    ("🚀", "🚀 Rocket"),
    ("⭐", "⭐ Star"),
    ("⚽", "⚽ Soccer"),
    ("🎮", "🎮 Game"),
    ("🎸", "🎸 Guitar"),
    ("🌈", "🌈 Rainbow")
]


# =========================================================
# LOGIN FORM
# =========================================================

class LoginForm(FlaskForm):
    """
    Avatar + PIN login form.
    """

    selected_user_id = HiddenField(
        "Selected User",
        validators=[
            DataRequired()
        ]
    )

    password = PasswordField(
        "PIN",
        validators=[
            DataRequired(),
            Length(min=4, max=20)
        ]
    )

    submit = SubmitField("Log In")


# =========================================================
# TASK FORM
# =========================================================

class TaskForm(FlaskForm):
    """
    Form used by admins to create or edit a task.
    """
    import_task_id = SelectField(
        "Import from Previous Task",
        coerce=int,
        choices=[],
        validators=[
            Optional()
        ]
    )
    title = StringField(
        "Task Title",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    point_value = IntegerField(
        "Value",
        validators=[
            DataRequired(),
            NumberRange(min=0)
        ]
    )

    # Category choices are populated dynamically in routes.py.
    category = SelectField(
        "Category",
        choices=[],
        validators=[
            Optional()
        ]
    )

    completion_behavior = SelectField(
        "After Approval",
        choices=[
            ("stay_active", "Stay active after approval"),
            ("hide_after_approval", "Hide after approval")
        ],
        validators=[
            DataRequired()
        ]
    )

    is_hot = BooleanField(
        "Mark as Hot Task"
    )

    hot_bonus_points = IntegerField(
        "Hot Task Bonus",
        validators=[
            Optional(),
            NumberRange(min=0)
        ],
        default=0
    )

    hot_label = StringField(
        "Hot Task Label",
        validators=[
            Optional(),
            Length(max=120)
        ]
    )

    # Task customisation fields.
    # assigned_user_id choices are populated dynamically in routes.
    assigned_user_id = SelectField(
        "Assign To",
        coerce=int,
        choices=[],
        validators=[
            Optional()
        ]
    )

    assigned_visibility = SelectField(
        "Assignment Visibility",
        choices=[
            ("all", "Visible to everyone, but only the assigned user can complete it"),
            ("assigned_only", "Only visible to the assigned user")
        ],
        validators=[
            Optional()
        ]
    )

    availability_window = SelectField(
        "Availability Window",
        choices=[
            ("always", "Always available"),
            ("morning", "Morning only (5am – 12pm)"),
            ("afternoon", "Afternoon only (12pm – 5pm)"),
            ("evening", "Evening only (5pm – 10pm)"),
            ("weekdays", "Weekdays only (Mon – Fri)"),
            ("weekends", "Weekends only (Sat – Sun)"),
        ],
        validators=[
            DataRequired()
        ]
    )

    completion_scope = SelectField(
        "Completion Scope",
        choices=[
            ("per_user", "Each user can complete it independently"),
            ("household_once", "Once per household — hides after any user submits it"),
        ],
        validators=[
            DataRequired()
        ]
    )

    recurrence_days = SelectField(
        "Recurrence",
        choices=[
            ("", "No recurrence"),
            ("0,1,2,3,4,5,6", "Every day"),
            ("0,1,2,3,4", "Weekdays (Mon–Fri)"),
            ("5,6", "Weekends (Sat–Sun)"),
            ("0", "Mondays only"),
            ("1", "Tuesdays only"),
            ("2", "Wednesdays only"),
            ("3", "Thursdays only"),
            ("4", "Fridays only"),
            ("5", "Saturdays only"),
            ("6", "Sundays only"),
        ],
        validators=[Optional()]
    )

    is_active = BooleanField(
        "Visible to users (uncheck to keep hidden until ready)"
    )

    submit = SubmitField("Save Task")


# =========================================================
# REWARD FORM
# =========================================================

class RewardForm(FlaskForm):
    """
    Form used by admins to create or edit a shop reward.
    """
    import_reward_id = SelectField(
        "Import from Previous Reward",
        coerce=int,
        choices=[],
        validators=[
            Optional()
        ]
    )
    name = StringField(
        "Reward Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    # Category choices are populated dynamically in routes.py.
    category = SelectField(
        "Category",
        choices=[],
        validators=[
            Optional()
        ]
    )

    point_cost = IntegerField(
        "Cost",
        validators=[
            DataRequired(),
            NumberRange(min=0)
        ]
    )

    is_active = BooleanField(
        "Visible in shop (uncheck to keep hidden until ready)"
    )

    price_estimate = StringField(
        "Real-world price (optional)",
        validators=[Optional(), Length(max=60)]
    )

    store_url = StringField(
        "Store / listing URL (optional)",
        validators=[Optional(), Length(max=500)]
    )

    image_url = StringField(
        "Image URL (optional — paste a link to an image)",
        validators=[Optional(), Length(max=500)]
    )

    quantity = IntegerField(
        "Total stock (leave blank for unlimited)",
        validators=[Optional(), NumberRange(min=0)]
    )

    allow_multiple_in_cart = BooleanField(
        "Allow users to add multiple of this item to their cart"
    )

    disappear_when_empty = BooleanField(
        "Hide from shop when stock runs out"
    )

    daily_limit_per_user = IntegerField(
        "Daily limit per user (leave blank for no limit)",
        validators=[Optional(), NumberRange(min=1)]
    )

    submit = SubmitField("Save Reward")


# =========================================================
# USER CREATION FORM
# =========================================================

class UserForm(FlaskForm):
    """
    Form used by admins to create new users.
    """

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    display_name = StringField(
        "Display Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    avatar_emoji = SelectField(
        "Avatar",
        choices=AVATAR_CHOICES,
        validators=[
            DataRequired()
        ]
    )

    password = PasswordField(
        "Password or PIN",
        validators=[
            DataRequired()
        ]
    )

    role = SelectField(
        "Role",
        choices=[
            ("user", "Standard User"),
            ("admin", "Admin")
        ],
        validators=[
            DataRequired()
        ]
    )

    submit = SubmitField("Create User")


# =========================================================
# USER EDIT FORM
# =========================================================

class EditUserForm(FlaskForm):
    """
    Form used by admins to edit an existing user.
    """

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    display_name = StringField(
        "Display Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    avatar_emoji = SelectField(
        "Avatar",
        choices=AVATAR_CHOICES,
        validators=[
            DataRequired()
        ]
    )

    role = SelectField(
        "Role",
        choices=[
            ("user", "Standard User"),
            ("admin", "Admin")
        ],
        validators=[
            DataRequired()
        ]
    )

    kiosk_pin_skip = BooleanField(
        "Allow kiosk login without PIN (for young children)"
    )

    allowance_amount = IntegerField(
        "Weekly allowance",
        validators=[Optional(), NumberRange(min=0)],
        default=0
    )

    allowance_day = SelectField(
        "Allowance day",
        choices=[
            (-1, "Disabled"),
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ],
        coerce=int
    )

    submit = SubmitField("Save Changes")


# =========================================================
# PASSWORD CHANGE FORM
# =========================================================

class ChangePasswordForm(FlaskForm):
    """
    Form used by admins to reset a user's PIN/password.
    """

    password = PasswordField(
        "New PIN / Password",
        validators=[
            DataRequired(),
            Length(min=4, max=128)
        ]
    )

    confirm_password = PasswordField(
        "Confirm New PIN / Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="PIN/passwords must match.")
        ]
    )

    submit = SubmitField("Update PIN / Password")


# =========================================================
# POINT ADJUSTMENT FORM
# =========================================================

class PointAdjustmentForm(FlaskForm):
    """
    Form used by admins to manually add or remove points.
    """

    amount = IntegerField(
        "Balance Adjustment",
        validators=[
            DataRequired()
        ]
    )

    reason = TextAreaField(
        "Reason",
        validators=[
            DataRequired(),
            Length(max=255)
        ]
    )

    submit = SubmitField("Apply Adjustment")


# =========================================================
# ADMIN COMPLETE TASK FORM
# =========================================================

class AdminCompleteTaskForm(FlaskForm):
    """
    Form used by admins to mark a task complete for a user.
    """

    user_id = SelectField(
        "User",
        coerce=int,
        validators=[
            DataRequired()
        ]
    )

    task_id = SelectField(
        "Task",
        coerce=int,
        validators=[
            DataRequired()
        ]
    )

    submit = SubmitField("Complete Task and Award")


# =========================================================
# CATEGORY FORM
# =========================================================

class CategoryForm(FlaskForm):
    """
    Form used by admins to add task or reward categories.
    """

    name = StringField(
        "Category Name",
        validators=[
            DataRequired(),
            Length(max=80)
        ]
    )

    submit = SubmitField("Add Category")

# =========================================================
# REJECTION REASON FORM
# =========================================================

class RejectionReasonForm(FlaskForm):
    """
    Form used by admins when rejecting a task completion or reward request.

    The reason is shown in the user's history page.
    """

    reason = TextAreaField(
        "Rejection Reason",
        validators=[
            DataRequired(),
            Length(max=255)
        ]
    )

    submit = SubmitField("Reject")

# =========================================================
# GROUP GOAL FORMS
# =========================================================

class GroupGoalForm(FlaskForm):
    """
    Form used by admins to create a shared group goal.
    """

    title = StringField(
        "Goal Title",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    target_points = IntegerField(
        "Target Amount",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    price_estimate = StringField(
        "Real-world price (optional)",
        validators=[Optional(), Length(max=60)]
    )

    store_url = StringField(
        "Store / listing URL (optional)",
        validators=[Optional(), Length(max=500)]
    )

    image_url = StringField(
        "Image URL (optional — paste a link to an image)",
        validators=[Optional(), Length(max=500)]
    )

    submit = SubmitField("Save Group Goal")


class GroupGoalContributionForm(FlaskForm):
    """
    Form used by users to contribute points to a group goal.
    """

    amount = IntegerField(
        "Contribution Amount",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    submit = SubmitField("Contribute")

# =========================================================
# WISHLIST FORMS
# =========================================================

class WishlistRequestForm(FlaskForm):
    """
    Form used by standard users to request a wishlist item.
    """

    requested_name = StringField(
        "Item Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    requested_description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    submit = SubmitField("Submit Wishlist Request")


class WishlistApproveForm(FlaskForm):
    """
    Form used by admins to approve a wishlist request.

    The admin controls the final item name, description, and point cost.
    """

    name = StringField(
        "Item Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    point_cost = IntegerField(
        "Cost",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    price_estimate = StringField(
        "Real-world price (optional)",
        validators=[Optional(), Length(max=60)]
    )

    store_url = StringField(
        "Store / listing URL (optional)",
        validators=[Optional(), Length(max=500)]
    )

    image_url = StringField(
        "Image URL (optional — paste a link to an image)",
        validators=[Optional(), Length(max=500)]
    )

    submit = SubmitField("Approve and Add to Wishlist")


class WishlistAdminItemForm(FlaskForm):
    """
    Form used by admins to directly add a wishlist item to a user.
    """

    user_id = SelectField(
        "User",
        coerce=int,
        validators=[
            DataRequired()
        ]
    )

    name = StringField(
        "Item Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    point_cost = IntegerField(
        "Cost",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    price_estimate = StringField(
        "Real-world price (optional)",
        validators=[Optional(), Length(max=60)]
    )

    store_url = StringField(
        "Store / listing URL (optional)",
        validators=[Optional(), Length(max=500)]
    )

    image_url = StringField(
        "Image URL (optional — paste a link to an image)",
        validators=[Optional(), Length(max=500)]
    )

    submit = SubmitField("Add Wishlist Item")

class WishlistContributionForm(FlaskForm):
    """
    Form used by a user to save points toward an approved wishlist item.
    """

    amount = IntegerField(
        "Contribution Amount",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    submit = SubmitField("Add to Wishlist Item")

class WishlistEditItemForm(FlaskForm):
    """
    Form used by admins to edit an existing wishlist item.
    """

    user_id = SelectField(
        "User",
        coerce=int,
        validators=[
            DataRequired()
        ]
    )

    name = StringField(
        "Item Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    point_cost = IntegerField(
        "Cost",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    price_estimate = StringField(
        "Real-world price (optional)",
        validators=[Optional(), Length(max=60)]
    )

    store_url = StringField(
        "Store / listing URL (optional)",
        validators=[Optional(), Length(max=500)]
    )

    image_url = StringField(
        "Image URL (optional — paste a link to an image)",
        validators=[Optional(), Length(max=500)]
    )

    submit = SubmitField("Save Wishlist Item")

# =========================================================
# ROUTINE FORM
# =========================================================

class RoutineForm(FlaskForm):
    """
    Form used by admins to create or edit a routine.
    """

    title = StringField(
        "Routine Title",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional()
        ]
    )

    point_value = IntegerField(
        "Point Value",
        validators=[
            DataRequired(),
            NumberRange(min=0)
        ]
    )

    # Choices populated dynamically in routes.
    assigned_user_id = SelectField(
        "Assign To",
        coerce=int,
        choices=[],
        validators=[
            Optional()
        ]
    )

    submit = SubmitField("Save Routine")


class HouseholdSettingsForm(FlaskForm):
    """
    Form used by admins to update household-level app settings.
    """

    household_name = StringField(
        "Household / App Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    points_label = StringField(
        "Balance Label",
        validators=[
            DataRequired(),
            Length(max=40)
        ]
    )

    wishlist_requests_enabled = BooleanField(
        "Allow users to request wishlist items"
    )

    group_goals_enabled = BooleanField(
        "Allow users to contribute to group goals"
    )

    auto_end_streaks = BooleanField(
        "Automatically end streaks when a day is missed"
    )

    submit = SubmitField("Save Settings")