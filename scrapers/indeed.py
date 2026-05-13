"""
scrapers/indeed.py — Scrapes Indeed using Playwright with country-aware URLs.
"""
import time, random
from playwright.sync_api import sync_playwright
from extensions import db
from models import Job
from flask import current_app

# Indeed uses country-specific domains
COUNTRY_DOMAINS = {
    "usa":         "https://www.indeed.com",
    "uk":          "https://uk.indeed.com",
    "germany":     "https://de.indeed.com",
    "canada":      "https://ca.indeed.com",
    "australia":   "https://au.indeed.com",
    "singapore":   "https://sg.indeed.com",
    "netherlands": "https://www.indeed.nl",
    "uae":         "https://www.indeed.ae",
    "india":       "https://in.indeed.com",
    "france":      "https://fr.indeed.com",
    "remote":      "https://www.indeed.com",
}

def scrape_indeed(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles:
        return []

    new_jobs = []
    countries = [c.lower() for c in (settings.target_countries or ["remote"])]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=current_app.config["PLAYWRIGHT_HEADLESS"],
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        ctx  = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = ctx.new_page()

        for role in (p.preferred_roles or [])[:2]:
            for country_key in countries[:3]:
                base = COUNTRY_DOMAINS.get(country_key, "https://www.indeed.com")
                q    = role.replace(" ", "+")
                remote_param = "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11" if settings.remote_only else ""
                url  = f"{base}/jobs?q={q}&sort=date{remote_param}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    time.sleep(random.uniform(2, 4))

                    cards = page.query_selector_all("div.job_seen_beacon, div.resultContent")
                    for card in cards[:12]:
                        try:
                            title_el   = card.query_selector("h2.jobTitle span, h2 a span")
                            company_el = card.query_selector("span.companyName, [data-testid='company-name']")
                            loc_el     = card.query_selector("div.companyLocation, [data-testid='text-location']")
                            link_el    = card.query_selector("a[id^='job_'], a.jcs-JobTitle")

                            if not title_el or not company_el or not link_el:
                                continue

                            href       = link_el.get_attribute("href") or ""
                            apply_url  = href if href.startswith("http") else base + href
                            ext_id     = "in_" + href.split("jk=")[-1].split("&")[0] if "jk=" in href else ""
                            if not ext_id or Job.query.filter_by(external_id=ext_id).first():
                                continue

                            co = company_el.inner_text().strip()
                            if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])):
                                continue

                            job = Job(
                                external_id=ext_id,
                                company=co,
                                title=title_el.inner_text().strip(),
                                location=loc_el.inner_text().strip() if loc_el else "",
                                country=country_key.title(),
                                remote=settings.remote_only,
                                apply_url=apply_url,
                                source="indeed",
                            )
                            db.session.add(job)
                            new_jobs.append(job)

                        except Exception:
                            continue

                    db.session.commit()
                    time.sleep(random.uniform(4, 8))

                except Exception:
                    continue

        browser.close()

    return new_jobs
