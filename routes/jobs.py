from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Job, Application
from ai.scorer import score_job_for_user
from tasks import apply_to_job

jobs_bp = Blueprint("jobs", __name__)

@jobs_bp.route("", methods=["GET"])
@jwt_required()
def list_jobs():
    uid       = int(get_jwt_identity())
    source    = request.args.get("source")
    country   = request.args.get("country")          # NEW: country filter
    min_score = int(request.args.get("min_score", 0))
    limit     = min(int(request.args.get("limit", 50)), 200)
    offset    = int(request.args.get("offset", 0))

    q = Job.query
    if source:  q = q.filter_by(source=source)
    if country and country != "all":
        q = q.filter(
            db.or_(
                Job.country.ilike(f"%{country}%"),
                Job.location.ilike(f"%{country}%"),
                Job.remote == True
            )
        )

    jobs = q.order_by(Job.scraped_at.desc()).offset(offset).limit(limit).all()

    results = []
    for j in jobs:
        score = score_job_for_user(j, uid)
        if score >= min_score:
            results.append({
                "id": j.id, "company": j.company, "title": j.title,
                "location": j.location, "country": j.country,
                "remote": j.remote, "salary_min": j.salary_min,
                "salary_max": j.salary_max, "source": j.source,
                "apply_url": j.apply_url,
                "scraped_at": j.scraped_at.isoformat(), "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(jobs=results, total=len(results)), 200

@jobs_bp.route("/apply/<int:job_id>", methods=["POST"])
@jwt_required()
def manual_apply(job_id):
    uid = int(get_jwt_identity())
    if Application.query.filter_by(user_id=uid, job_id=job_id).first():
        return jsonify(error="Already applied"), 409
    apply_to_job.delay(uid, job_id)
    return jsonify(message="Application queued"), 202
