from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from extensions import db, bcrypt
from models import User, Profile, AutomationSettings
import re

auth_bp = Blueprint("auth", __name__)
BLOCKLIST = set()

def valid_email(e):
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", e))

@auth_bp.route("/register", methods=["POST"])
def register():
    d = request.get_json(silent=True) or {}
    name     = (d.get("name") or "").strip()
    email    = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    if not name:             return jsonify(error="Name required"), 400
    if not valid_email(email): return jsonify(error="Invalid email"), 400
    if len(password) < 8:   return jsonify(error="Password min 8 chars"), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="Email already registered"), 409
    pw = bcrypt.generate_password_hash(password).decode()
    u  = User(name=name, email=email, password_hash=pw)
    db.session.add(u); db.session.flush()
    db.session.add(Profile(user_id=u.id))
    db.session.add(AutomationSettings(user_id=u.id))
    db.session.commit()
    return jsonify(
        message="Account created",
        access_token=create_access_token(identity=str(u.id)),
        refresh_token=create_refresh_token(identity=str(u.id)),
        user=dict(id=u.id, name=u.name, email=u.email)
    ), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    d = request.get_json(silent=True) or {}
    email    = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    u = User.query.filter_by(email=email).first()
    if not u or not bcrypt.check_password_hash(u.password_hash, password):
        return jsonify(error="Invalid credentials"), 401
    return jsonify(
        access_token=create_access_token(identity=str(u.id)),
        refresh_token=create_refresh_token(identity=str(u.id)),
        user=dict(id=u.id, name=u.name, email=u.email)
    ), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    return jsonify(access_token=create_access_token(identity=get_jwt_identity())), 200

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    BLOCKLIST.add(get_jwt()["jti"])
    return jsonify(message="Logged out"), 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    u = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify(id=u.id, name=u.name, email=u.email), 200
