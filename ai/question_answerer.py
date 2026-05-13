import google.generativeai as genai
from flask import current_app
from models import Profile, User

def answer_application_question(question: str, user_id: int, job) -> str:
    p = Profile.query.filter_by(user_id=user_id).first()
    u = User.query.get(user_id)
    try:
        genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
        model  = genai.GenerativeModel(current_app.config["GEMINI_MODEL"])
        prompt = f"""
You are filling a job application form. Answer concisely (1-3 sentences or just a number).
Reply with ONLY the answer text — nothing else.

Candidate: {u.name} | Skills: {p.skills} | Experience: {p.years_experience} yrs
Salary expectation: ${p.salary_expectation}/yr | Auth: {p.work_authorization}
Location: {p.location}
Job: {job.title} at {job.company}

Form question: {question}
""".strip()
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception:
        return ""
