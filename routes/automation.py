from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import AutomationSettings, ActivityLog
from tasks import run_automation_cycle

automation_bp = Blueprint("automation", __name__)

UPDATABLE = [
    "daily_limit","min_score","scan_interval_mins","min_salary","remote_only",
    "target_countries","blacklisted_companies","preferred_industries",
    "use_linkedin","use_indeed","use_wellfound","use_remoteok","use_greenhouse",
    "auto_answer","human_like","skip_duplicates",
]

def _dict(s):
    return {f: getattr(s, f) for f in UPDATABLE + ["is_running"]}

@automation_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    uid = int(get_jwt_identity())
    s   = AutomationSettings.query.filter_by(user_id=uid).first_or_404()
    return jsonify(_dict(s)), 200

@automation_bp.route("/settings", methods=["PUT"])
@jwt_required()
def update_settings():
    uid  = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    s    = AutomationSettings.query.filter_by(user_id=uid).first_or_404()
    for f in UPDATABLE:
        if f in data: setattr(s, f, data[f])
    db.session.commit()
    return jsonify(message="Saved", settings=_dict(s)), 200

@automation_bp.route("/start", methods=["POST"])
@jwt_required()
def start():
    uid = int(get_jwt_identity())
    s   = AutomationSettings.query.filter_by(user_id=uid).first_or_404()
    if not s.is_running:
        s.is_running = True
        db.session.add(ActivityLog(user_id=uid, event_type="system", message="Automation started"))
        db.session.commit()
        run_automation_cycle.delay(uid)
    return jsonify(message="Running"), 200

@automation_bp.route("/stop", methods=["POST"])
@jwt_required()
def stop():
    uid = int(get_jwt_identity())
    s   = AutomationSettings.query.filter_by(user_id=uid).first_or_404()
    s.is_running = False
    db.session.add(ActivityLog(user_id=uid, event_type="system", message="Automation stopped"))
    db.session.commit()
    return jsonify(message="Stopped"), 200

@automation_bp.route("/logs", methods=["GET"])
@jwt_required()
def logs():
    uid   = int(get_jwt_identity())
    limit = min(int(request.args.get("limit", 100)), 500)
    etype = request.args.get("type")
    q = ActivityLog.query.filter_by(user_id=uid)
    if etype: q = q.filter_by(event_type=etype)
    rows = q.order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return jsonify(logs=[{
        "id":r.id,"event_type":r.event_type,"message":r.message,
        "created_at":r.created_at.isoformat()
    } for r in rows]), 200
