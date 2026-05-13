"""
scrapers/indeed.py — Scrapes Indeed using HTTP requests + BeautifulSoup.
"""
import time
import random
import requests
from bs4 import BeautifulSoup
from extensions import db
from models import Job

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape_indeed(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles:
        return []

    new_jobs  = []
    countries = [c.lower() for c in (settings.target_countries or ["remote"])]

    for role in (p.preferred_roles or [])[:2]:
        for country_key in countries[:3]:
            base  = COUNTRY_DOMAINS.get(country_key, "https://www.indeed.com")
            q     = role.replace(" ", "+")
            remote_param = "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11" if settings.remote_only else ""
            url   = f"{base}/jobs?q={q}&sort=date{remote_param}"

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                soup  = BeautifulSoup(resp.text, "lxml")
                cards = soup.find_all("div", class_=["job_seen_beacon", "resultContent"])

                for card in cards[:10]:
                    try:
                        title_el   = card.find("h2", class_="jobTitle")
                        company_el = card.find("span", class_="companyName") or \
                                     card.find(attrs={"data-testid": "company-name"})
                        loc_el     = card.find("div", class_="companyLocation") or \
                                     card.find(attrs={"data-testid": "text-location"})
                        link_el    = card.find("a", id=lambda x: x and x.startswith("job_"))

                        if not title_el or not company_el:
                            continue

                        href      = (link_el.get("href", "") if link_el else "")
                        apply_url = href if href.startswith("http") else base + href
                        jk        = href.split("jk=")[-1].split("&")[0] if "jk=" in href else ""
                        ext_id    = f"in_{jk}" if jk else ""

                        if not ext_id or Job.query.filter_by(external_id=ext_id).first():
                            continue

                        co = company_el.get_text(strip=True)
                        if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])):
                            continue

                        job = Job(
                            external_id = ext_id,
                            company     = co,
                            title       = title_el.get_text(strip=True),
                            location    = loc_el.get_text(strip=True) if loc_el else country_key.title(),
                            country     = country_key.title(),
                            remote      = (country_key == "remote" or settings.remote_only),
                            apply_url   = apply_url,
                            source      = "indeed",
                        )
                        db.session.add(job)
                        new_jobs.append(job)

                    except Exception:
                        continue

                db.session.commit()
                time.sleep(random.uniform(4, 8))

            except Exception:
                continue

    return new_jobs
