import os
from flask import Flask, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Initialize extensions
bcrypt = Bcrypt()
login_manager = LoginManager()
from app.models import db

# Setup login manager redirects
login_manager.login_view = 'main_index'
login_manager.login_message_category = 'warning'

def create_app():
    app = Flask(__name__)
    
    # Configure app settings
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key')
    
    # Fallback to local SQLite if DATABASE_URL is not configured
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///healthcare.db')
    # PostgreSQL standard correction (render often injects postgres:// but SQLAlchemy requires postgresql://)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Bind extensions
    from app.models import db, User
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprint routes
    from app.patient.routes import patient_bp
    from app.doctor.routes import doctor_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(patient_bp, url_prefix='/patient')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Main system routes (Landing Page & Shared routes)
    @app.route('/')
    def main_index():
        from flask import render_template
        return render_template('index.html')

    # Initialize APScheduler for automated 24hr email reminders
    from app.email_service import init_scheduler
    # To prevent APScheduler from running multiple times in Flask reload debug mode
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_scheduler(app)

    return app
