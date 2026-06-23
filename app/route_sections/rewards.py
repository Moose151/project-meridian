"""
Reward routes: shop, reward creation, purchase requests, and management.

Registered onto the existing main blueprint to preserve all endpoint names.
"""

import json
import os
from datetime import date, datetime, timezone

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import RewardForm
from app.models import PointTransaction, Reward, RewardCategory, RewardImage, RewardPurchase
from app.services.settings_service import get_points_label
from app.services.reward_service import create_reward_reservation


def _reward_category_choices(include_current=None):
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


def _reward_import_choices():
    """
    Build dropdown choices for importing a previous reward.

    Includes active and archived rewards so admins can quickly duplicate
    any reward that has existed before.
    """

    rewards = Reward.query.order_by(Reward.name).all()

    choices = [(0, "Do not import")]

    for reward in rewards:
        status_label = "Active" if reward.is_active else "Hidden/Archived"
        choices.append((reward.id, f"{reward.name} ({status_label})"))

    return choices


_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}


def _save_reward_images(reward, files):
    """Save uploaded image files for a reward and attach RewardImage records."""
    upload_dir = os.path.join(
        current_app.root_path, "static", "uploads", "rewards", str(reward.id)
    )
    os.makedirs(upload_dir, exist_ok=True)
    next_order = max((img.sort_order for img in reward.images), default=-1) + 1

    for f in files:
        if not f or not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in _ALLOWED_IMAGE_EXTS:
            continue
        filename = f"{reward.id}_{next_order}.{ext}"
        f.save(os.path.join(upload_dir, filename))
        db.session.add(RewardImage(
            reward_id=reward.id,
            filename=filename,
            sort_order=next_order
        ))
        next_order += 1


def _get_cart():
    """Return cart as {reward_id (int): quantity (int)}, migrating old list format."""
    raw = session.get("shop_cart", {})
    if isinstance(raw, list):
        # Migrate old list-of-ids format
        migrated = {}
        for rid in raw:
            migrated[str(rid)] = migrated.get(str(rid), 0) + 1
        session["shop_cart"] = migrated
        return migrated
    return raw


def _save_cart(cart):
    session["shop_cart"] = cart


def _cart_total_qty(cart):
    return sum(cart.values())


def _today_midnight_utc():
    """Return today's local midnight as a UTC-aware datetime for daily limit queries."""
    today = date.today()
    midnight_naive = datetime(today.year, today.month, today.day, 0, 0, 0)
    # Convert naive local time to UTC using the system offset
    local_now = datetime.now()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    offset = utc_now - local_now
    midnight_utc = midnight_naive + offset
    return midnight_utc.replace(tzinfo=timezone.utc)


