import requests
from extensions import db
from models import Job

# Country → RemoteOK tag / location keyword mapping
COUNTRY_TAGS = {
    "usa": "usa", "uk": "uk", "germany": "germany",
    "canada": "canada", "uae": "dubai", "singapore": "singapore",
    "netherlands": "netherlands", "australia": "australia",
    "india": "india", "remote": "",
}

def scrape_remoteok(user_id: int, settings) -> list:
    from models import Profile
    p = Profile.query.filter_by(user_id=user_id).first()
    if not p or not p.preferred_roles: return []

    new_jobs = []
    headers  = {"User-Agent": "JobAgent/1.0 (autonomous job applicant)"}
    countries = [c.lower() for c in (settings.target_countries or [])] or ["remote"]

    for role in (p.preferred_roles or [])[:3]:
        tag = role.lower().replace(" ", "-")
        for country_key in countries[:3]:
            loc_tag  = COUNTRY_TAGS.get(country_key, "")
            query    = f"{tag}-{loc_tag}" if loc_tag else tag
            try:
                resp = requests.get(
                    f"https://remoteok.com/api?tag={query}",
                    headers=headers, timeout=12
                )
                if resp.status_code != 200: continue
                data = resp.json()
                for item in data[1:16]:
                    if not isinstance(item, dict): continue
                    ext_id = f"rok_{item.get('id','')}"
                    if not item.get("id") or Job.query.filter_by(external_id=ext_id).first():
                        continue
                    co = item.get("company","")
                    if any(b.lower() in co.lower() for b in (settings.blacklisted_companies or [])):
                        continue
                    # Salary parse
                    s_min = s_max = None
                    sal = item.get("salary","")
                    if sal and "-" in str(sal):
                        parts = str(sal).replace("$","").replace("k","000").split("-")
                        try: s_min, s_max = int(parts[0].strip()), int(parts[1].strip())
                        except Exception: pass
                    if s_min and settings.min_salary and s_min < settings.min_salary:
                        continue

                    job = Job(
                        external_id=ext_id,
                        company=co,
                        title=item.get("position",""),
                        description=item.get("description",""),
                        location=item.get("location","Remote"),
                        country=country_key.title(),
                        remote=True,
                        salary_min=s_min, salary_max=s_max,
                        apply_url=item.get("url",""),
                        source="remoteok",
                    )
                    db.session.add(job)
                    new_jobs.append(job)
            except Exception:
                continue

    db.session.commit()
    return new_jobs
