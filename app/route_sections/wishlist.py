"""
Wishlist routes.

These routes are registered onto the existing main blueprint so endpoint names
such as main.wishlist and main.contribute_wishlist_item stay unchanged.
"""

import os
from datetime import datetime, timezone

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import (
    RejectionReasonForm,
    WishlistAdminItemForm,
    WishlistApproveForm,
    WishlistContributionForm,
    WishlistEditItemForm,
    WishlistRequestForm,
)
from app.models import (
    PointTransaction,
    User,
    WishlistContribution,
    WishlistItem,
    WishlistRequest,
)
from app.services.badge_service import check_and_award_badges
from app.services.notification_service import create_notification, notify_admins
from app.services.points_service import format_points
from app.services.settings_service import get_household_settings, get_points_label


_ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}


def _save_item_image(item_id, file):
    """Save a single uploaded image for a wishlist item. Returns filename or None."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_IMAGE_EXTS:
        return None
    upload_dir = os.path.join(
        current_app.root_path, "static", "uploads", "wishlist-items", str(item_id)
    )
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"image.{ext}"
    file.save(os.path.join(upload_dir, filename))
    return filename


def register_wishlist_routes(bp, admin_required):
    """
    Register wishlist routes.
    """

    @bp.route("/wishlist")
    @login_required
    def wishlist():
        """
        Wishlist page.
        """

        visible_item_statuses = [
            "active",
            "funded"
        ]

        visible_request_statuses = [
            "requested"
        ]

        if current_user.is_admin():
            wishlist_items = WishlistItem.query.filter(
                WishlistItem.status.in_(visible_item_statuses),
                WishlistItem.is_active == True
            ).order_by(
                WishlistItem.created_at.desc()
            ).all()

            wishlist_requests = WishlistRequest.query.filter(
                WishlistRequest.status.in_(visible_request_statuses)
            ).order_by(
                WishlistRequest.created_at.desc()
            ).limit(20).all()
        else:
            wishlist_items = WishlistItem.query.filter(
                WishlistItem.user_id == current_user.id,
                WishlistItem.status.in_(visible_item_statuses),
                WishlistItem.is_active == True
            ).order_by(
                WishlistItem.created_at.desc()
            ).all()

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
                price_estimate=form.price_estimate.data or None,
                store_url=form.store_url.data or None,
                image_url=form.image_url.data or None,
                status="active",
                is_active=True,
                created_by_id=current_user.id
            )

            db.session.add(item)
            db.session.flush()

            uploaded = request.files.get("image_file")
            filename = _save_item_image(item.id, uploaded)
            if filename:
                item.image_filename = filename

            create_notification(
                user_id=user.id,
                title="Wishlist item added",
                message=f"'{item.name}' was added to your wishlist for {format_points(item.point_cost)}.",
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
                price_estimate=form.price_estimate.data or None,
                store_url=form.store_url.data or None,
                image_url=form.image_url.data or None,
                status="active",
                is_active=True,
                created_by_id=current_user.id
            )

            db.session.add(item)
            db.session.flush()

            uploaded = request.files.get("image_file")
            filename = _save_item_image(item.id, uploaded)
            if filename:
                item.image_filename = filename

            wishlist_request.status = "approved"
            wishlist_request.reviewed_at = datetime.now(timezone.utc)
            wishlist_request.reviewed_by_id = current_user.id

            create_notification(
                user_id=wishlist_request.user_id,
                title="Wishlist request approved",
                message=f"'{item.name}' was added to your wishlist for {format_points(item.point_cost)}.",
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
            message=f"'{item.name}' was removed from your wishlist. Any saved {get_points_label()} were refunded.",
            notification_type="warning"
        )

        db.session.commit()

        flash(f"Wishlist item removed and saved {get_points_label()} refunded.")
        return redirect(url_for("main.wishlist"))

    @bp.route("/wishlist/items/<int:item_id>/contribute", methods=["GET", "POST"])
    @login_required
    def contribute_wishlist_item(item_id):
        """
        Allow a standard user to contribute points toward one of their wishlist
        items.
        """

        if not current_user.can_participate():
            flash("Enable participation mode to contribute to wishlist items.")
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
                flash(f"You do not have enough {get_points_label()} to contribute that amount.")
                return redirect(url_for("main.contribute_wishlist_item", item_id=item.id))

            if amount > item.remaining_points():
                flash(f"This wishlist item only needs {format_points(item.remaining_points())} more.")
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
                reason=f"Saved toward wishlist item: {item.name}",
                created_by_id=current_user.id
            )

            db.session.add(transaction)

            if item.is_funded():
                item.status = "funded"

                create_notification(
                    user_id=current_user.id,
                    title="Wishlist item funded",
                    message=f"Your wishlist item '{item.name}' has reached its {get_points_label()} target.",
                    notification_type="success"
                )

                notify_admins(
                    title="Wishlist item funded",
                    message=f"{current_user.display_name}'s wishlist item '{item.name}' is now fully funded and ready for fulfilment.",
                    notification_type="success",
                    action_url=url_for("main.wishlist"),
                    action_label="Open Wishlist"
                )

            check_and_award_badges(current_user)

            db.session.commit()

            flash(f"{get_points_label().capitalize()} added to wishlist item.")
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
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        item = db.session.get(WishlistItem, item_id)

        if not item:
            flash("Wishlist item not found.")
            return redirect(url_for("main.wishlist"))

        if not item.is_active or item.status == "removed":
            flash("Removed wishlist items cannot be fulfilled.")
            return redirect(url_for("main.wishlist"))

        if not item.is_funded():
            flash(f"This wishlist item has not reached its {get_points_label()} target yet.")
            return redirect(url_for("main.wishlist"))

        item.status = "fulfilled"
        item.is_active = False

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
        """

        if not admin_required():
            return redirect(url_for("main.dashboard"))

        item = db.session.get(WishlistItem, item_id)

        if not item:
            flash("Wishlist item not found.")
            return redirect(url_for("main.wishlist"))

        if item.status in ["removed", "fulfilled"]:
            flash("Removed or fulfilled wishlist items cannot be edited.")
            return redirect(url_for("main.wishlist"))

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

        if request.method == "GET":
            form.user_id.data = item.user_id
            form.name.data = item.name
            form.description.data = item.description
            form.point_cost.data = item.point_cost
            form.price_estimate.data = item.price_estimate
            form.store_url.data = item.store_url
            form.image_url.data = item.image_url

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
            item.price_estimate = form.price_estimate.data or None
            item.store_url = form.store_url.data or None
            item.image_url = form.image_url.data or None

            uploaded = request.files.get("image_file")
            filename = _save_item_image(item.id, uploaded)
            if filename:
                item.image_filename = filename

            if request.form.get("clear_image"):
                item.image_filename = None
                item.image_url = None

            if item.is_funded():
                item.status = "funded"
            else:
                item.status = "active"

            create_notification(
                user_id=item.user_id,
                title="Wishlist item updated",
                message=f"Your wishlist item '{item.name}' was updated by an admin.",
                notification_type="info",
                action_url=url_for("main.wishlist"),
                action_label="Open Wishlist"
            )

            if old_user_id != item.user_id:
                create_notification(
                    user_id=old_user_id,
                    title="Wishlist item reassigned",
                    message=f"The wishlist item '{item.name}' was moved to another user.",
                    notification_type="warning"
                )

            if old_point_cost != item.point_cost:
                create_notification(
                    user_id=item.user_id,
                    title="Wishlist cost changed",
                    message=f"'{item.name}' changed from {format_points(old_point_cost)} to {format_points(item.point_cost)}.",
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
