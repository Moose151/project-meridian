# Import Flask helpers.
from flask import Blueprint

# Import Flask-Login helpers.
from flask_login import current_user

from app.route_sections.activity import register_activity_routes
from app.route_sections.admin_exports import register_admin_export_routes
from app.route_sections.admin_home import register_admin_home_routes
from app.route_sections.approvals import register_approval_routes
from app.route_sections.auth import register_auth_routes
from app.route_sections.categories import register_category_routes
from app.route_sections.dashboard import register_dashboard_routes
from app.route_sections.group_goals import register_group_goal_routes
from app.route_sections.leaderboard import register_leaderboard_routes
from app.route_sections.profiles import register_profile_routes
from app.route_sections.request_archive import register_request_archive_routes
from app.route_sections.rewards import register_reward_routes
from app.route_sections.routines import register_routine_routes
from app.route_sections.settings import register_settings_routes
from app.route_sections.tasks import register_task_routes
from app.route_sections.users import register_user_routes
from app.route_sections.wishlist import register_wishlist_routes

from app.services.settings_service import get_household_settings

# Create the main blueprint.
# All routes in this app are registered under this blueprint.
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
    Helper for admin-only pages.

    Returns True if the current user is an admin.
    Returns False and flashes a message if not.
    """

    if not current_user.is_authenticated or not current_user.is_admin():
        from flask import flash
        flash("Admin access required.")
        return False

    return True


register_activity_routes(bp)
register_admin_export_routes(bp, admin_required)
register_admin_home_routes(bp, admin_required)
register_approval_routes(bp, admin_required)
register_auth_routes(bp)
register_category_routes(bp, admin_required)
register_dashboard_routes(bp)
register_group_goal_routes(bp, admin_required)
register_leaderboard_routes(bp)
register_profile_routes(bp, admin_required)
register_request_archive_routes(bp)
register_reward_routes(bp, admin_required)
register_routine_routes(bp, admin_required)
register_settings_routes(bp, admin_required)
register_task_routes(bp, admin_required)
register_user_routes(bp, admin_required)
register_wishlist_routes(bp, admin_required)