def register_reward_routes(bp, admin_required):
    """
    Register reward shop, purchase, management, and admin edit routes.
    """

    # =========================================================
    # SHOP AND REWARD REQUESTS
    # =========================================================

    @bp.route("/shop")
    @login_required
    def shop():
        """
        Reward shop page.

        Regular users see only active, non-archived rewards.
        Admins see all non-archived rewards; hidden ones are greyed out.

        Optional filters:
        - category
        - visibility (admin only: all / active / hidden)
        """

        selected_category = request.args.get("category", "")
        selected_visibility = request.args.get("visibility", "active")

        reward_query = Reward.query.filter_by(is_archived=False)

        if current_user.is_admin():
            if selected_visibility == "active":
                reward_query = reward_query.filter_by(is_active=True)
            elif selected_visibility == "hidden":
                reward_query = reward_query.filter_by(is_active=False)
            # "all" shows both
        else:
            reward_query = reward_query.filter_by(is_active=True)

        if selected_category:
            reward_query = reward_query.filter_by(category=selected_category)

        rewards = reward_query.order_by(
            Reward.category,
            Reward.point_cost,
            Reward.name
        ).all()

        # For users: filter out out-of-stock rewards that should disappear.
        if not current_user.is_admin():
            def _is_available(r):
                stock = r.remaining_stock()
                if stock is not None and stock <= 0 and r.disappear_when_empty:
                    return False
                return True
            rewards = [r for r in rewards if _is_available(r)]

        categories = [
            category.name
            for category in RewardCategory.query.filter_by(
                is_active=True
            ).order_by(
                RewardCategory.name
            ).all()
        ]

        cart = _get_cart()

        # Build per-reward info for the template.
        reward_info = {}
        if not current_user.is_admin():
            for r in rewards:
                reward_info[r.id] = {
                    "remaining_stock": r.remaining_stock(),
                    "daily_remaining": r.daily_remaining_for_user(current_user.id),
                    "cart_qty": int(cart.get(str(r.id), 0)),
                }

        requested_reward_ids = set()
        if not current_user.is_admin():
            requested_reward_ids = {
                row[0] for row in db.session.query(RewardPurchase.reward_id).filter_by(
                    user_id=current_user.id,
                    status="requested"
                ).all()
            }

        return render_template(
            "shop.html",
            rewards=rewards,
            categories=categories,
            selected_category=selected_category,
            selected_visibility=selected_visibility,
            cart=cart,
            reward_info=reward_info,
            requested_reward_ids=requested_reward_ids,
        )

    @bp.route("/rewards/create", methods=["GET", "POST"])
    @login_required
    def create_reward():
        """
        Admin-only page for creating a new reward.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = RewardForm()
        form.category.choices = _reward_category_choices()
        form.import_reward_id.choices = _reward_import_choices()

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
                    form.quantity.data = imported_reward.quantity
                    form.allow_multiple_in_cart.data = imported_reward.allow_multiple_in_cart
                    form.disappear_when_empty.data = imported_reward.disappear_when_empty
                    form.daily_limit_per_user.data = imported_reward.daily_limit_per_user

                    flash("Reward imported. Review the details, then save when ready.")

        if request.method == "POST" and request.form.get("import_action") == "1":
            imported_reward = db.session.get(Reward, form.import_reward_id.data)

            if not imported_reward:
                flash("Selected reward could not be imported.")
                return redirect(url_for("main.create_reward"))

            form.name.data = imported_reward.name
            form.description.data = imported_reward.description
            form.point_cost.data = imported_reward.point_cost
            form.category.data = imported_reward.category
            form.quantity.data = imported_reward.quantity
            form.allow_multiple_in_cart.data = imported_reward.allow_multiple_in_cart
            form.disappear_when_empty.data = imported_reward.disappear_when_empty
            form.daily_limit_per_user.data = imported_reward.daily_limit_per_user

            flash("Reward imported. Review the details, then save when ready.")

            return render_template("create_reward.html", form=form)

        if form.validate_on_submit():
            reward = Reward(
                name=form.name.data,
                description=form.description.data,
                point_cost=form.point_cost.data,
                category=form.category.data or None,
                is_active=form.is_active.data,
                price_estimate=form.price_estimate.data or None,
                store_url=form.store_url.data or None,
                image_url=form.image_url.data or None,
                quantity=form.quantity.data if form.quantity.data is not None else None,
                allow_multiple_in_cart=form.allow_multiple_in_cart.data,
                disappear_when_empty=form.disappear_when_empty.data,
                daily_limit_per_user=form.daily_limit_per_user.data if form.daily_limit_per_user.data else None,
            )

            db.session.add(reward)
            db.session.flush()

            uploaded_files = request.files.getlist("reward_images")
            _save_reward_images(reward, uploaded_files)

            db.session.commit()

            flash("Reward created.")
            return redirect(url_for("main.manage_rewards"))

        return render_template("create_reward.html", form=form)

    @bp.route("/shop/<int:reward_id>/request", methods=["POST"])
    @login_required
    def request_reward(reward_id):
        """
        Standard user route for requesting a single reward (legacy direct-request flow).

        Points are reserved immediately when the reward is requested.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to request rewards.")
            return redirect(url_for("main.shop"))

        reward = db.session.get(Reward, reward_id)

        if not reward or not reward.is_active or reward.is_archived:
            flash("Reward not found.")
            return redirect(url_for("main.shop"))

        existing_request = RewardPurchase.query.filter_by(
            reward_id=reward.id,
            user_id=current_user.id,
            status="requested"
        ).first()

        if existing_request:
            flash("You already have a pending request for this reward.")
            return redirect(url_for("main.shop"))

        if current_user.point_balance() < reward.point_cost:
            flash(f"You do not have enough {get_points_label()} for this reward.")
            return redirect(url_for("main.shop"))

        purchase = RewardPurchase(
            reward_id=reward.id,
            user_id=current_user.id,
            status="requested"
        )

        db.session.add(purchase)
        db.session.flush()
        create_reward_reservation(purchase)
        db.session.commit()

        flash(f"Reward requested. {get_points_label().capitalize()} have been reserved pending approval.")
        return redirect(url_for("main.dashboard"))

    @bp.route("/shop/requests/<int:purchase_id>/cancel", methods=["POST"])
    @login_required
    def cancel_reward_request(purchase_id):
        """
        Allow a standard user to cancel their own pending reward request.

        If points were reserved, they are refunded.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to manage reward requests.")
            return redirect(url_for("main.reward_history"))

        purchase = db.session.get(RewardPurchase, purchase_id)

        if not purchase:
            flash("Reward request not found.")
            return redirect(url_for("main.reward_history"))

        if purchase.user_id != current_user.id:
            flash("You can only cancel your own reward requests.")
            return redirect(url_for("main.reward_history"))

        if purchase.status != "requested":
            flash("This reward request can no longer be cancelled.")
            return redirect(url_for("main.reward_history"))

        reservation = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_requested"
        ).first()

        existing_refund = PointTransaction.query.filter_by(
            related_reward_purchase_id=purchase.id,
            transaction_type="reward_cancelled_refund"
        ).first()

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

        purchase.status = "cancelled"
        purchase.reviewed_at = datetime.now(timezone.utc)
        purchase.rejection_reason = "Cancelled by user."

        db.session.commit()

        flash("Reward request cancelled and reserved balance refunded.")
        return redirect(url_for("main.reward_history"))

    # =========================================================
    # CART
    # =========================================================

    @bp.route("/shop/cart")
    @login_required
    def shop_cart():
        """
        Cart view — shows rewards the user has added to their cart.
        """
        if not current_user.can_participate():
            return redirect(url_for("main.shop"))

        cart = _get_cart()
        cart_items = []
        total_cost = 0

        for rid_str, qty in list(cart.items()):
            rid = int(rid_str)
            r = db.session.get(Reward, rid)
            if r and r.is_active and not r.is_archived:
                cart_items.append((r, qty))
                total_cost += r.point_cost * qty
            else:
                # Remove stale cart entries
                cart.pop(rid_str, None)

        _save_cart(cart)

        balance = current_user.point_balance()

        return render_template(
            "shop_cart.html",
            cart_items=cart_items,
            total_cost=total_cost,
            balance=balance,
        )

    @bp.route("/shop/cart/add/<int:reward_id>", methods=["POST"])
    @login_required
    def cart_add(reward_id):
        """Add a reward to the session cart, respecting daily limit and stock."""
        if not current_user.can_participate():
            return redirect(url_for("main.shop"))

        reward = db.session.get(Reward, reward_id)
        if not reward or not reward.is_active or reward.is_archived:
            flash("Reward not found.")
            return redirect(url_for("main.shop"))

        qty_requested = request.form.get("quantity", 1, type=int)
        if qty_requested < 1:
            qty_requested = 1

        if not reward.allow_multiple_in_cart:
            qty_requested = 1

        cart = _get_cart()
        current_in_cart = int(cart.get(str(reward_id), 0))

        # Check daily limit
        daily_rem = reward.daily_remaining_for_user(current_user.id)
        if daily_rem is not None:
            already_today = reward.daily_used_by_user(current_user.id)
            already_in_cart = current_in_cart
            total_today = already_today + already_in_cart + qty_requested
            if total_today > reward.daily_limit_per_user:
                allowed = reward.daily_limit_per_user - already_today - already_in_cart
                if allowed <= 0:
                    flash(f"You've reached your daily limit for '{reward.name}'.")
                    return redirect(request.referrer or url_for("main.shop"))
                qty_requested = allowed

        # Check stock
        stock = reward.remaining_stock()
        if stock is not None:
            in_cart_already = current_in_cart
            if in_cart_already + qty_requested > stock:
                allowed = stock - in_cart_already
                if allowed <= 0:
                    flash(f"'{reward.name}' is out of stock.")
                    return redirect(request.referrer or url_for("main.shop"))
                qty_requested = allowed

        new_qty = current_in_cart + qty_requested
        if new_qty <= 0:
            cart.pop(str(reward_id), None)
        else:
            cart[str(reward_id)] = new_qty

        _save_cart(cart)

        if qty_requested > 1:
            flash(f"Added {qty_requested}× '{reward.name}' to cart.")
        else:
            flash(f"'{reward.name}' added to cart.")

        return redirect(request.referrer or url_for("main.shop"))

    @bp.route("/shop/cart/remove/<int:reward_id>", methods=["POST"])
    @login_required
    def cart_remove(reward_id):
        """Remove a reward from the session cart."""
        cart = _get_cart()
        cart.pop(str(reward_id), None)
        _save_cart(cart)
        return redirect(url_for("main.shop_cart"))

    @bp.route("/shop/cart/checkout", methods=["POST"])
    @login_required
    def shop_checkout():
        """
        Process all items in the cart as reward purchase requests.

        For each item, creates one RewardPurchase per unit so each can be
        individually approved or rejected. Daily limits are enforced at
        checkout (pending + approved count toward the limit).
        """
        if not current_user.can_participate():
            return redirect(url_for("main.shop"))

        cart = _get_cart()
        if not cart:
            flash("Your cart is empty.")
            return redirect(url_for("main.shop"))

        midnight_utc = _today_midnight_utc()
        requested = []
        skipped = []

        for rid_str, qty in list(cart.items()):
            rid = int(rid_str)
            reward = db.session.get(Reward, rid)

            if not reward or not reward.is_active or reward.is_archived:
                skipped.append(rid_str)
                continue

            # Enforce daily limit per unit
            if reward.daily_limit_per_user is not None:
                used_today = RewardPurchase.query.filter(
                    RewardPurchase.reward_id == rid,
                    RewardPurchase.user_id == current_user.id,
                    RewardPurchase.status.in_(["requested", "approved", "fulfilled"]),
                    RewardPurchase.requested_at >= midnight_utc
                ).count()
                allowed = reward.daily_limit_per_user - used_today
                if allowed <= 0:
                    flash(f"Daily limit reached for '{reward.name}' — skipped.")
                    skipped.append(rid_str)
                    continue
                qty = min(qty, allowed)

            # Check stock (count all non-cancelled/rejected purchases)
            if reward.quantity is not None:
                used_total = RewardPurchase.query.filter(
                    RewardPurchase.reward_id == rid,
                    RewardPurchase.status.in_(["requested", "approved", "fulfilled"])
                ).count()
                remaining = reward.quantity - used_total
                if remaining <= 0:
                    flash(f"'{reward.name}' is out of stock — skipped.")
                    skipped.append(rid_str)
                    continue
                qty = min(qty, remaining)

            # Create one purchase record per unit
            unit_names = []
            for _ in range(qty):
                if current_user.point_balance() < reward.point_cost:
                    flash(f"Not enough {get_points_label()} for '{reward.name}' — some units skipped.")
                    break

                purchase = RewardPurchase(
                    reward_id=reward.id,
                    user_id=current_user.id,
                    status="requested"
                )
                db.session.add(purchase)
                db.session.flush()
                create_reward_reservation(purchase)
                unit_names.append(reward.name)

            if unit_names:
                if len(unit_names) > 1:
                    requested.append(f"{reward.name} ×{len(unit_names)}")
                else:
                    requested.append(reward.name)

        db.session.commit()
        _save_cart({})

        if requested:
            flash(f"Requested: {', '.join(requested)}. {get_points_label().capitalize()} reserved pending approval.")
        return redirect(url_for("main.reward_history"))

    # =========================================================
    # REWARD MANAGEMENT: EDIT, HIDE, RESTORE, ARCHIVE, DELETE
    # =========================================================

    @bp.route("/admin/rewards/manage")
    @login_required
    def manage_rewards():
        """
        Admin-only reward management page.

        Shows active and hidden rewards by default.
        Archived rewards only shown when show=archived.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        show = request.args.get("show", "active")

        if show == "archived":
            rewards = Reward.query.filter_by(is_archived=True).order_by(Reward.created_at.desc()).all()
        elif show == "hidden":
            rewards = Reward.query.filter_by(is_active=False, is_archived=False).order_by(Reward.created_at.desc()).all()
        else:
            rewards = Reward.query.filter_by(is_archived=False).order_by(Reward.created_at.desc()).all()

        return render_template("manage_rewards.html", rewards=rewards, show=show)

    @bp.route("/admin/rewards/<int:reward_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_reward(reward_id):
        """
        Admin-only page for editing an existing reward.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        form = RewardForm(obj=reward)
        form.category.choices = _reward_category_choices(reward.category)

        if form.validate_on_submit():
            reward.name = form.name.data
            reward.description = form.description.data
            reward.category = form.category.data or None
            reward.point_cost = form.point_cost.data
            reward.is_active = form.is_active.data
            reward.price_estimate = form.price_estimate.data or None
            reward.store_url = form.store_url.data or None
            reward.image_url = form.image_url.data or None
            reward.quantity = form.quantity.data if form.quantity.data is not None else None
            reward.allow_multiple_in_cart = form.allow_multiple_in_cart.data
            reward.disappear_when_empty = form.disappear_when_empty.data
            reward.daily_limit_per_user = form.daily_limit_per_user.data if form.daily_limit_per_user.data else None

            # Handle image deletions (checkboxes posted as delete_image_<id>).
            for key in request.form:
                if key.startswith("delete_image_"):
                    try:
                        img_id = int(key.split("_")[-1])
                    except ValueError:
                        continue
                    img = db.session.get(RewardImage, img_id)
                    if img and img.reward_id == reward.id:
                        upload_dir = os.path.join(
                            current_app.root_path, "static", "uploads", "rewards", str(reward.id)
                        )
                        try:
                            os.remove(os.path.join(upload_dir, img.filename))
                        except OSError:
                            pass
                        db.session.delete(img)

            uploaded_files = request.files.getlist("reward_images")
            _save_reward_images(reward, uploaded_files)

            db.session.commit()

            flash("Reward updated.")
            return redirect(url_for("main.manage_rewards"))

        return render_template("edit_reward.html", form=form, reward=reward)

    @bp.route("/admin/rewards/<int:reward_id>/hide", methods=["POST"])
    @login_required
    def hide_reward(reward_id):
        """Hide an active reward."""

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        reward.is_active = False
        db.session.commit()

        flash("Reward hidden.")
        return redirect(request.referrer or url_for("main.manage_rewards"))

    @bp.route("/admin/rewards/<int:reward_id>/restore", methods=["POST"])
    @login_required
    def restore_reward(reward_id):
        """Restore a hidden reward."""

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        reward.is_active = True
        db.session.commit()

        flash("Reward restored.")
        return redirect(request.referrer or url_for("main.manage_rewards"))

    @bp.route("/admin/rewards/<int:reward_id>/toggle-visible", methods=["POST"])
    @login_required
    def toggle_reward_visible(reward_id):
        """Quick toggle of a reward's user-facing visibility."""

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        reward.is_active = not reward.is_active
        db.session.commit()

        flash(f"Reward {'made visible' if reward.is_active else 'hidden'}.")
        return redirect(request.referrer or url_for("main.manage_rewards"))

    @bp.route("/admin/rewards/<int:reward_id>/archive", methods=["POST"])
    @login_required
    def archive_reward(reward_id):
        """Archive a reward — removes it from all views until unarchived."""

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        reward.is_archived = True
        reward.is_active = False
        db.session.commit()

        flash("Reward archived.")
        return redirect(url_for("main.manage_rewards"))

    @bp.route("/admin/rewards/<int:reward_id>/unarchive", methods=["POST"])
    @login_required
    def unarchive_reward(reward_id):
        """Restore an archived reward (stays hidden until made active)."""

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards", show="archived"))

        reward.is_archived = False
        db.session.commit()

        flash("Reward unarchived. It is currently hidden — make it visible to show it in the shop.")
        return redirect(url_for("main.manage_rewards", show="archived"))

    @bp.route("/admin/rewards/<int:reward_id>/delete", methods=["POST"])
    @login_required
    def delete_reward(reward_id):
        """
        Delete a reward only if it has no purchase history.

        If it has history, archive it instead.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        if reward.purchases:
            reward.is_active = False
            reward.is_archived = True
            db.session.commit()

            flash("This reward has history, so it cannot be deleted. It has been archived instead.")
            return redirect(url_for("main.manage_rewards"))

        # Delete associated images from disk
        upload_dir = os.path.join(
            current_app.root_path, "static", "uploads", "rewards", str(reward.id)
        )
        for img in list(reward.images):
            try:
                os.remove(os.path.join(upload_dir, img.filename))
            except OSError:
                pass

        db.session.delete(reward)
        db.session.commit()

        flash("Unused reward deleted.")
        return redirect(url_for("main.manage_rewards"))
