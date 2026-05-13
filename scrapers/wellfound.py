"""
scrapers/wellfound.py — Scrapes Wellfound via HTTP requests.
Uses their public search page with BeautifulSoup parsing.
"""
import time
import random
import requests
from bs4 import BeautifulSoup
from extensions import db
from models import Job

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

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

    new_jobs  = []
    countries = [c.lower() for c in (settings.target_countries or ["remote"])]

    for role in (p.preferred_roles or [])[:2]:
        for country_key in countries[:2]:
            loc = COUNTRY_MAP.get(country_key, "remote")
            q   = role.lower().replace(" ", "-")
            url = f"https://wellfound.com/jobs?q={q}&location={loc}"

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup  = BeautifulSoup(resp.text, "lxml")

                # Wellfound renders JS, so grab any job links from raw HTML
                links = soup.find_all("a", href=lambda x: x and "/jobs/" in x)

                seen = set()
                for link in links[:10]:
                    try:
                        href      = link.get("href", "")
                        apply_url = href if href.startswith("http") else "https://wellfound.com" + href
                        ext_id    = "wf_" + href.split("/")[-1].split("?")[0]

                        if ext_id in seen or ext_id == "wf_" or \
                           Job.query.filter_by(external_id=ext_id).first():
                            continue
                        seen.add(ext_id)

                        title_text = link.get_text(strip=True)
                        if not title_text or len(title_text) < 3:
                            continue

                        job = Job(
                            external_id = ext_id,
                            company     = "Via Wellfound",
                            title       = title_text,
                            location    = country_key.title(),
                            country     = country_key.title(),
                            remote      = (loc == "remote" or settings.remote_only),
                            apply_url   = apply_url,
                            source      = "wellfound",
                        )
                        db.session.add(job)
                        new_jobs.append(job)

                    except Exception:
                        continue

                db.session.commit()
                time.sleep(random.uniform(3, 6))

            except Exception:
                continue

    return new_jobs
