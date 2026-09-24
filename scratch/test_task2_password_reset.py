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
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Test suite for Task 2: Self-Service Password Reset & Login Stability

class TestPasswordResetAndLogin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.client = TestClient(app)

    # ============================================================
    # 1. EXISTING LOGIN VERIFICATION (PRESERVED BEHAVIOR)
    # ============================================================

    def test_existing_login_success(self):
        """Verify normal login works exactly as before with valid credentials."""
        from app import supabase

        mock_auth_res = MagicMock()
        mock_auth_res.session.access_token = "mock_valid_token"
        mock_auth_res.session.refresh_token = "mock_refresh_token"
        mock_auth_res.user.id = "user_123"

        mock_staff_data = [{
            "id": "staff_123",
            "full_name": "Test Manager",
            "email": "manager@vtab.com",
            "role": "manager",
            "is_active": True
        }]

        with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
             patch.object(supabase, "table") as mock_table:

            mock_query = MagicMock()
            mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data

            resp = self.client.post("/api/auth/login", json={
                "email": "manager@vtab.com",
                "password": "Password123!"
            })

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["access_token"], "mock_valid_token")
            self.assertEqual(data["staff"]["role"], "manager")

    def test_existing_login_invalid_password_rejected(self):
        """Verify normal login rejects invalid credentials with 401."""
        from app import supabase

        with patch.object(supabase.auth, "sign_in_with_password", side_effect=Exception("Invalid login credentials")):
            resp = self.client.post("/api/auth/login", json={
                "email": "manager@vtab.com",
                "password": "WrongPassword!"
            })
            self.assertEqual(resp.status_code, 401)
            self.assertIn("Login failed", resp.json()["detail"])

    def test_existing_login_inactive_staff_rejected(self):
        """Verify inactive staff members are rejected with 403."""
        from app import supabase

        mock_auth_res = MagicMock()
        mock_auth_res.session.access_token = "mock_token"
        mock_auth_res.user.id = "user_inactive"

        with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
             patch.object(supabase, "table") as mock_table:

            # No active staff found
            mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

            resp = self.client.post("/api/auth/login", json={
                "email": "inactive@vtab.com",
                "password": "Password123!"
            })
            self.assertEqual(resp.status_code, 403)
            self.assertIn("not an active staff member", resp.json()["detail"])

    # ============================================================
    # 2. FORGOT PASSWORD TESTS (ANTI-ENUMERATION & SECURITY)
    # ============================================================

    def test_forgot_password_invalid_email_format(self):
        """Verify malformed email addresses are rejected with 400."""
        resp = self.client.post("/api/auth/forgot-password", json={
            "email": "not-an-email"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid email address format", resp.json()["detail"])

    def test_forgot_password_empty_email_rejected(self):
        """Verify empty email is rejected by request validation."""
        resp = self.client.post("/api/auth/forgot-password", json={
            "email": ""
        })
        self.assertEqual(resp.status_code, 422)

    def test_forgot_password_active_staff_triggers_reset(self):
        """Verify active staff email triggers Supabase reset_password_for_email."""
        from app import supabase

        mock_staff_data = [{
            "id": "staff_123",
            "email": "hr@vtab.com",
            "is_active": True
        }]

        with patch.object(supabase, "table") as mock_table, \
             patch.object(supabase.auth, "reset_password_for_email") as mock_reset:

            mock_table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data

            resp = self.client.post("/api/auth/forgot-password", json={
                "email": "hr@vtab.com"
            }, headers={"origin": "http://localhost:5173"})

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertIn("password reset instructions have been sent", data["message"])
            mock_reset.assert_called_once()
            call_args = mock_reset.call_args
            self.assertEqual(call_args[0][0], "hr@vtab.com")
            self.assertIn("http://localhost:5173", call_args[1]["options"]["redirect_to"])

    def test_forgot_password_unregistered_email_anti_enumeration(self):
        """CRITICAL SECURITY: Unregistered emails receive the exact same 200 response to prevent enumeration."""
        from app import supabase

        with patch.object(supabase, "table") as mock_table, \
             patch.object(supabase.auth, "reset_password_for_email") as mock_reset:

            # Email not found in staff_users
            mock_table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

            resp = self.client.post("/api/auth/forgot-password", json={
                "email": "unknown_stranger@example.com"
            })

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            # Identical safe response
            self.assertIn("password reset instructions have been sent", data["message"])
            # reset_password_for_email was NOT called for non-staff
            mock_reset.assert_not_called()

    def test_forgot_password_supabase_fallback_to_admin_link(self):
        """Verify fallback to admin.generate_link and email delivery when Supabase SMTP fails."""
        from app import supabase
        import app

        mock_staff_data = [{
            "id": "staff_123",
            "email": "manager@vtab.com",
            "is_active": True
        }]

        mock_link_res = MagicMock()
        mock_link_res.properties.action_link = "https://supabase.co/verify?token=123"

        with patch.object(supabase, "table") as mock_table, \
             patch.object(supabase.auth, "reset_password_for_email", side_effect=Exception("SMTP not configured")), \
             patch.object(supabase.auth.admin, "generate_link", return_value=mock_link_res) as mock_gen, \
             patch("app.send_email") as mock_send:

            mock_table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data

            resp = self.client.post("/api/auth/forgot-password", json={
                "email": "manager@vtab.com"
            })

            self.assertEqual(resp.status_code, 200)
            mock_gen.assert_called_once()
            mock_send.assert_called_once()
            self.assertEqual(mock_send.call_args[1]["recipient_email"], "manager@vtab.com")

    # ============================================================
    # 3. RESET PASSWORD TESTS (TOKEN VALIDATION & PASSWORD UPDATE)
    # ============================================================

    def test_reset_password_missing_token(self):
        """Verify reset password rejects requests with missing or empty token."""
        resp = self.client.post("/api/auth/reset-password", json={
            "token": "",
            "password": "NewSecretPassword123"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Password reset token is required", resp.json()["detail"])

    def test_reset_password_short_password_rejected(self):
        """Verify passwords under 6 characters are rejected with 422 or 400."""
        resp = self.client.post("/api/auth/reset-password", json={
            "token": "valid_token_xyz",
            "password": "123"
        })
        self.assertIn(resp.status_code, (400, 422))

    def test_reset_password_invalid_expired_token(self):
        """Verify invalid or expired tokens return a user-friendly 400 error."""
        from app import supabase

        with patch.object(supabase.auth, "get_user", side_effect=Exception("JWT expired")), \
             patch.object(supabase.auth, "verify_otp", side_effect=Exception("Token invalid")):

            resp = self.client.post("/api/auth/reset-password", json={
                "token": "expired_jwt_token",
                "password": "NewValidPassword123"
            })
            self.assertEqual(resp.status_code, 400)
            self.assertIn("invalid or has expired", resp.json()["detail"])

    def test_reset_password_success(self):
        """Verify valid token updates user password via Supabase admin and succeeds."""
        from app import supabase

        mock_user = MagicMock()
        mock_user.id = "user_456"
        mock_user.email = "staff@vtab.com"

        mock_user_resp = MagicMock()
        mock_user_resp.user = mock_user

        with patch.object(supabase.auth, "get_user", return_value=mock_user_resp), \
             patch.object(supabase.auth.admin, "update_user_by_id") as mock_update:

            resp = self.client.post("/api/auth/reset-password", json={
                "token": "valid_jwt_recovery_token",
                "password": "NewSecurePassword456!"
            })

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertIn("Password updated successfully", data["message"])
            mock_update.assert_called_once_with("user_456", {"password": "NewSecurePassword456!"})

    # ============================================================
    # 4. REGRESSION VERIFICATION
    # ============================================================

    def test_existing_endpoints_intact(self):
        """Verify existing application endpoints remain registered and intact."""
        from app import app
        route_paths = [r.path for r in app.routes]
        self.assertIn("/api/auth/login", route_paths)
        self.assertIn("/api/candidates", route_paths)
        self.assertIn("/api/candidate-ai", route_paths)
        self.assertIn("/api/interview-feedback", route_paths)
        self.assertIn("/api/manager/candidate-decision", route_paths)

if __name__ == "__main__":
    unittest.main()
