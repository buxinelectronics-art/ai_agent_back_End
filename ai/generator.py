import os, json
from datetime import datetime
import google.generativeai as genai
from flask import current_app
from extensions import db
from models import Profile, Job, Resume, CoverLetter, User

def _model():
    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
    return genai.GenerativeModel(current_app.config["GEMINI_MODEL"])

def _clean(text):
    return text.strip().replace("```json","").replace("```","").strip()

# ── RESUME ────────────────────────────────────────────────────────────────────

def generate_and_save_resume(user_id: int, job_id: int) -> Resume:
    p   = Profile.query.filter_by(user_id=user_id).first()
    u   = User.query.get(user_id)
    job = Job.query.get(job_id)

    prompt = f"""
You are an expert ATS resume writer. Rewrite this candidate's resume for the target job.
Reply ONLY with valid JSON, no markdown fences.

JSON structure:
{{
  "name": "...", "email": "...", "phone": "...", "location": "...",
  "github": "...", "portfolio": "...",
  "summary": "2-3 sentence tailored summary",
  "skills": ["skill1","skill2",...],
  "experience": [
    {{"company":"...","title":"...","dates":"...","bullets":["...","...","..."]}}
  ],
  "education": [{{"institution":"...","degree":"...","dates":"..."}}],
  "projects": [
    {{"name":"...","tech":"...","description":"..."}}
  ],
  "ats_keywords_injected": 0
}}

Candidate:
Name: {u.name} | Email: {u.email} | Phone: {p.phone}
Location: {p.location} | GitHub: {p.github_url} | Portfolio: {p.portfolio_url}
Skills: {p.skills}
Experience years: {p.years_experience}
Past experience: {(p.experience_text or 'Not provided')[:1500]}
Education: {p.education or 'BSc Computer Science, Sharda University'}

Target Job: {job.title} at {job.company}
Job Description: {(job.description or '')[:2000]}
""".strip()

    resp = _model().generate_content(prompt)
    data = json.loads(_clean(resp.text))
    return _save_resume_pdf(data, user_id, job)


def _save_resume_pdf(data: dict, user_id: int, job) -> Resume:
    from weasyprint import HTML
    exp_html = ""
    for e in data.get("experience", []):
        bullets = "".join(f"<li>{b}</li>" for b in e.get("bullets", []))
        exp_html += f"""<div class="item">
          <div class="row"><strong>{e['title']}</strong><span>{e.get('dates','')}</span></div>
          <div style="color:#555;font-size:11px">{e['company']}</div>
          <ul>{bullets}</ul></div>"""

    proj_html = ""
    for pr in data.get("projects", []):
        proj_html += f"""<div class="item">
          <div class="row"><strong>{pr['name']}</strong>
          <span style="font-size:10px;color:#777">{pr.get('tech','')}</span></div>
          <p style="margin:3px 0 0">{pr.get('description','')}</p></div>"""

    edu_html = "".join(
        f'<div class="item"><div class="row"><strong>{e["degree"]}</strong>'
        f'<span>{e.get("dates","")}</span></div>'
        f'<div style="color:#555;font-size:11px">{e["institution"]}</div></div>'
        for e in data.get("education", [])
    )
    skills = " · ".join(data.get("skills", []))

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Helvetica Neue',Arial,sans-serif;font-size:11.5px;color:#111;padding:36px 44px;line-height:1.55}}
    h1{{font-size:22px;letter-spacing:-0.5px}}
    .contact{{font-size:10px;color:#555;margin:4px 0 18px}}
    a{{color:#111;text-decoration:none}}
    .section-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
                    border-bottom:1.5px solid #111;margin:16px 0 8px;padding-bottom:3px}}
    .item{{margin-bottom:10px}}
    .row{{display:flex;justify-content:space-between;align-items:baseline}}
    ul{{margin:4px 0 0 16px}}
    li{{margin-bottom:2px}}
    .summary{{margin-bottom:4px;color:#333}}
    </style></head><body>
    <h1>{data.get('name','')}</h1>
    <div class="contact">
      {data.get('email','')} &nbsp;|&nbsp; {data.get('phone','')} &nbsp;|&nbsp;
      {data.get('location','')} &nbsp;|&nbsp;
      <a href="https://{data.get('github','')}">{data.get('github','')}</a> &nbsp;|&nbsp;
      <a href="https://{data.get('portfolio','')}">{data.get('portfolio','')}</a>
    </div>
    <div class="section-title">Professional Summary</div>
    <p class="summary">{data.get('summary','')}</p>
    <div class="section-title">Technical Skills</div>
    <p style="color:#333">{skills}</p>
    <div class="section-title">Experience</div>{exp_html}
    <div class="section-title">Projects</div>{proj_html}
    <div class="section-title">Education</div>{edu_html}
    </body></html>"""

    folder   = os.path.join(current_app.config["GENERATED_FOLDER"], str(user_id))
    os.makedirs(folder, exist_ok=True)
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(folder, f"resume_{job.company}_{ts}.pdf")
    HTML(string=html).write_pdf(out_path)

    r = Resume(user_id=user_id, job_id=job.id, resume_path=out_path,
               job_title=job.title, company=job.company,
               ats_score=data.get("ats_keywords_injected"))
    db.session.add(r); db.session.commit()
    return r


# ── COVER LETTER ──────────────────────────────────────────────────────────────

def generate_and_save_cover_letter(user_id: int, job_id: int) -> CoverLetter:
    p   = Profile.query.filter_by(user_id=user_id).first()
    u   = User.query.get(user_id)
    job = Job.query.get(job_id)

    prompt = f"""
Write a professional cover letter. Reply ONLY with valid JSON, no markdown.

JSON: {{"body": "full letter text, paragraphs separated by \\n\\n"}}

Rules: under 320 words, specific to the role, no clichés.

Candidate: {u.name}, {p.years_experience} years exp
Skills: {p.skills}
Experience: {(p.experience_text or '')[:800]}
Target: {job.title} at {job.company}
Job desc: {(job.description or '')[:1000]}
""".strip()

    resp = _model().generate_content(prompt)
    data = json.loads(_clean(resp.text))

    from weasyprint import HTML
    body_html = "".join(f"<p>{p_}</p>" for p_ in data["body"].split("\n\n"))
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{{font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;color:#111;
          padding:52px 60px;line-height:1.7}}
    p{{margin:0 0 14px}} .sig{{margin-top:32px}}
    </style></head><body>
    <p>Hiring Manager<br>{job.company}</p><br>
    {body_html}
    <div class="sig">Sincerely,<br><strong>{u.name}</strong></div>
    </body></html>"""

    folder   = os.path.join(current_app.config["GENERATED_FOLDER"], str(user_id))
    os.makedirs(folder, exist_ok=True)
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(folder, f"cover_{job.company}_{ts}.pdf")
    HTML(string=html).write_pdf(out_path)

    c = CoverLetter(user_id=user_id, job_id=job_id, pdf_path=out_path, company=job.company)
    db.session.add(c); db.session.commit()
    return c
