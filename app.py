import os
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, jwt, bcrypt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": app.config["ALLOWED_ORIGINS"]}})

    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.profile import profile_bp
    from routes.jobs import jobs_bp
    from routes.resume import resume_bp
    from routes.automation import automation_bp
    from routes.applications import applications_bp

    app.register_blueprint(auth_bp,          url_prefix="/api/auth")
    app.register_blueprint(profile_bp,       url_prefix="/api/profile")
    app.register_blueprint(jobs_bp,          url_prefix="/api/jobs")
    app.register_blueprint(resume_bp,        url_prefix="/api/resume")
    app.register_blueprint(automation_bp,    url_prefix="/api/automation")
    app.register_blueprint(applications_bp,  url_prefix="/api/applications")

    @app.route("/")
    def index():
        return jsonify(status="JobAgent API running", model=app.config.get("GEMINI_MODEL"))

    @app.route("/api/health")
    def health():
        return jsonify(status="ok", model=app.config.get("GEMINI_MODEL"))

    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database init error: {e}")

        try:
            os.makedirs(app.config["UPLOAD_FOLDER"],    exist_ok=True)
            os.makedirs(app.config["GENERATED_FOLDER"], exist_ok=True)
        except Exception as e:
            logger.error(f"Folder creation error: {e}")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
