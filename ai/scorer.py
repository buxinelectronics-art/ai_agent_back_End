import json
import google.generativeai as genai
from flask import current_app
from models import Profile

def score_job_for_user(job, user_id: int) -> int:
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p: return 50
    try:
        genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
        model  = genai.GenerativeModel(current_app.config["GEMINI_MODEL"])
        prompt = f"""
Score this job match 0-100. Reply ONLY with JSON: {{"score": <int>}}

Candidate skills: {p.skills}
Experience: {p.years_experience} years
Preferred roles: {p.preferred_roles}
Salary expectation: ${p.salary_expectation}/yr
Work preference: {p.work_preference}
Authorization: {p.work_authorization}

Job: {job.title} at {job.company}
Location: {job.location} | Remote: {job.remote}
Salary: ${job.salary_min}-${job.salary_max}
Description: {(job.description or '')[:800]}
""".strip()
        resp = model.generate_content(prompt)
        text = resp.text.strip().replace("```json","").replace("```","")
        return max(0, min(100, int(json.loads(text)["score"])))
    except Exception:
        return 50
