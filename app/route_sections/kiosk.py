"""
Kiosk mode routes.

Touch-friendly household hub interface at /kiosk.
Uses its own session key (kiosk_user_id) rather than Flask-Login, so the
kiosk can switch users without affecting sessions on other devices.
"""

from datetime import date, datetime, timezone

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from app import db
from app.models import (
    Badge, UserBadge,
    GroupGoal, GroupGoalContribution,
    Notification,
    PointTransaction,
    Reward, RewardPurchase,
    Routine, RoutineCompletion,
    Task, TaskCompletion,
    User,
    WishlistContribution, WishlistItem, WishlistRequest,
)
from app.services.badge_service import check_and_award_badges
from app.services.notification_service import notify_admins
from app.services.points_service import calculate_total_earned
from app.services.settings_service import get_household_settings, get_points_label


def _kiosk_user():
    """Return the active kiosk session user, or None."""
    user_id = session.get("kiosk_user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user or not user.is_active_account:
        session.pop("kiosk_user_id", None)
        return None
    return user


def _get_kiosk_cart(user_id):
    """Return kiosk cart for the given user as {str(reward_id): int}."""
    return session.get(f"kiosk_cart_{user_id}", {})


def _save_kiosk_cart(user_id, cart):
    session[f"kiosk_cart_{user_id}"] = cart


def _kiosk_today_midnight_utc():
    """Return today's local midnight as UTC-aware datetime for daily limit queries."""
    today = date.today()
    midnight_naive = datetime(today.year, today.month, today.day, 0, 0, 0)
    local_now = datetime.now()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    offset = utc_now - local_now
    return (midnight_naive + offset).replace(tzinfo=timezone.utc)


def _task_in_window(task):
    """Return True if the task is within its availability window."""
    window = task.availability_window or "always"
    if window == "always":
        return True
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    if window == "morning":
        return 5 <= hour < 12
    elif window == "afternoon":
        return 12 <= hour < 17
    elif window == "evening":
        return 17 <= hour < 22
    elif window == "weekdays":
        return weekday < 5
    elif window == "weekends":
        return weekday >= 5
    return True


def _visible_to_user(task, user):
    """Return True if the task is visible to this user."""
    if not task.assigned_user_id:
        return True
    if task.assigned_user_id == user.id:
        return True
    return (task.assigned_visibility or "all") == "all"


def _recurrence_days_set(task):
    """Return the set of weekday ints from task.recurrence_days, or None."""
    if not task.recurrence_days:
        return None
    try:
        return {int(d) for d in task.recurrence_days.split(",") if d.strip()}
    except ValueError:
        return None


def _get_available_tasks(user):
    """Return tasks available for the given kiosk user."""
    from datetime import timedelta
    today = date.today()
    today_weekday = today.weekday()
    week_start = today - timedelta(days=today_weekday)  # Monday of current week

    tasks = Task.query.filter_by(is_active=True, is_archived=False).order_by(
        Task.is_hot.desc(),
        Task.category,
        Task.title
    ).all()

    tasks = [t for t in tasks if _task_in_window(t)]
    tasks = [t for t in tasks if _visible_to_user(t, user)]

    # Filter recurring tasks to only show on their designated weekdays.
    filtered = []
    for t in tasks:
        days = _recurrence_days_set(t)
        if days is not None and today_weekday not in days:
            continue
        filtered.append(t)
    tasks = filtered

    household_once_ids = [
        t.id for t in tasks
        if (t.completion_scope or "per_user") == "household_once"
    ]
    if household_once_ids:
        # For recurring tasks, only block on completions from this week.
        recurring_ids = {
            t.id for t in tasks
            if t.id in set(household_once_ids) and _recurrence_days_set(t) is not None
        }
        non_recurring_once = [tid for tid in household_once_ids if tid not in recurring_ids]

        taken_ids = set()

        if non_recurring_once:
            taken_ids |= {
                row[0] for row in db.session.query(TaskCompletion.task_id).filter(
                    TaskCompletion.task_id.in_(non_recurring_once),
                    TaskCompletion.status.in_(["submitted", "approved"])
                ).all()
            }

        if recurring_ids:
            taken_ids |= {
                row[0] for row in db.session.query(TaskCompletion.task_id).filter(
                    TaskCompletion.task_id.in_(recurring_ids),
                    TaskCompletion.status.in_(["submitted", "approved"]),
                    TaskCompletion.submitted_at >= week_start
                ).all()
            }

        tasks = [t for t in tasks if t.id not in taken_ids]

    return tasks


def register_kiosk_routes(bp):
    """Register kiosk mode routes."""

    # =========================================================
    # LANDING AND AUTH
    # =========================================================

    @bp.route("/kiosk")
    def kiosk_landing():
        """
        Kiosk landing page.

        Shows all active participating users as large tap targets.
        """
        session.pop("kiosk_user_id", None)

        active_users = User.query.filter_by(
            is_active_account=True
        ).order_by(
            User.display_name
        ).all()

        return render_template(
            "kiosk_landing.html",
            users=active_users
        )

    @bp.route("/kiosk/user/<int:user_id>", methods=["GET", "POST"])
    def kiosk_pin(user_id):
        """
        PIN entry screen for a specific user.

        If the user has kiosk_pin_skip enabled, a GET request auto-logs them
        in immediately without requiring a PIN.
        """
        user = db.session.get(User, user_id)

        if not user or not user.is_active_account:
            return redirect(url_for("main.kiosk_landing"))

        # PIN-skip: auto-login on GET for users with the flag set.
        if request.method == "GET" and user.kiosk_pin_skip:
            session["kiosk_user_id"] = user.id
            return redirect(url_for("main.kiosk_dashboard"))

        error = None

        if request.method == "POST":
            pin = request.form.get("pin", "").strip()

            if user.check_password(pin):
                session["kiosk_user_id"] = user.id
                return redirect(url_for("main.kiosk_dashboard"))

            error = "Incorrect PIN. Please try again."

        return render_template(
            "kiosk_pin.html",
            user=user,
            error=error
        )

    @bp.route("/kiosk/switch")
    def kiosk_switch():
        """
        Clear kiosk session and return to landing.
        """
        session.pop("kiosk_user_id", None)
        return redirect(url_for("main.kiosk_landing"))

    # =========================================================
    # DASHBOARD
    # =========================================================

    @bp.route("/kiosk/dashboard")
    def kiosk_dashboard():
        """
        Kiosk user dashboard with overview cards.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        available_tasks = _get_available_tasks(user)

        submitted_task_ids = {
            row[0] for row in db.session.query(TaskCompletion.task_id).filter_by(
                user_id=user.id,
                status="submitted"
            ).all()
        }

        ready_tasks = [t for t in available_tasks if t.id not in submitted_task_ids]
        hot_tasks = [t for t in ready_tasks if t.is_hot]

        pending_task_completions = TaskCompletion.query.filter_by(
            user_id=user.id,
            status="submitted"
        ).order_by(TaskCompletion.submitted_at.desc()).all()

        pending_reward_requests = RewardPurchase.query.filter_by(
            user_id=user.id,
            status="requested"
        ).order_by(RewardPurchase.requested_at.desc()).all()

        current_balance = user.point_balance()

        affordable_count = Reward.query.filter(
            Reward.is_active == True,
            Reward.is_archived == False,
            Reward.point_cost <= current_balance
        ).count()

        # Routines today.
        today = date.today()
        user_routines = Routine.query.filter_by(is_active=True).filter(
            or_(
                Routine.assigned_user_id == None,
                Routine.assigned_user_id == user.id
            )
        ).all()

        routine_data_dash = [
            {
                "routine": r,
                "streak": r.current_streak_for_user(user.id),
                "done_today": r.completed_today_by_user(user.id),
            }
            for r in user_routines
        ]
        total_routines = len(user_routines)
        routines_done_today = sum(1 for rd in routine_data_dash if rd["done_today"])
        best_streak = max((rd["streak"] for rd in routine_data_dash), default=0)
        incomplete_routines = [rd for rd in routine_data_dash if not rd["done_today"]]

        # Admin approval counts (shown even for non-admin kiosk users as context).
        pending_task_count = TaskCompletion.query.filter_by(status="submitted").count()
        pending_reward_count = RewardPurchase.query.filter_by(status="requested").count()

        # Mini leaderboard: top 5 participating users by current balance.
        all_users = User.query.filter_by(is_active_account=True).all()
        participating = [
            (u, u.point_balance())
            for u in all_users
            if u.can_participate()
        ]
        leaderboard = sorted(participating, key=lambda x: x[1], reverse=True)[:5]

        return render_template(
            "kiosk_dashboard.html",
            user=user,
            kiosk_user=user,
            ready_task_count=len(ready_tasks),
            hot_task_count=len(hot_tasks),
            pending_task_completions=pending_task_completions,
            pending_reward_requests=pending_reward_requests,
            pending_task_count=pending_task_count,
            pending_reward_count=pending_reward_count,
            leaderboard=leaderboard,
            current_balance=current_balance,
            affordable_count=affordable_count,
            total_routines=total_routines,
            routines_done_today=routines_done_today,
            best_streak=best_streak,
            incomplete_routines=incomplete_routines,
        )

    # =========================================================
    # TASKS
    # =========================================================

    @bp.route("/kiosk/tasks")
    def kiosk_tasks():
        """
        Kiosk task list.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        tasks = _get_available_tasks(user)

        submitted_task_ids = {
            row[0] for row in db.session.query(TaskCompletion.task_id).filter_by(
                user_id=user.id,
                status="submitted"
            ).all()
        }

        return render_template(
            "kiosk_tasks.html",
            user=user,
            kiosk_user=user,
            tasks=tasks,
            submitted_task_ids=submitted_task_ids
        )

    @bp.route("/kiosk/tasks/<int:task_id>/complete", methods=["POST"])
    def kiosk_complete_task(task_id):
        """
        Submit a task completion from the kiosk.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        task = db.session.get(Task, task_id)

        if not task or not task.is_active:
            flash("Task not found or no longer available.")
            return redirect(url_for("main.kiosk_tasks"))

        if task.assigned_user_id and task.assigned_user_id != user.id:
            flash("This task is assigned to another user.")
            return redirect(url_for("main.kiosk_tasks"))

        existing = TaskCompletion.query.filter_by(
            task_id=task.id,
            user_id=user.id,
            status="submitted"
        ).first()

        if existing:
            flash("You already submitted this task and it is waiting for approval.")
            return redirect(url_for("main.kiosk_tasks"))

        if (task.completion_scope or "per_user") == "household_once":
            household_sub = TaskCompletion.query.filter(
                TaskCompletion.task_id == task.id,
                TaskCompletion.status.in_(["submitted", "approved"])
            ).first()
            if household_sub:
                flash("This task was already submitted by another household member.")
                return redirect(url_for("main.kiosk_tasks"))

        completion = TaskCompletion(
            task_id=task.id,
            user_id=user.id,
            status="submitted"
        )
        db.session.add(completion)
        db.session.commit()

        flash(f"'{task.title}' submitted for approval!", "celebrate")
        return redirect(url_for("main.kiosk_tasks"))

    # =========================================================
    # SHOP (REWARDS + CART)
    # =========================================================

    @bp.route("/kiosk/rewards")
    def kiosk_rewards():
        """Kiosk shop — browse rewards and add them to the cart."""
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        rewards = Reward.query.filter_by(is_active=True, is_archived=False).order_by(
            Reward.point_cost, Reward.name
        ).all()

        # Hide rewards that are out of stock and set to disappear.
        rewards = [
            r for r in rewards
            if not (r.remaining_stock() is not None and r.remaining_stock() <= 0 and r.disappear_when_empty)
        ]

        cart = _get_kiosk_cart(user.id)
        current_balance = user.point_balance()

        reward_info = {}
        for r in rewards:
            reward_info[r.id] = {
                "remaining_stock": r.remaining_stock(),
                "daily_remaining": r.daily_remaining_for_user(user.id),
                "cart_qty": int(cart.get(str(r.id), 0)),
            }

        return render_template(
            "kiosk_rewards.html",
            user=user,
            kiosk_user=user,
            rewards=rewards,
            reward_info=reward_info,
            current_balance=current_balance,
        )

    @bp.route("/kiosk/shop/cart")
    def kiosk_cart():
        """Kiosk cart — review items before checkout."""
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        cart = _get_kiosk_cart(user.id)
        cart_items = []
        total_cost = 0

        for rid_str, qty in list(cart.items()):
            rid = int(rid_str)
            r = db.session.get(Reward, rid)
            if r and r.is_active and not r.is_archived:
                cart_items.append((r, qty))
                total_cost += r.point_cost * qty
            else:
                cart.pop(rid_str, None)

        _save_kiosk_cart(user.id, cart)
        current_balance = user.point_balance()

        return render_template(
            "kiosk_cart.html",
            user=user,
            kiosk_user=user,
            cart_items=cart_items,
            total_cost=total_cost,
            current_balance=current_balance,
        )

    @bp.route("/kiosk/shop/cart/add/<int:reward_id>", methods=["POST"])
    def kiosk_cart_add(reward_id):
        """Add a reward to the kiosk cart, respecting stock and daily limits."""
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        reward = db.session.get(Reward, reward_id)
        if not reward or not reward.is_active or reward.is_archived:
            flash("Reward not found.")
            return redirect(url_for("main.kiosk_rewards"))

        qty_requested = request.form.get("quantity", 1, type=int)
        if qty_requested < 1:
            qty_requested = 1
        if not reward.allow_multiple_in_cart:
            qty_requested = 1

        cart = _get_kiosk_cart(user.id)
        current_in_cart = int(cart.get(str(reward_id), 0))

        # Enforce daily limit.
        daily_rem = reward.daily_remaining_for_user(user.id)
        if daily_rem is not None:
            already_today = reward.daily_used_by_user(user.id)
            total_today = already_today + current_in_cart + qty_requested
            if total_today > reward.daily_limit_per_user:
                allowed = reward.daily_limit_per_user - already_today - current_in_cart
                if allowed <= 0:
                    flash(f"You've reached your daily limit for '{reward.name}'.")
                    return redirect(url_for("main.kiosk_rewards"))
                qty_requested = allowed

        # Enforce stock.
        stock = reward.remaining_stock()
        if stock is not None:
            if current_in_cart + qty_requested > stock:
                allowed = stock - current_in_cart
                if allowed <= 0:
                    flash(f"'{reward.name}' is out of stock.")
                    return redirect(url_for("main.kiosk_rewards"))
                qty_requested = allowed

        new_qty = current_in_cart + qty_requested
        if new_qty <= 0:
            cart.pop(str(reward_id), None)
        else:
            cart[str(reward_id)] = new_qty

        _save_kiosk_cart(user.id, cart)

        if qty_requested > 1:
            flash(f"Added {qty_requested}× '{reward.name}' to cart.")
        else:
            flash(f"'{reward.name}' added to cart.")
        return redirect(url_for("main.kiosk_rewards"))

    @bp.route("/kiosk/shop/cart/remove/<int:reward_id>", methods=["POST"])
    def kiosk_cart_remove(reward_id):
        """Remove a reward from the kiosk cart."""
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        cart = _get_kiosk_cart(user.id)
        cart.pop(str(reward_id), None)
        _save_kiosk_cart(user.id, cart)
        return redirect(url_for("main.kiosk_cart"))

    @bp.route("/kiosk/shop/checkout", methods=["POST"])
    def kiosk_checkout():
        """
        Checkout the kiosk cart — creates one RewardPurchase per unit and reserves points.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        cart = _get_kiosk_cart(user.id)
        if not cart:
            flash("Your cart is empty.")
            return redirect(url_for("main.kiosk_rewards"))

        midnight_utc = _kiosk_today_midnight_utc()
        requested = []

        for rid_str, qty in list(cart.items()):
            rid = int(rid_str)
            reward = db.session.get(Reward, rid)

            if not reward or not reward.is_active or reward.is_archived:
                continue

            # Enforce daily limit.
            if reward.daily_limit_per_user is not None:
                used_today = RewardPurchase.query.filter(
                    RewardPurchase.reward_id == rid,
                    RewardPurchase.user_id == user.id,
                    RewardPurchase.status.in_(["requested", "approved", "fulfilled"]),
                    RewardPurchase.requested_at >= midnight_utc
                ).count()
                allowed = reward.daily_limit_per_user - used_today
                if allowed <= 0:
                    flash(f"Daily limit reached for '{reward.name}' — skipped.")
                    continue
                qty = min(qty, allowed)

            # Enforce stock.
            if reward.quantity is not None:
                used_total = RewardPurchase.query.filter(
                    RewardPurchase.reward_id == rid,
                    RewardPurchase.status.in_(["requested", "approved", "fulfilled"])
                ).count()
                remaining = reward.quantity - used_total
                if remaining <= 0:
                    flash(f"'{reward.name}' is out of stock — skipped.")
                    continue
                qty = min(qty, remaining)

            unit_count = 0
            for _ in range(qty):
                if user.point_balance() < reward.point_cost:
                    flash(f"Not enough {get_points_label()} for '{reward.name}' — some units skipped.")
                    break

                purchase = RewardPurchase(
                    reward_id=reward.id,
                    user_id=user.id,
                    status="requested"
                )
                db.session.add(purchase)
                db.session.flush()

                reservation = PointTransaction(
                    user_id=user.id,
                    amount=-reward.point_cost,
                    transaction_type="reward_requested",
                    reason=f"Requested reward: {reward.name}",
                    related_reward_purchase_id=purchase.id,
                    created_by_id=user.id
                )
                db.session.add(reservation)
                unit_count += 1

            if unit_count:
                requested.append(f"{reward.name}" if unit_count == 1 else f"{reward.name} ×{unit_count}")

        db.session.commit()
        _save_kiosk_cart(user.id, {})

        if requested:
            flash(
                f"Requested: {', '.join(requested)}. {get_points_label().capitalize()} reserved pending approval.",
                "celebrate"
            )
        return redirect(url_for("main.kiosk_dashboard"))

    # =========================================================
    # LEADERBOARD
    # =========================================================

    @bp.route("/kiosk/leaderboard")
    def kiosk_leaderboard():
        """
        Kiosk leaderboard page.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        participants = User.query.filter(
            User.is_active_account == True,
            or_(
                User.role == "user",
                (User.role == "admin") & (User.participation_enabled == True)
            )
        ).order_by(User.display_name).all()

        current_points = sorted(
            [{"user": u, "score": u.point_balance()} for u in participants],
            key=lambda x: x["score"], reverse=True
        )

        total_earned = sorted(
            [{"user": u, "score": calculate_total_earned(u)} for u in participants],
            key=lambda x: x["score"], reverse=True
        )

        from app.models import TaskCompletion as TC
        tasks_done = []
        for u in participants:
            count = TC.query.filter_by(user_id=u.id, status="approved").count()
            tasks_done.append({"user": u, "score": count})
        tasks_done = sorted(tasks_done, key=lambda x: x["score"], reverse=True)

        routines_done = []
        for u in participants:
            count = RoutineCompletion.query.filter_by(user_id=u.id).count()
            routines_done.append({"user": u, "score": count})
        routines_done = sorted(routines_done, key=lambda x: x["score"], reverse=True)

        return render_template(
            "kiosk_leaderboard.html",
            user=user,
            kiosk_user=user,
            current_points=current_points,
            total_earned=total_earned,
            tasks_done=tasks_done,
            routines_done=routines_done,
        )

    # =========================================================
    # GROUP GOALS
    # =========================================================

    @bp.route("/kiosk/goals")
    def kiosk_goals():
        """
        Kiosk group goals page.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        settings = get_household_settings()

        goals = GroupGoal.query.filter_by(
            is_active=True
        ).order_by(
            GroupGoal.created_at.desc()
        ).all()

        current_balance = user.point_balance()

        return render_template(
            "kiosk_goals.html",
            user=user,
            kiosk_user=user,
            goals=goals,
            current_balance=current_balance,
            group_goals_enabled=settings.group_goals_enabled
        )

    @bp.route("/kiosk/goals/<int:goal_id>/contribute", methods=["GET", "POST"])
    def kiosk_contribute_goal(goal_id):
        """
        Contribute points to a group goal from the kiosk.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        settings = get_household_settings()
        if not settings.group_goals_enabled:
            flash("Group goal contributions are currently disabled.")
            return redirect(url_for("main.kiosk_goals"))

        goal = db.session.get(GroupGoal, goal_id)
        if not goal or not goal.is_active or goal.status != "active":
            flash("Group goal not found or already completed.")
            return redirect(url_for("main.kiosk_goals"))

        current_balance = user.point_balance()
        error = None

        if request.method == "POST":
            try:
                amount = int(request.form.get("amount", "0"))
            except ValueError:
                amount = 0

            if amount < 1:
                error = "Please enter a valid amount (at least 1)."
            elif amount > current_balance:
                error = f"You only have {current_balance} {get_points_label()}."
            elif amount > goal.remaining_points():
                error = f"This goal only needs {goal.remaining_points()} more {get_points_label()}."
            else:
                contribution = GroupGoalContribution(
                    goal_id=goal.id,
                    user_id=user.id,
                    amount=amount,
                    status="active"
                )
                db.session.add(contribution)
                db.session.flush()

                transaction = PointTransaction(
                    user_id=user.id,
                    amount=-amount,
                    transaction_type="group_goal_contribution",
                    reason=f"Contributed to group goal: {goal.title}",
                    created_by_id=user.id
                )
                db.session.add(transaction)

                if goal.is_funded():
                    goal.status = "completed"
                    notify_admins(
                        title="Group goal funded",
                        message=f"'{goal.title}' has reached its target and is ready for fulfilment.",
                        notification_type="success",
                        action_url=url_for("main.group_goals"),
                        action_label="Open Group Goals"
                    )

                check_and_award_badges(user)
                db.session.commit()

                flash(f"Contributed {amount} {get_points_label()} to '{goal.title}'!")
                return redirect(url_for("main.kiosk_goals"))

        return render_template(
            "kiosk_goals_contribute.html",
            user=user,
            kiosk_user=user,
            goal=goal,
            current_balance=current_balance,
            error=error
        )

    # =========================================================
    # WISHLIST
    # =========================================================

    @bp.route("/kiosk/wishlist")
    def kiosk_wishlist():
        """
        Kiosk wishlist page — shows the user's own items and pending requests.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        settings = get_household_settings()

        wishlist_items = WishlistItem.query.filter(
            WishlistItem.user_id == user.id,
            WishlistItem.status.in_(["active", "funded"]),
            WishlistItem.is_active == True
        ).order_by(WishlistItem.created_at.desc()).all()

        pending_requests = WishlistRequest.query.filter_by(
            user_id=user.id,
            status="requested"
        ).order_by(WishlistRequest.created_at.desc()).all()

        current_balance = user.point_balance()

        return render_template(
            "kiosk_wishlist.html",
            user=user,
            kiosk_user=user,
            wishlist_items=wishlist_items,
            pending_requests=pending_requests,
            current_balance=current_balance,
            wishlist_requests_enabled=settings.wishlist_requests_enabled
        )

    @bp.route("/kiosk/wishlist/<int:item_id>/contribute", methods=["GET", "POST"])
    def kiosk_contribute_wishlist(item_id):
        """
        Contribute points toward a wishlist item from the kiosk.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        item = db.session.get(WishlistItem, item_id)

        if not item or item.user_id != user.id or not item.is_active or item.status != "active":
            flash("Wishlist item not found.")
            return redirect(url_for("main.kiosk_wishlist"))

        current_balance = user.point_balance()
        error = None

        if request.method == "POST":
            try:
                amount = int(request.form.get("amount", "0"))
            except ValueError:
                amount = 0

            if amount < 1:
                error = "Please enter a valid amount (at least 1)."
            elif amount > current_balance:
                error = f"You only have {current_balance} {get_points_label()}."
            elif amount > item.remaining_points():
                error = f"This item only needs {item.remaining_points()} more {get_points_label()}."
            else:
                contribution = WishlistContribution(
                    item_id=item.id,
                    user_id=user.id,
                    amount=amount,
                    status="active"
                )
                db.session.add(contribution)
                db.session.flush()

                transaction = PointTransaction(
                    user_id=user.id,
                    amount=-amount,
                    transaction_type="wishlist_contribution",
                    reason=f"Saved toward wishlist item: {item.name}",
                    created_by_id=user.id
                )
                db.session.add(transaction)

                if item.is_funded():
                    item.status = "funded"
                    from app.services.notification_service import create_notification
                    create_notification(
                        user_id=user.id,
                        title="Wishlist item funded",
                        message=f"'{item.name}' has reached its {get_points_label()} target!",
                        notification_type="success"
                    )
                    notify_admins(
                        title="Wishlist item funded",
                        message=f"{user.display_name}'s wishlist item '{item.name}' is fully funded.",
                        notification_type="success",
                        action_url=url_for("main.wishlist"),
                        action_label="Open Wishlist"
                    )

                check_and_award_badges(user)
                db.session.commit()

                flash(f"Saved {amount} {get_points_label()} toward '{item.name}'!")
                return redirect(url_for("main.kiosk_wishlist"))

        return render_template(
            "kiosk_wishlist_contribute.html",
            user=user,
            kiosk_user=user,
            item=item,
            current_balance=current_balance,
            error=error
        )

    @bp.route("/kiosk/wishlist/request", methods=["GET", "POST"])
    def kiosk_request_wishlist():
        """
        Submit a new wishlist item request from the kiosk.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        settings = get_household_settings()
        if not settings.wishlist_requests_enabled:
            flash("Wishlist requests are currently disabled.")
            return redirect(url_for("main.kiosk_wishlist"))

        error = None

        if request.method == "POST":
            name = request.form.get("requested_name", "").strip()
            description = request.form.get("requested_description", "").strip()

            if not name:
                error = "Please enter an item name."
            elif len(name) > 120:
                error = "Item name must be 120 characters or fewer."
            else:
                wishlist_request = WishlistRequest(
                    user_id=user.id,
                    requested_name=name,
                    requested_description=description or None,
                    status="requested"
                )
                db.session.add(wishlist_request)

                notify_admins(
                    title="New wishlist request",
                    message=f"{user.display_name} requested '{name}' to be added to their wishlist.",
                    notification_type="info",
                    action_url=url_for("main.wishlist"),
                    action_label="Review Wishlist"
                )

                db.session.commit()

                flash(f"Wishlist request for '{name}' submitted!")
                return redirect(url_for("main.kiosk_wishlist"))

        return render_template(
            "kiosk_wishlist_request.html",
            user=user,
            kiosk_user=user,
            error=error
        )

    # =========================================================
    # ROUTINES
    # =========================================================

    @bp.route("/kiosk/routines")
    def kiosk_routines():
        """
        Kiosk routines page — today's habits with streak info.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        today = date.today()

        active_routines = Routine.query.filter_by(is_active=True).filter(
            or_(
                Routine.assigned_user_id == None,
                Routine.assigned_user_id == user.id
            )
        ).order_by(Routine.title).all()

        routine_data = [
            {
                "routine": r,
                "completed_today": r.completed_today_by_user(user.id),
                "streak": r.current_streak_for_user(user.id)
            }
            for r in active_routines
        ]

        return render_template(
            "kiosk_routines.html",
            user=user,
            kiosk_user=user,
            routine_data=routine_data,
            today=today
        )

    @bp.route("/kiosk/routines/<int:routine_id>/complete", methods=["POST"])
    def kiosk_complete_routine(routine_id):
        """
        Mark a routine as complete for today from the kiosk.

        Awards points immediately — no admin approval needed.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        routine = db.session.get(Routine, routine_id)

        if not routine or not routine.is_active:
            flash("Routine not found.")
            return redirect(url_for("main.kiosk_routines"))

        if routine.assigned_user_id and routine.assigned_user_id != user.id:
            flash("This routine is assigned to another user.")
            return redirect(url_for("main.kiosk_routines"))

        today = date.today()

        existing = RoutineCompletion.query.filter_by(
            routine_id=routine.id,
            user_id=user.id,
            completed_date=today
        ).first()

        if existing:
            flash(f"You already completed '{routine.title}' today.")
            return redirect(url_for("main.kiosk_routines"))

        completion = RoutineCompletion(
            routine_id=routine.id,
            user_id=user.id,
            completed_date=today
        )
        db.session.add(completion)
        db.session.flush()

        if routine.point_value > 0:
            transaction = PointTransaction(
                user_id=user.id,
                amount=routine.point_value,
                transaction_type="routine_completed",
                reason=f"Routine completed: {routine.title}",
                created_by_id=user.id
            )
            db.session.add(transaction)

        db.session.commit()

        streak = routine.current_streak_for_user(user.id)
        msg = f"'{routine.title}' done!"
        if routine.point_value > 0:
            msg += f" +{routine.point_value} {get_points_label()}."
        if streak > 1:
            msg += f" {streak}-day streak! 🔥"

        flash(msg, "celebrate")
        return redirect(url_for("main.kiosk_routines"))

    # =========================================================
    # ADMIN APPROVALS
    # =========================================================

    @bp.route("/kiosk/approvals")
    def kiosk_approvals():
        """
        Admin-only kiosk approvals page.

        Shows pending task completions and reward requests so an admin can
        approve them directly from the home hub.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))
        if not user.is_admin():
            flash("Admin access required.")
            return redirect(url_for("main.kiosk_dashboard"))

        pending_tasks = TaskCompletion.query.filter_by(
            status="submitted"
        ).order_by(TaskCompletion.submitted_at.asc()).all()

        pending_rewards = RewardPurchase.query.filter_by(
            status="requested"
        ).order_by(RewardPurchase.requested_at.asc()).all()

        return render_template(
            "kiosk_approvals.html",
            user=user,
            kiosk_user=user,
            pending_tasks=pending_tasks,
            pending_rewards=pending_rewards
        )

    @bp.route("/kiosk/approvals/tasks/<int:completion_id>/approve", methods=["POST"])
    def kiosk_approve_task(completion_id):
        """
        Approve a task completion from the kiosk.
        """
        from datetime import timezone
        from app.services.notification_service import create_notification
        from app.services.badge_service import check_and_award_badges as _award_badges

        user = _kiosk_user()
        if not user or not user.is_admin():
            return redirect(url_for("main.kiosk_landing"))

        completion = db.session.get(TaskCompletion, completion_id)

        if not completion or completion.status != "submitted":
            flash("Task completion not found or already reviewed.")
            return redirect(url_for("main.kiosk_approvals"))

        completion.status = "approved"
        completion.reviewed_at = datetime.now(timezone.utc)
        completion.reviewed_by_id = user.id

        awarded_points = completion.task.total_point_value()

        transaction = PointTransaction(
            user_id=completion.user_id,
            amount=awarded_points,
            transaction_type="task_approved",
            reason=f"Approved task: {completion.task.title}",
            related_task_completion_id=completion.id,
            created_by_id=user.id
        )
        db.session.add(transaction)

        if completion.task.completion_behavior == "hide_after_approval":
            completion.task.is_active = False

        create_notification(
            user_id=completion.user_id,
            title="Task approved",
            message=f"'{completion.task.title}' was approved. You earned {awarded_points} {get_points_label()}.",
            notification_type="success"
        )
        _award_badges(completion.user)

        db.session.commit()

        flash(f"Approved '{completion.task.title}' for {completion.user.display_name}. +{awarded_points} {get_points_label()}.")
        return redirect(url_for("main.kiosk_approvals"))

    @bp.route("/kiosk/approvals/tasks/<int:completion_id>/reject", methods=["POST"])
    def kiosk_reject_task(completion_id):
        """
        Reject a task completion from the kiosk.
        """
        from datetime import timezone
        from app.services.notification_service import create_notification

        user = _kiosk_user()
        if not user or not user.is_admin():
            return redirect(url_for("main.kiosk_landing"))

        completion = db.session.get(TaskCompletion, completion_id)

        if not completion or completion.status != "submitted":
            flash("Task completion not found or already reviewed.")
            return redirect(url_for("main.kiosk_approvals"))

        completion.status = "rejected"
        completion.reviewed_at = datetime.now(timezone.utc)
        completion.reviewed_by_id = user.id
        completion.rejection_reason = "Rejected via kiosk."

        create_notification(
            user_id=completion.user_id,
            title="Task not approved",
            message=f"'{completion.task.title}' was not approved this time.",
            notification_type="warning"
        )

        db.session.commit()

        flash(f"Rejected '{completion.task.title}' for {completion.user.display_name}.")
        return redirect(url_for("main.kiosk_approvals"))

    @bp.route("/kiosk/approvals/rewards/<int:purchase_id>/approve", methods=["POST"])
    def kiosk_approve_reward(purchase_id):
        """
        Approve a reward purchase from the kiosk.
        """
        from datetime import timezone
        from app.services.notification_service import create_notification

        user = _kiosk_user()
        if not user or not user.is_admin():
            return redirect(url_for("main.kiosk_landing"))

        purchase = db.session.get(RewardPurchase, purchase_id)

        if not purchase or purchase.status != "requested":
            flash("Reward request not found or already reviewed.")
            return redirect(url_for("main.kiosk_approvals"))

        # Points were already reserved at request time; no extra deduction needed.
        # Create a fallback deduction only if there is no existing reservation.
        reservation = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_requested"
        ).first()

        if not reservation:
            if purchase.user.point_balance() < purchase.reward.point_cost:
                flash(f"{purchase.user.display_name} no longer has enough {get_points_label()}.")
                return redirect(url_for("main.kiosk_approvals"))

            fallback = PointTransaction(
                user_id=purchase.user_id,
                amount=-purchase.reward.point_cost,
                transaction_type="reward_approved",
                reason=f"Approved reward: {purchase.reward.name}",
                related_reward_purchase_id=purchase.id,
                created_by_id=user.id
            )
            db.session.add(fallback)

        purchase.status = "approved"
        purchase.reviewed_at = datetime.now(timezone.utc)
        purchase.reviewed_by_id = user.id

        create_notification(
            user_id=purchase.user_id,
            title="Reward approved",
            message=f"Your request for '{purchase.reward.name}' was approved.",
            notification_type="success"
        )

        db.session.commit()

        flash(f"Approved '{purchase.reward.name}' for {purchase.user.display_name}.")
        return redirect(url_for("main.kiosk_approvals"))

    @bp.route("/kiosk/approvals/rewards/<int:purchase_id>/reject", methods=["POST"])
    def kiosk_reject_reward(purchase_id):
        """
        Reject a reward purchase from the kiosk and refund reserved points.
        """
        from datetime import timezone
        from app.services.notification_service import create_notification
        from app.services.points_service import format_points

        user = _kiosk_user()
        if not user or not user.is_admin():
            return redirect(url_for("main.kiosk_landing"))

        purchase = db.session.get(RewardPurchase, purchase_id)

        if not purchase or purchase.status != "requested":
            flash("Reward request not found or already reviewed.")
            return redirect(url_for("main.kiosk_approvals"))

        # Refund reserved points (prevents double-refund).
        reservation = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_requested"
        ).first()
        existing_refund = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_refunded"
        ).first()

        if reservation and not existing_refund:
            refund = PointTransaction(
                user_id=purchase.user_id,
                amount=purchase.reward.point_cost,
                transaction_type="reward_refunded",
                reason=f"Refunded rejected reward: {purchase.reward.name}",
                related_reward_purchase_id=purchase.id,
                created_by_id=user.id
            )
            db.session.add(refund)

        purchase.status = "rejected"
        purchase.reviewed_at = datetime.now(timezone.utc)
        purchase.reviewed_by_id = user.id
        purchase.rejection_reason = "Rejected via kiosk."

        create_notification(
            user_id=purchase.user_id,
            title="Reward not approved",
            message=(
                f"Your request for '{purchase.reward.name}' was not approved. "
                f"{format_points(purchase.reward.point_cost)} have been refunded."
            ),
            notification_type="warning"
        )

        db.session.commit()

        flash(f"Rejected '{purchase.reward.name}' for {purchase.user.display_name}. {get_points_label().capitalize()} refunded.")
        return redirect(url_for("main.kiosk_approvals"))

    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    @bp.route("/kiosk/notifications")
    def kiosk_notifications():
        """
        Kiosk notifications page.

        Shows the user's notifications newest-first and marks them all read.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        notifications = (
            Notification.query
            .filter_by(user_id=user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
            .all()
        )

        # Mark all unread as read now that the user has seen them.
        Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
        db.session.commit()

        return render_template(
            "kiosk_notifications.html",
            user=user,
            kiosk_user=user,
            notifications=notifications,
        )

    # =========================================================
    # BADGES
    # =========================================================

    @bp.route("/kiosk/badges")
    def kiosk_badges():
        """
        Kiosk badges page.

        Shows badges the user has earned and locks those they haven't yet.
        """
        user = _kiosk_user()
        if not user:
            return redirect(url_for("main.kiosk_landing"))

        user_badges = (
            UserBadge.query
            .filter_by(user_id=user.id)
            .order_by(UserBadge.earned_at.desc())
            .all()
        )
        earned_badge_ids = {ub.badge_id for ub in user_badges}

        all_badges = Badge.query.order_by(Badge.name).all()

        return render_template(
            "kiosk_badges.html",
            user=user,
            kiosk_user=user,
            user_badges=user_badges,
            all_badges=all_badges,
            earned_badge_ids=earned_badge_ids,
        )
