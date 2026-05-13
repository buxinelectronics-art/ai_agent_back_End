import time, random
from playwright.sync_api import sync_playwright
from extensions import db
from models import Job
from flask import current_app

COUNTRY_CODES = {
    "usa":"United States","uk":"United Kingdom","germany":"Germany",
    "canada":"Canada","uae":"United Arab Emirates","singapore":"Singapore",
    "netherlands":"Netherlands","australia":"Australia","india":"India",
}

def scrape_linkedin(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles: return []

    new_jobs = []
    countries = [c.lower() for c in (settings.target_countries or ["remote"])]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=current_app.config["PLAYWRIGHT_HEADLESS"],
            args=["--no-sandbox"]
        )
        ctx  = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width":1440,"height":900}
        )
        page = ctx.new_page()

        for role in (p.preferred_roles or [])[:2]:
            for country_key in countries[:3]:
                loc = COUNTRY_CODES.get(country_key, "worldwide")
                q   = role.replace(" ","%20")
                url = (f"https://www.linkedin.com/jobs/search/?keywords={q}"
                       f"&location={loc.replace(' ','%20')}"
                       f"{'&f_WT=2' if settings.remote_only else ''}&f_TPR=r3600")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(random.uniform(2, 4))
                    for card in page.query_selector_all(".job-search-card")[:10]:
                        try:
                            title_el   = card.query_selector(".base-search-card__title")
                            company_el = card.query_selector(".base-search-card__subtitle")
                            loc_el     = card.query_selector(".job-search-card__location")
                            link_el    = card.query_selector("a.base-card__full-link")
                            if not all([title_el, company_el, link_el]): continue
                            apply_url  = link_el.get_attribute("href") or ""
                            ext_id     = "li_" + apply_url.split("/jobs/view/")[-1].split("?")[0]
                            if Job.query.filter_by(external_id=ext_id).first(): continue
                            co = company_el.inner_text().strip()
                            if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])): continue
                            job = Job(
                                external_id=ext_id, company=co,
                                title=title_el.inner_text().strip(),
                                location=loc_el.inner_text().strip() if loc_el else loc,
                                country=country_key.title(),
                                remote=settings.remote_only,
                                apply_url=apply_url, source="linkedin",
                            )
                            db.session.add(job)
                            new_jobs.append(job)
                        except Exception: continue
                    db.session.commit()
                    time.sleep(random.uniform(3, 7))
                except Exception: continue
        browser.close()
    return new_jobs
