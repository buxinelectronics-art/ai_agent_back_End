"""
scrapers/wellfound.py — Scrapes Wellfound (AngelList) for startup jobs.
Wellfound has a public search page, no login needed for browsing.
"""
import time, random
from playwright.sync_api import sync_playwright
from extensions import db
from models import Job
from flask import current_app

COUNTRY_MAP = {
    "usa":         "united-states",
    "uk":          "united-kingdom",
    "germany":     "germany",
    "canada":      "canada",
    "singapore":   "singapore",
    "netherlands": "netherlands",
    "australia":   "australia",
    "india":       "india",
    "remote":      "remote",
}

def scrape_wellfound(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles:
        return []

    new_jobs = []
    countries = [c.lower() for c in (settings.target_countries or ["remote"])]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=current_app.config["PLAYWRIGHT_HEADLESS"],
            args=["--no-sandbox"]
        )
        ctx  = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = ctx.new_page()

        for role in (p.preferred_roles or [])[:2]:
            for country_key in countries[:2]:
                loc = COUNTRY_MAP.get(country_key, "remote")
                q   = role.lower().replace(" ", "-")
                url = f"https://wellfound.com/jobs?q={q}&location={loc}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    time.sleep(random.uniform(2, 4))

                    cards = page.query_selector_all("div[data-test='StartupResult'], div.styles_component__")
                    for card in cards[:10]:
                        try:
                            title_el   = card.query_selector("a[data-test='job-link'], a.styles_title__")
                            company_el = card.query_selector("span[data-test='startup-link'], a.styles_startupLink__")
                            loc_el     = card.query_selector("span[data-test='location']")

                            if not title_el or not company_el:
                                continue

                            href      = title_el.get_attribute("href") or ""
                            apply_url = href if href.startswith("http") else "https://wellfound.com" + href
                            ext_id    = "wf_" + href.split("/")[-1]

                            if Job.query.filter_by(external_id=ext_id).first():
                                continue

                            co = company_el.inner_text().strip()
                            if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])):
                                continue

                            job = Job(
                                external_id=ext_id,
                                company=co,
                                title=title_el.inner_text().strip(),
                                location=loc_el.inner_text().strip() if loc_el else country_key.title(),
                                country=country_key.title(),
                                remote=(loc == "remote" or settings.remote_only),
                                apply_url=apply_url,
                                source="wellfound",
                            )
                            db.session.add(job)
                            new_jobs.append(job)

                        except Exception:
                            continue

                    db.session.commit()
                    time.sleep(random.uniform(3, 6))

                except Exception:
                    continue

        browser.close()

    return new_jobs
