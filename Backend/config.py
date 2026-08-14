from dotenv import load_dotenv
import os


load_dotenv()


# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# Brevo
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")


# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")