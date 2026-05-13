import os
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from extensions import db
from models import Profile, Resume, CoverLetter, Job
from tasks import generate_resume_task, generate_cover_letter_task

resume_bp = Blueprint("resume", __name__)

def _allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in {"pdf", "docx"}

@resume_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_resume():
    uid = int(get_jwt_identity())
    if "file" not in request.files: return jsonify(error="No file"), 400
    f = request.files["file"]
    if not _allowed(f.filename): return jsonify(error="PDF/DOCX only"), 400
    folder = os.path.join(os.environ.get("UPLOAD_FOLDER", "/var/data/uploads"), str(uid))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, secure_filename(f"resume_{uid}_{f.filename}"))
    f.save(path)
    Profile.query.filter_by(user_id=uid).update({"base_resume_path": path})
    db.session.commit()
    return jsonify(message="Resume uploaded", path=path), 200

@resume_bp.route("/upload-cover", methods=["POST"])
@jwt_required()
def upload_cover():
    uid = int(get_jwt_identity())
    if "file" not in request.files: return jsonify(error="No file"), 400
    f = request.files["file"]
    if not _allowed(f.filename): return jsonify(error="PDF/DOCX only"), 400
    folder = os.path.join(os.environ.get("UPLOAD_FOLDER", "/var/data/uploads"), str(uid))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, secure_filename(f"cover_{uid}_{f.filename}"))
    f.save(path)
    Profile.query.filter_by(user_id=uid).update({"cover_letter_path": path})
    db.session.commit()
    return jsonify(message="Cover letter uploaded", path=path), 200

@resume_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate():
    uid    = int(get_jwt_identity())
    data   = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    if not job_id or not Job.query.get(job_id):
        return jsonify(error="Valid job_id required"), 400
    generate_resume_task.delay(uid, job_id)
    generate_cover_letter_task.delay(uid, job_id)
    return jsonify(message="Generating — check /resume/list shortly"), 202

@resume_bp.route("/list", methods=["GET"])
@jwt_required()
def list_docs():
    uid = int(get_jwt_identity())
    r = Resume.query.filter_by(user_id=uid).order_by(Resume.generated_at.desc()).limit(50).all()
    c = CoverLetter.query.filter_by(user_id=uid).order_by(CoverLetter.generated_at.desc()).limit(50).all()
    return jsonify(
        resumes=[{"id": x.id,"job_title":x.job_title,"company":x.company,
                  "ats_score":x.ats_score,"generated_at":x.generated_at.isoformat()} for x in r],
        cover_letters=[{"id":x.id,"company":x.company,
                        "generated_at":x.generated_at.isoformat()} for x in c],
    ), 200

@resume_bp.route("/download/resume/<int:rid>", methods=["GET"])
@jwt_required()
def dl_resume(rid):
    uid = int(get_jwt_identity())
    r   = Resume.query.filter_by(id=rid, user_id=uid).first_or_404()
    return send_file(r.resume_path, as_attachment=True,
                     download_name=f"resume_{r.company}.pdf")

@resume_bp.route("/download/cover/<int:cid>", methods=["GET"])
@jwt_required()
def dl_cover(cid):
    uid = int(get_jwt_identity())
    c   = CoverLetter.query.filter_by(id=cid, user_id=uid).first_or_404()
    return send_file(c.pdf_path, as_attachment=True,
                     download_name=f"cover_{c.company}.pdf")
