# Import os so the app can read environment variables from .env.
import os
from datetime import timezone

# Load environment variables from the .env file.
from dotenv import load_dotenv

# Import Flask core.
from flask import Flask, jsonify, session

# Import SQLAlchemy for database handling.
from flask_sqlalchemy import SQLAlchemy

# Import LoginManager for login/session handling.
from flask_login import LoginManager

from flask_migrate import Migrate


# Create the database object.
# Models use this object to define tables.
db = SQLAlchemy()
migrate = Migrate()


# Create the login manager.
# Flask-Login uses this to manage logged-in users.
login_manager = LoginManager()


def create_app():
    """
    Flask application factory.

    This creates and configures the Project Meridian app.
    """

    # Load values from the .env file before creating the app.
    load_dotenv()

    # Create the Flask app.
    app = Flask(__name__)

    # Basic app configuration.
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "dev-secret-key-change-later"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///meridian.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Max upload size for task evidence photos (8 MB).
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    # Connect database to app.
    db.init_app(app)
    migrate.init_app(app, db)

    # Connect Flask-Login to app.
    login_manager.init_app(app)

    # Tell Flask-Login where to send users who are not logged in.
    login_manager.login_view = "main.login"

    # Import User here to avoid circular imports.
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        """
        Reload a user from the stored session ID.

        Flask-Login stores the user ID in the browser session.
        This function tells Flask-Login how to turn that ID back into a User.
        """

        return db.session.get(User, int(user_id))

    @app.template_filter("datetimeformat")
    def datetimeformat(value):
        """Format a UTC datetime as 'Mon, 13 Jan, 21:42' in local time."""
        if value is None:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        local = value.astimezone()
        return local.strftime("%-d %b %Y, %H:%M")

    # Import and register routes.
    from app.routes import bp

    # Context processor must be registered on the blueprint BEFORE
    # app.register_blueprint() is called, otherwise Flask raises an error.
    @bp.context_processor
    def inject_kiosk_unread():
        from app.models import Notification
        user_id = session.get("kiosk_user_id")
        if user_id:
            count = Notification.query.filter_by(
                user_id=user_id, is_read=False
            ).count()
            return {"kiosk_unread_count": count}
        return {"kiosk_unread_count": 0}

    app.register_blueprint(bp)

    # Health check endpoint — useful for Docker / reverse proxy health checks.
    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    # Create database tables, run column migrations, and seed default data.
    with app.app_context():
        db.create_all()

        # Ensure the evidence photo upload directory exists.
        upload_dir = os.path.join(app.root_path, "static", "uploads", "evidence")
        os.makedirs(upload_dir, exist_ok=True)

        from app.services.seed_service import run_column_migrations, seed_default_data
        run_column_migrations()
        seed_default_data()

    # Start background scheduler (DB backups, allowances).
    from app.services.scheduler_service import start_scheduler
    start_scheduler(app)

    return app
