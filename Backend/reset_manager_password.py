import os
import sys
import getpass
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

USER_ID = os.getenv("RESET_USER_ID", "81a46fc6-c82f-45d2-9f66-99d2d4f43b1e").strip()

# Safely obtain new password: env var -> command-line argument -> interactive prompt
NEW_PASSWORD = os.getenv("RESET_NEW_PASSWORD", "").strip()
if not NEW_PASSWORD:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        NEW_PASSWORD = sys.argv[1].strip()
    else:
        try:
            NEW_PASSWORD = getpass.getpass("Enter new manager password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(1)

if not NEW_PASSWORD or len(NEW_PASSWORD) < 6:
    raise ValueError("Password must be at least 6 characters long.")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing from .env")

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
    print("User ID: " + USER_ID)
    print("Password was changed successfully.")
    print("========================================")

except Exception as error:
    print("PASSWORD UPDATE FAILED")
    print(error)