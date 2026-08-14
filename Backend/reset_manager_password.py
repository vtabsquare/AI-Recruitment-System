import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

USER_ID = "81a46fc6-c82f-45d2-9f66-99d2d4f43b1e"
NEW_PASSWORD = "vasanth@123"

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY is missing from .env"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

try:
    result = supabase.auth.admin.update_user_by_id(
        USER_ID,
        {
            "password": NEW_PASSWORD
        }
    )

    print("========================================")
    print("MANAGER PASSWORD UPDATED SUCCESSFULLY")
    print("========================================")
    print("Email: vasanththiru786573@gmail.com")
    print("User ID: " + USER_ID)
    print("Password was changed successfully.")
    print("========================================")

except Exception as error:
    print("PASSWORD UPDATE FAILED")
    print(error)