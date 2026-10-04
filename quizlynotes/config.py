"""Application configuration, read from environment variables."""
import os


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # Local development only. Never rely on SQLite inside a container:
        # Cloud Run wipes the filesystem whenever an instance is replaced.
        return "sqlite:///" + os.path.join(os.getcwd(), "instance", "dev.db")
    # Neon / Supabase / Heroku style URLs -> SQLAlchemy + psycopg 3 driver.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    ENV = os.getenv("APP_ENV", "development")
    IS_PRODUCTION = ENV == "production"

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or os.getenv("SECRET_KEY")

    SITE_URL = os.getenv("SITE_URL", "https://quizlynotes.com").rstrip("/")
    SITE_NAME = "QuizlyNotes"
    CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "quizlynotes@gmail.com")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Serverless Postgres (Neon) closes idle connections; check before use.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Uploads: Gemini's Files API takes up to 50MB; Cloud Run caps request
    # bodies at 32MB, so stay safely under that.
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "150"))
    MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "300000"))

    # AI
    AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")  # "gemini" or "fake"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    # Cheaper model for small jobs (guest demo, "improve section").
    GEMINI_FAST_MODEL = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
    # Tried automatically when the main model is overloaded.
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")

    # --- Billing -----------------------------------------------------------
    # Pro is unlocked by Stripe subscriptions, the signup trial, referral
    # bonuses, promo codes, or being listed in ADMIN_EMAILS.
    # Plans, limits, trials, referrals and payments. While off, everyone gets
    # the full product (with Pro's fair-use caps) and nothing mentions Pro.
    MONETISATION_ENABLED = _bool("MONETISATION_ENABLED", False)
    ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")
    STRIPE_PRICE_YEARLY = os.getenv("STRIPE_PRICE_YEARLY", "")
    # Shown on the pricing page; keep in sync with the Stripe prices.
    PRICE_MONTHLY_DISPLAY = os.getenv("PRICE_MONTHLY_DISPLAY", "£4.99")
    PRICE_YEARLY_DISPLAY = os.getenv("PRICE_YEARLY_DISPLAY", "£29.99")
    PRICE_YEARLY_PER_MONTH_DISPLAY = os.getenv("PRICE_YEARLY_PER_MONTH_DISPLAY", "£2.50")
    TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))
    REFERRED_TRIAL_DAYS = int(os.getenv("REFERRED_TRIAL_DAYS", "14"))
    REFERRAL_REWARD_DAYS = int(os.getenv("REFERRAL_REWARD_DAYS", "7"))
    REFERRAL_MAX_REWARD_DAYS = int(os.getenv("REFERRAL_MAX_REWARD_DAYS", "90"))

    # Google sign-in
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    # Local developer login (never enable in production).
    ENABLE_DEV_LOGIN = _bool("ENABLE_DEV_LOGIN", False)

    # Public "try it" box on the landing pages.
    ENABLE_GUEST_DEMO = _bool("ENABLE_GUEST_DEMO", True)
    GUEST_DEMO_MAX_CHARS = 6000

    # Rate limits (Flask-Limiter syntax)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    GENERATION_LIMIT = os.getenv("GENERATION_LIMIT", "30 per hour;100 per day")
    GUEST_LIMIT = os.getenv("GUEST_LIMIT", "1 per minute;4 per day")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    WTF_CSRF_TIME_LIMIT = None  # tokens live as long as the session


class TestConfig(Config):
    TESTING = True
    ENV = "test"
    IS_PRODUCTION = False
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AI_PROVIDER = "fake"
    ENABLE_DEV_LOGIN = True
    MONETISATION_ENABLED = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SESSION_COOKIE_SECURE = False
