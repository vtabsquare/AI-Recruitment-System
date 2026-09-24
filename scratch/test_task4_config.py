import sys
import os
from pathlib import Path

BACKEND_DIR = r"c:\Users\moham\OneDrive\Documents\AI-Recruitment-System-main\AI-Recruitment-System-main\Backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set dummy env vars for unconfigured services
os.environ.setdefault("GEMINI_API_KEY", "dummy_key_for_testing")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy_supabase_key")

import unittest
from unittest.mock import patch

class TestConfigAndSecretsHygiene(unittest.TestCase):

    def test_config_exports_all_required_variables(self):
        """Verify config.py exports all centralized application configuration variables."""
        import config

        required_attrs = [
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "BREVO_API_KEY",
            "BREVO_SENDER_EMAIL",
            "BREVO_SENDER_NAME",
            "BREVO_API_URL",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_ANON_KEY",
            "COMPANY_EMAIL",
            "INTERVIEW_MANAGER_EMAIL",
            "FRONTEND_URL",
            "ALLOWED_ORIGINS",
            "GOOGLE_CREDENTIALS_FILE",
            "GOOGLE_TOKEN_FILE",
        ]

        for attr in required_attrs:
            self.assertTrue(hasattr(config, attr), f"Missing config attribute: {attr}")

    def test_config_safe_fallbacks(self):
        """Verify config.py provides safe defaults for optional company and frontend settings."""
        import config

        self.assertEqual(config.COMPANY_EMAIL, "vitabsquare@gmail.com")
        self.assertEqual(config.BREVO_SENDER_NAME, "VTAB Square Recruitment")
        self.assertTrue(config.FRONTEND_URL in ("http://localhost:5173", "https://ai-recruitment-system-1-f6yw.onrender.com"))
        self.assertEqual(config.GEMINI_MODEL, "gemini-2.5-flash")
        self.assertTrue(any(origin in config.ALLOWED_ORIGINS for origin in ("localhost:5173", "onrender.com")))

    def test_reset_manager_password_no_hardcoded_plaintext(self):
        """Verify reset_manager_password.py no longer contains hardcoded plaintext passwords."""
        script_path = os.path.join(BACKEND_DIR, "reset_manager_password.py")
        with open(script_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertNotIn("vasanth@123", code)
        self.assertNotIn("NEW_PASSWORD = \"", code)
        self.assertIn("RESET_NEW_PASSWORD", code)

    def test_email_service_uses_config(self):
        """Verify email_service uses the centralized configuration module."""
        import email_service
        import config

        self.assertEqual(email_service.BREVO_API_URL, config.BREVO_API_URL)
        self.assertEqual(email_service.BREVO_SENDER_NAME, config.BREVO_SENDER_NAME)

    def test_gmail_reader_uses_config_email(self):
        """Verify gmail_reader reflects the centralized COMPANY_EMAIL."""
        import gmail_reader
        import config

        self.assertEqual(gmail_reader.COMPANY_EMAIL, config.COMPANY_EMAIL)

    def test_reply_pipeline_uses_config_emails(self):
        """Verify reply_pipeline reflects centralized COMPANY_EMAIL and INTERVIEW_MANAGER_EMAIL."""
        import reply_pipeline
        import config

        self.assertEqual(reply_pipeline.COMPANY_EMAIL, config.COMPANY_EMAIL)
        self.assertEqual(reply_pipeline.INTERVIEW_MANAGER_EMAIL, config.INTERVIEW_MANAGER_EMAIL)

    def test_env_example_has_no_secrets(self):
        """Verify .env.example contains only placeholders and no real secrets."""
        env_example_path = os.path.join(BACKEND_DIR, ".env.example")
        with open(env_example_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                # Ensure no live API keys or passwords are in example
                self.assertFalse(val.startswith("xkeysib-"), f"Real Brevo key found in .env.example: {key}")
                self.assertFalse(val.startswith("AIza"), f"Real Google key found in .env.example: {key}")
                self.assertFalse(val.startswith("sbp_"), f"Real Supabase key found in .env.example: {key}")

    def test_fastapi_app_imports_cleanly(self):
        """Verify FastAPI app imports without errors with centralized configuration."""
        import app
        self.assertTrue(hasattr(app, "app"))

if __name__ == "__main__":
    unittest.main()
