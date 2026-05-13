"""
tasks.py — Celery async tasks.
Start worker: celery -A tasks.celery worker --loglevel=info --concurrency=2
"""
import time
import random
from celery import Celery
from config import Config

celery = Celery(__name__, broker=Config.REDIS_URL, backend=Config.REDIS_URL)


def _app():
    from app import create_app
    return create_app()


def _log(uid, msg, etype="info"):
    from extensions import db
    from models import ActivityLog
    try:
        db.session.add(ActivityLog(user_id=uid, event_type=etype, message=msg))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── Resume generation ─────────────────────────────────────────────────────────

@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_resume_task(self, uid: int, job_id: int):
    with _app().app_context():
        try:
            from ai.generator import generate_and_save_resume
            r = generate_and_save_resume(uid, job_id)
            return {"resume_id": r.id, "path": r.resume_path}
        except Exception as exc:
            raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_cover_letter_task(self, uid: int, job_id: int):
    with _app().app_context():
        try:
            from ai.generator import generate_and_save_cover_letter
            c = generate_and_save_cover_letter(uid, job_id)
            return {"cover_id": c.id, "path": c.pdf_path}
        except Exception as exc:
            raise self.retry(exc=exc)


# ── Full application pipeline ─────────────────────────────────────────────────

@celery.task(bind=True, max_retries=2, default_retry_delay=60)
def apply_to_job(self, uid: int, job_id: int):
    with _app().app_context():
        from extensions import db
        from models import Job, Application, AutomationSettings
        from ai.scorer import score_job_for_user
        from ai.generator import generate_and_save_resume, generate_and_save_cover_letter
        from automation.browser_agent import BrowserAgent

        job = Job.query.get(job_id)
        if not job:
            return {"status": "error", "reason": "job not found"}
        s = AutomationSettings.query.filter_by(user_id=uid).first()

        try:
            score  = score_job_for_user(job, uid)
            min_sc = s.min_score if s else 70
            if score < min_sc:
                _log(uid, f"Skipped: {job.title} @ {job.company} — score {score} < {min_sc}", "skipped")
                return {"status": "skipped"}

            _log(uid, f"Applying: {job.title} @ {job.company} (score:{score})", "info")
            resume = generate_and_save_resume(uid, job_id)
            cover  = generate_and_save_cover_letter(uid, job_id)

            agent  = BrowserAgent(headless=True, human_like=s.human_like if s else True)
            result = agent.apply(
                apply_url   = job.apply_url,
                resume_path = resume.resume_path,
                cover_path  = cover.pdf_path,
                user_id     = uid, job=job,
                auto_answer = s.auto_answer if s else True,
            )
            agent.close()

            if result["success"]:
                rec = Application(user_id=uid, job_id=job_id,
                                  resume_id=resume.id, cover_letter_id=cover.id,
                                  status="pending", match_score=score)
                db.session.add(rec); db.session.commit()
                _log(uid, f"✓ Applied: {job.title} @ {job.company}", "applied")
                return {"status": "applied", "application_id": rec.id}
            else:
                _log(uid, f"Failed: {job.title} @ {job.company} — {result.get('reason')}", "error")
                return {"status": "failed", "reason": result.get("reason")}

        except Exception as exc:
            _log(uid, f"Error job {job_id}: {exc}", "error")
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "error", "reason": str(exc)}


# ── Master automation cycle ───────────────────────────────────────────────────

@celery.task
def run_automation_cycle(uid: int):
    with _app().app_context():
        from extensions import db
        from models import AutomationSettings, Application
        from scrapers.remoteok   import scrape_remoteok
        from scrapers.linkedin   import scrape_linkedin
        from scrapers.indeed     import scrape_indeed
        from scrapers.wellfound  import scrape_wellfound
        from scrapers.greenhouse import scrape_greenhouse
        from datetime import date

        s = AutomationSettings.query.filter_by(user_id=uid).first()
        if not s or not s.is_running:
            return {"status": "stopped"}

        today_count = Application.query.filter(
            Application.user_id == uid,
            db.func.date(Application.applied_at) == date.today()
        ).count()
        remaining = s.daily_limit - today_count

        if remaining <= 0:
            _log(uid, "Daily limit reached — resuming tomorrow", "info")
            run_automation_cycle.apply_async(args=[uid], countdown=s.scan_interval_mins * 60)
            return {"status": "limit_reached"}

        target = s.target_countries or ["remote"]
        _log(uid, f"Scan started — countries: {target}", "info")

        found = []
        for scraper_name, scraper_fn, enabled in [
            ("RemoteOK",   scrape_remoteok,   s.use_remoteok),
            ("LinkedIn",   scrape_linkedin,   s.use_linkedin),
            ("Indeed",     scrape_indeed,     s.use_indeed),
            ("Wellfound",  scrape_wellfound,  s.use_wellfound),
            ("Greenhouse", scrape_greenhouse, s.use_greenhouse),
        ]:
            if not enabled:
                continue
            try:
                jobs = scraper_fn(uid, s)
                found += jobs
                _log(uid, f"{scraper_name}: found {len(jobs)} jobs", "info")
            except Exception as e:
                _log(uid, f"{scraper_name} error: {e}", "error")

        _log(uid, f"Total {len(found)} new jobs this cycle", "info")

        applied = 0
        for job in found:
            if applied >= remaining:
                break
            if s.skip_duplicates:
                if Application.query.filter_by(user_id=uid, job_id=job.id).first():
                    continue
            apply_to_job.delay(uid, job.id)
            applied += 1
            time.sleep(random.uniform(2, 5))

        _log(uid, f"Queued {applied} applications. Next scan in {s.scan_interval_mins} min.", "info")
        run_automation_cycle.apply_async(args=[uid], countdown=s.scan_interval_mins * 60)
        return {"status": "ok", "found": len(found), "queued": applied}
