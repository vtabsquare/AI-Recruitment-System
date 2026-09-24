import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ============================================================
# GOOGLE GEMINI AI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()


# ============================================================
# BREVO (TRANSACTIONAL EMAIL) CONFIGURATION
# ============================================================

BREVO_API_URL = os.getenv(
    "BREVO_API_URL",
    "https://api.brevo.com/v3/smtp/email"
).strip()

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "").strip()
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "VTAB Square Recruitment").strip()


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()

# SUPABASE_KEY: prefers service role key for backend administration, falls back to anon key
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
).strip()

SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()


# ============================================================
# COMPANY & RECRUITMENT DEFAULTS
# ============================================================

COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "vitabsquare@gmail.com").strip().lower()

INTERVIEW_MANAGER_EMAIL = (
    os.getenv("INTERVIEW_MANAGER_EMAIL")
    or os.getenv("INTERVIEWER_EMAIL")
    or COMPANY_EMAIL
).strip().lower()


# ============================================================
# FRONTEND & CORS CONFIGURATION
# ============================================================

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
).strip()


# ============================================================
# GOOGLE OAUTH & SERVICE FILES
# ============================================================

GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    str(BASE_DIR / "credentials.json")
).strip()

GOOGLE_TOKEN_FILE = os.getenv(
    "GOOGLE_TOKEN_FILE",
    str(BASE_DIR / "token.json")
).strip()

GOOGLE_TOKEN_JSON = os.getenv("GOOGLE_TOKEN_JSON", "").strip()


# ============================================================
# OBSERVABILITY & ERROR MONITORING (OPTIONAL)
# ============================================================

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
ENVIRONMENT = os.getenv("ENVIRONMENT", "production" if os.getenv("RENDER") else "development").strip()