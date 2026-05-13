from datetime import datetime
from extensions import db

class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    profile       = db.relationship("Profile",            back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes       = db.relationship("Resume",             back_populates="user", cascade="all, delete-orphan")
    cover_letters = db.relationship("CoverLetter",        back_populates="user", cascade="all, delete-orphan")
    applications  = db.relationship("Application",        back_populates="user", cascade="all, delete-orphan")
    automation    = db.relationship("AutomationSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Profile(db.Model):
    __tablename__ = "profiles"
    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    phone               = db.Column(db.String(30))
    location            = db.Column(db.String(120))
    linkedin_url        = db.Column(db.String(255))
    github_url          = db.Column(db.String(255))
    portfolio_url       = db.Column(db.String(255))
    skills              = db.Column(db.ARRAY(db.String), default=list)
    years_experience    = db.Column(db.Integer, default=0)
    preferred_roles     = db.Column(db.ARRAY(db.String), default=list)
    preferred_countries = db.Column(db.ARRAY(db.String), default=list)   # e.g. ["USA","Germany","UAE"]
    salary_expectation  = db.Column(db.Integer)
    work_preference     = db.Column(db.String(20), default="remote")
    work_authorization  = db.Column(db.String(60), default="requires_sponsorship")
    education           = db.Column(db.Text)
    experience_text     = db.Column(db.Text)
    base_resume_path    = db.Column(db.String(255))
    cover_letter_path   = db.Column(db.String(255))
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user                = db.relationship("User", back_populates="profile")


class AutomationSettings(db.Model):
    __tablename__ = "automation_settings"
    id                    = db.Column(db.Integer, primary_key=True)
    user_id               = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    is_running            = db.Column(db.Boolean, default=False)
    daily_limit           = db.Column(db.Integer, default=50)
    min_score             = db.Column(db.Integer, default=70)
    scan_interval_mins    = db.Column(db.Integer, default=30)
    min_salary            = db.Column(db.Integer, default=0)
    remote_only           = db.Column(db.Boolean, default=True)
    target_countries      = db.Column(db.ARRAY(db.String), default=list)  # country filter
    blacklisted_companies = db.Column(db.ARRAY(db.String), default=list)
    preferred_industries  = db.Column(db.ARRAY(db.String), default=list)
    use_linkedin          = db.Column(db.Boolean, default=True)
    use_indeed            = db.Column(db.Boolean, default=True)
    use_wellfound         = db.Column(db.Boolean, default=False)
    use_remoteok          = db.Column(db.Boolean, default=True)
    use_greenhouse        = db.Column(db.Boolean, default=True)
    auto_answer           = db.Column(db.Boolean, default=True)
    human_like            = db.Column(db.Boolean, default=True)
    skip_duplicates       = db.Column(db.Boolean, default=True)
    updated_at            = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user                  = db.relationship("User", back_populates="automation")


class Job(db.Model):
    __tablename__ = "jobs"
    id          = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(255), index=True)
    company     = db.Column(db.String(120), nullable=False)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    salary_min  = db.Column(db.Integer)
    salary_max  = db.Column(db.Integer)
    location    = db.Column(db.String(120))
    country     = db.Column(db.String(80))    # normalised country field for filtering
    remote      = db.Column(db.Boolean, default=False)
    apply_url   = db.Column(db.String(500), nullable=False)
    source      = db.Column(db.String(50))
    scraped_at  = db.Column(db.DateTime, default=datetime.utcnow)
    applications = db.relationship("Application", back_populates="job")


class Resume(db.Model):
    __tablename__ = "resumes"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id       = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)
    resume_path  = db.Column(db.String(255), nullable=False)
    job_title    = db.Column(db.String(255))
    company      = db.Column(db.String(120))
    ats_score    = db.Column(db.Integer)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    user         = db.relationship("User", back_populates="resumes")


class CoverLetter(db.Model):
    __tablename__ = "cover_letters"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id       = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)
    pdf_path     = db.Column(db.String(255), nullable=False)
    company      = db.Column(db.String(120))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    user         = db.relationship("User", back_populates="cover_letters")


class Application(db.Model):
    __tablename__ = "applications"
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id            = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    resume_id         = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=True)
    cover_letter_id   = db.Column(db.Integer, db.ForeignKey("cover_letters.id"), nullable=True)
    status            = db.Column(db.String(30), default="pending")
    match_score       = db.Column(db.Integer)
    applied_at        = db.Column(db.DateTime, default=datetime.utcnow)
    response_received = db.Column(db.DateTime, nullable=True)
    notes             = db.Column(db.Text)
    user              = db.relationship("User", back_populates="applications")
    job               = db.relationship("Job",  back_populates="applications")


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_type = db.Column(db.String(50))
    message    = db.Column(db.Text)
    meta       = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
