"""
Reward routes: shop, reward creation, purchase requests, and management.

Registered onto the existing main blueprint to preserve all endpoint names.
"""

from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import RewardForm
from app.models import PointTransaction, Reward, RewardCategory, RewardPurchase
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
        status_label = "Active" if reward.is_active else "Archived"
        choices.append((reward.id, f"{reward.name} ({status_label})"))

    return choices


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

        Shows active rewards only.

        Optional filter:
        - category
        """

        selected_category = request.args.get("category", "")

        reward_query = Reward.query.filter_by(is_active=True)

        if selected_category:
            reward_query = reward_query.filter_by(category=selected_category)

        rewards = reward_query.order_by(
            Reward.category,
            Reward.point_cost,
            Reward.name
        ).all()

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

        Admins can either create a reward manually or import details from a
        previous reward and then edit before saving.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        form = RewardForm()
        form.category.choices = _reward_category_choices()
        form.import_reward_id.choices = _reward_import_choices()

        # Allow importing from a URL such as /rewards/create?import_reward_id=5
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

        # If admin clicked the Import button, pre-fill form and re-render.
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

            return render_template("create_reward.html", form=form)

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

        return render_template("create_reward.html", form=form)

    @bp.route("/shop/<int:reward_id>/request", methods=["POST"])
    @login_required
    def request_reward(reward_id):
        """
        Standard user route for requesting a reward.

        Points are reserved immediately when the reward is requested.
        If the request is cancelled or rejected, the points are refunded.
        If the request is approved, no further deduction is needed.
        """

        if current_user.is_admin():
            flash("Admins do not request rewards.")
            return redirect(url_for("main.shop"))

        reward = db.session.get(Reward, reward_id)

        if not reward or not reward.is_active:
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

        # Flush to get purchase.id before creating the linked point transaction.
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

        if current_user.is_admin():
            flash("Admins do not cancel reward requests.")
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

        # Prevent accidental double refunds.
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
    # REWARD MANAGEMENT: EDIT, HIDE, RESTORE, DELETE
    # =========================================================

    @bp.route("/admin/rewards/manage")
    @login_required
    def manage_rewards():
        """
        Admin-only reward management page.

        Shows active and hidden rewards.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        all_rewards = Reward.query.order_by(Reward.created_at.desc()).all()

        return render_template("manage_rewards.html", rewards=all_rewards)

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

        # Include the reward's current category in case it has been removed.
        form.category.choices = _reward_category_choices(reward.category)

        if form.validate_on_submit():
            reward.name = form.name.data
            reward.description = form.description.data
            reward.category = form.category.data or None
            reward.point_cost = form.point_cost.data

            db.session.commit()

            flash("Reward updated.")
            return redirect(url_for("main.manage_rewards"))

        return render_template("edit_reward.html", form=form, reward=reward)

    @bp.route("/admin/rewards/<int:reward_id>/hide", methods=["POST"])
    @login_required
    def hide_reward(reward_id):
        """
        Hide an active reward.
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

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

        if not admin_required():
            return redirect(url_for("main.dashboard"))

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

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        reward = db.session.get(Reward, reward_id)

        if not reward:
            flash("Reward not found.")
            return redirect(url_for("main.manage_rewards"))

        if reward.purchases:
            reward.is_active = False
            db.session.commit()

            flash("This reward has history, so it cannot be deleted. It has been hidden instead.")
            return redirect(url_for("main.manage_rewards"))

        db.session.delete(reward)
        db.session.commit()

        flash("Unused reward deleted.")
        return redirect(url_for("main.manage_rewards"))
