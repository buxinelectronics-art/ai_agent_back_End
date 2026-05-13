from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, jwt, bcrypt
from routes.auth import auth_bp
from routes.profile import profile_bp
from routes.jobs import jobs_bp
from routes.resume import resume_bp
from routes.automation import automation_bp
from routes.applications import applications_bp
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": app.config["ALLOWED_ORIGINS"]}})
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    app.register_blueprint(auth_bp,         url_prefix="/api/auth")
    app.register_blueprint(profile_bp,      url_prefix="/api/profile")
    app.register_blueprint(jobs_bp,         url_prefix="/api/jobs")
    app.register_blueprint(resume_bp,       url_prefix="/api/resume")
    app.register_blueprint(automation_bp,   url_prefix="/api/automation")
    app.register_blueprint(applications_bp, url_prefix="/api/applications")

    @app.route("/api/health")
    def health():
        return jsonify(status="ok", model=app.config["GEMINI_MODEL"])

    with app.app_context():
        db.create_all()
        os.makedirs(app.config["UPLOAD_FOLDER"],    exist_ok=True)
        os.makedirs(app.config["GENERATED_FOLDER"], exist_ok=True)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
