from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Application

applications_bp = Blueprint("applications", __name__)

@applications_bp.route("", methods=["GET"])
@jwt_required()
def list_apps():
    uid    = int(get_jwt_identity())
    status = request.args.get("status")
    limit  = min(int(request.args.get("limit", 50)), 500)
    offset = int(request.args.get("offset", 0))
    q = Application.query.filter_by(user_id=uid)
    if status: q = q.filter_by(status=status)
    rows = q.order_by(Application.applied_at.desc()).offset(offset).limit(limit).all()
    return jsonify(applications=[{
        "id": r.id, "job_id": r.job_id,
        "company": r.job.company, "title": r.job.title,
        "location": r.job.location, "country": r.job.country,
        "source": r.job.source, "apply_url": r.job.apply_url,
        "status": r.status, "match_score": r.match_score,
        "applied_at": r.applied_at.isoformat(),
        "response_received": r.response_received.isoformat() if r.response_received else None,
    } for r in rows]), 200

@applications_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    uid = int(get_jwt_identity())
    return jsonify(
        total=Application.query.filter_by(user_id=uid).count(),
        pending=Application.query.filter_by(user_id=uid, status="pending").count(),
        interview=Application.query.filter_by(user_id=uid, status="interview").count(),
        rejected=Application.query.filter_by(user_id=uid, status="rejected").count(),
    ), 200
