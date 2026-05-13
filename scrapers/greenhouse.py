"""
scrapers/greenhouse.py — Queries Greenhouse job board API directly.
Many companies post jobs via Greenhouse with a public JSON API.
"""
import requests
from extensions import db
from models import Job

# Top robotics/AI companies using Greenhouse
GREENHOUSE_COMPANIES = [
    "boston-dynamics", "waymo", "nuro", "cruise", "zoox",
    "openai", "scale-ai", "covariant", "embodied-intelligence",
    "agility-robotics", "apptronik", "figure", "sanctuary-ai",
    "1x-technologies", "skild-ai", "physicalintelligence",
    "deepmind", "nvidia", "qualcomm", "arm",
    "mobileye", "aurora", "argo-ai", "motional",
]

def scrape_greenhouse(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles:
        return []

    new_jobs    = []
    role_kws    = [r.lower() for r in (p.preferred_roles or [])]
    headers     = {"User-Agent": "JobAgent/1.0"}
    countries   = [c.lower() for c in (settings.target_countries or [])]

    for company_slug in GREENHOUSE_COMPANIES:
        try:
            url  = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            for item in data.get("jobs", [])[:20]:
                title = item.get("title", "").lower()

                # Only pick jobs matching preferred roles
                if not any(kw in title for kw in role_kws + ["robot","ai","vision","autonomous","embedded","perception","slam","ros"]):
                    continue

                location = item.get("location", {}).get("name", "")
                country_match = (
                    not countries
                    or any(c in location.lower() for c in countries)
                    or settings.remote_only
                    or "remote" in location.lower()
                )
                if not country_match:
                    continue

                co       = company_slug.replace("-", " ").title()
                ext_id   = f"gh_{item.get('id','')}"
                apply_url = item.get("absolute_url", "")

                if not apply_url or Job.query.filter_by(external_id=ext_id).first():
                    continue
                if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])):
                    continue

                # Salary (Greenhouse rarely includes it)
                sal_range = item.get("metadata", [])
                s_min = s_max = None
                for m in sal_range:
                    if "salary" in (m.get("name","")).lower():
                        val = str(m.get("value",""))
                        parts = val.replace("$","").replace("k","000").replace(",","").split("-")
                        try:
                            s_min = int(parts[0].strip())
                            s_max = int(parts[-1].strip())
                        except Exception:
                            pass

                if s_min and settings.min_salary and s_min < settings.min_salary:
                    continue

                # Normalise country
                detected_country = "Remote"
                for c in ["USA","UK","Germany","Canada","Singapore","India","Australia","France"]:
                    if c.lower() in location.lower():
                        detected_country = c
                        break
                if "remote" in location.lower():
                    detected_country = "Remote"

                job = Job(
                    external_id=ext_id,
                    company=co,
                    title=item.get("title",""),
                    description=item.get("content","")[:3000],
                    location=location,
                    country=detected_country,
                    remote=("remote" in location.lower() or settings.remote_only),
                    salary_min=s_min,
                    salary_max=s_max,
                    apply_url=apply_url,
                    source="greenhouse",
                )
                db.session.add(job)
                new_jobs.append(job)

        except Exception:
            continue

    db.session.commit()
    return new_jobs
