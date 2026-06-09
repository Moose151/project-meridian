# Import os so the app can read environment variables from .env.
import os

# Load environment variables from the .env file.
from dotenv import load_dotenv

# Import Flask core.
from flask import Flask

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

    # Import and register routes.
    from app.routes import bp
    app.register_blueprint(bp)

    # Create database tables and seed required default data.
    with app.app_context():
        db.create_all()

        from app.services.seed_service import seed_default_data
        seed_default_data()

    return app