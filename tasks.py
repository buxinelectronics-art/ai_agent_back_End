"""
tasks.py — Background task runner using Python threading.
No Celery, no Redis, no greenlet. Works on any Python version.
"""
import threading
import time
import random
import logging

logger = logging.getLogger(__name__)


def _log(app, uid, msg, etype="info"):
    with app.app_context():
        from extensions import db
        from models import ActivityLog
        try:
            db.session.add(ActivityLog(user_id=uid, event_type=etype, message=msg))
            db.session.commit()
        except Exception:
            db.session.rollback()


# ── Thread runner ─────────────────────────────────────────────────────────────

def run_in_thread(fn, *args, **kwargs):
    """Run a function in a daemon background thread."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


# ── Resume generation ─────────────────────────────────────────────────────────

def generate_resume_task(app, uid: int, job_id: int):
    def _run():
        with app.app_context():
            try:
                from ai.generator import generate_and_save_resume
                r = generate_and_save_resume(uid, job_id)
                logger.info(f"Resume generated: {r.id}")
            except Exception as e:
                logger.error(f"Resume generation failed: {e}")
    run_in_thread(_run)


def generate_cover_letter_task(app, uid: int, job_id: int):
    def _run():
        with app.app_context():
            try:
                from ai.generator import generate_and_save_cover_letter
                c = generate_and_save_cover_letter(uid, job_id)
                logger.info(f"Cover letter generated: {c.id}")
            except Exception as e:
                logger.error(f"Cover letter generation failed: {e}")
    run_in_thread(_run)


# ── Full application pipeline ─────────────────────────────────────────────────

def apply_to_job(app, uid: int, job_id: int):
    def _run():
        with app.app_context():
            from extensions import db
            from models import Job, Application, AutomationSettings
            from ai.scorer import score_job_for_user
            from ai.generator import generate_and_save_resume, generate_and_save_cover_letter
            from automation.browser_agent import BrowserAgent

            job = Job.query.get(job_id)
            if not job:
                return
            s = AutomationSettings.query.filter_by(user_id=uid).first()

            try:
                score  = score_job_for_user(job, uid)
                min_sc = s.min_score if s else 70

                if score < min_sc:
                    _log(app, uid,
                         f"Skipped: {job.title} @ {job.company} — score {score} < {min_sc}",
                         "skipped")
                    return

                _log(app, uid, f"Applying: {job.title} @ {job.company} (score:{score})", "info")

                resume = generate_and_save_resume(uid, job_id)
                cover  = generate_and_save_cover_letter(uid, job_id)

                agent  = BrowserAgent(headless=True, human_like=s.human_like if s else True)
                result = agent.apply(
                    apply_url   = job.apply_url,
                    resume_path = resume.resume_path,
                    cover_path  = cover.pdf_path,
                    user_id     = uid,
                    job         = job,
                    auto_answer = s.auto_answer if s else True,
                )
                agent.close()

                if result["success"]:
                    rec = Application(
                        user_id         = uid,
                        job_id          = job_id,
                        resume_id       = resume.id,
                        cover_letter_id = cover.id,
                        status          = "pending",
                        match_score     = score,
                    )
                    db.session.add(rec)
                    db.session.commit()
                    _log(app, uid, f"✓ Applied: {job.title} @ {job.company}", "applied")
                else:
                    _log(app, uid,
                         f"Failed: {job.title} @ {job.company} — {result.get('reason')}",
                         "error")

            except Exception as e:
                _log(app, uid, f"Error on job {job_id}: {e}", "error")
                logger.exception(f"apply_to_job error uid={uid} job={job_id}")

    run_in_thread(_run)


# ── Master automation cycle ───────────────────────────────────────────────────

def run_automation_cycle(app, uid: int):
    """
    One full automation cycle:
    1. Check if still running + daily limit
    2. Scrape all enabled sources
    3. Dispatch apply threads for qualifying jobs
    4. Schedule next cycle via threading.Timer
    """
    def _run():
        with app.app_context():
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
                logger.info(f"Automation stopped for user {uid}")
                return

            # Daily limit check
            today_count = Application.query.filter(
                Application.user_id == uid,
                db.func.date(Application.applied_at) == date.today()
            ).count()
            remaining = s.daily_limit - today_count

            if remaining <= 0:
                _log(app, uid, "Daily limit reached — resuming tomorrow", "info")
                _schedule_next(app, uid, s.scan_interval_mins)
                return

            target = s.target_countries or ["remote"]
            _log(app, uid, f"Scan started — countries: {target}", "info")

            found = []
            for name, fn, enabled in [
                ("RemoteOK",   scrape_remoteok,   s.use_remoteok),
                ("LinkedIn",   scrape_linkedin,   s.use_linkedin),
                ("Indeed",     scrape_indeed,     s.use_indeed),
                ("Wellfound",  scrape_wellfound,  s.use_wellfound),
                ("Greenhouse", scrape_greenhouse, s.use_greenhouse),
            ]:
                if not enabled:
                    continue
                try:
                    jobs = fn(uid, s)
                    found += jobs
                    _log(app, uid, f"{name}: {len(jobs)} new jobs found", "info")
                except Exception as e:
                    _log(app, uid, f"{name} error: {e}", "error")

            _log(app, uid, f"Total {len(found)} new jobs this cycle", "info")

            applied = 0
            for job in found:
                if applied >= remaining:
                    break
                if s.skip_duplicates:
                    already = Application.query.filter_by(user_id=uid, job_id=job.id).first()
                    if already:
                        continue
                # Each application runs in its own thread
                apply_to_job(app, uid, job.id)
                applied += 1
                time.sleep(random.uniform(2, 5))

            _log(app, uid,
                 f"Queued {applied} applications. Next scan in {s.scan_interval_mins} min.",
                 "info")

            _schedule_next(app, uid, s.scan_interval_mins)

    run_in_thread(_run)


def _schedule_next(app, uid: int, interval_mins: int):
    """Schedule the next automation cycle using a Timer thread."""
    def _check_and_run():
        with app.app_context():
            from models import AutomationSettings
            s = AutomationSettings.query.filter_by(user_id=uid).first()
            if s and s.is_running:
                run_automation_cycle(app, uid)
    t = threading.Timer(interval_mins * 60, _check_and_run)
    t.daemon = True
    t.start()
