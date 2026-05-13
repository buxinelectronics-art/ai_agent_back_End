from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Profile, User

profile_bp = Blueprint("profile", __name__)

FIELDS = [
    "phone","location","linkedin_url","github_url","portfolio_url",
    "skills","years_experience","preferred_roles","preferred_countries",
    "salary_expectation","work_preference","work_authorization",
    "education","experience_text"
]

@profile_bp.route("", methods=["GET"])
@jwt_required()
def get_profile():
    uid = int(get_jwt_identity())
    p   = Profile.query.filter_by(user_id=uid).first_or_404()
    u   = User.query.get(uid)
    return jsonify(
        name=u.name, email=u.email,
        **{f: getattr(p, f) for f in FIELDS},
        base_resume_path=p.base_resume_path,
        cover_letter_path=p.cover_letter_path,
    ), 200

@profile_bp.route("", methods=["PUT"])
@jwt_required()
def update_profile():
    uid  = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    p    = Profile.query.filter_by(user_id=uid).first_or_404()
    for f in FIELDS:
        if f in data: setattr(p, f, data[f])
    if "name" in data: User.query.get(uid).name = data["name"]
    db.session.commit()
    return jsonify(message="Profile updated"), 200
