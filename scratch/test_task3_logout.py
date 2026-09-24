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

# Test suite for Task 3: Session Security — Server-Side Logout / Session Invalidation

class TestServerSideLogout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.client = TestClient(app)

    # ============================================================
    # 1. EXISTING AUTHENTICATION STILL WORKS
    # ============================================================

    def test_login_works_normally(self):
        """Verify normal login endpoint continues issuing valid sessions."""
        from app import supabase

        mock_auth_res = MagicMock()
        mock_auth_res.session.access_token = "valid_manager_jwt_token_1"
        mock_auth_res.session.refresh_token = "valid_refresh_token_1"
        mock_auth_res.user.id = "manager_user_1"

        mock_staff_data = [{
            "id": "staff_1",
            "full_name": "Test Manager",
            "email": "manager@vtab.com",
            "role": "manager",
            "is_active": True
        }]

        with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
             patch.object(supabase, "table") as mock_table:

            mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data

            resp = self.client.post("/api/auth/login", json={
                "email": "manager@vtab.com",
                "password": "ValidPassword123!"
            })
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["success"])
            self.assertEqual(resp.json()["access_token"], "valid_manager_jwt_token_1")

    def test_protected_route_access_before_logout(self):
        """Verify protected route allows access when provided with a valid, active bearer token."""
        from app import supabase

        mock_user_resp = MagicMock()
        mock_user_resp.user.id = "user_active_1"
        mock_user_resp.user.email = "manager@vtab.com"

        mock_staff_data = [{
            "id": "staff_1",
            "full_name": "Active Manager",
            "email": "manager@vtab.com",
            "role": "manager",
            "is_active": True
        }]

        with patch.object(supabase.auth, "get_user", return_value=mock_user_resp), \
             patch.object(supabase, "table") as mock_table:

            # Return staff member for auth check, then empty candidates list
            mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data
            mock_table.return_value.select.return_value.order.return_value.execute.return_value.data = []

            headers = {"Authorization": "Bearer active_token_xyz"}
            resp = self.client.get("/api/candidates", headers=headers)
            self.assertEqual(resp.status_code, 200)

    # ============================================================
    # 2. SERVER-SIDE LOGOUT & SESSION INVALIDATION
    # ============================================================

    def test_logout_endpoint_success_and_invalidation(self):
        """Verify calling /api/auth/logout invalidates token and subsequently blocks protected access."""
        from app import supabase, is_token_revoked

        token_to_logout = "test_user_session_token_to_revoke_123"

        # Check token is not revoked initially
        self.assertFalse(is_token_revoked(token_to_logout))

        with patch.object(supabase.auth.admin, "sign_out") as mock_admin_sign_out:
            # 1. Call logout
            resp = self.client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token_to_logout}"}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["message"], "Successfully logged out.")

            # 2. Verify Supabase admin.sign_out was notified
            mock_admin_sign_out.assert_called_once_with(token_to_logout, scope="local")

            # 3. Verify server-side token revocation cache registers the token
            self.assertTrue(is_token_revoked(token_to_logout))

            # 4. CRITICAL: Try accessing protected endpoint with the logged-out token -> must be rejected with 401
            resp_after_logout = self.client.get(
                "/api/candidates",
                headers={"Authorization": f"Bearer {token_to_logout}"}
            )
            self.assertEqual(resp_after_logout.status_code, 401)
            self.assertIn("Session has been logged out", resp_after_logout.json()["detail"])

    def test_session_isolation_other_user_unaffected(self):
        """CRITICAL: Verify logging out User A does NOT invalidate User B's active session."""
        from app import supabase, is_token_revoked

        token_user_a = "token_for_user_alpha"
        token_user_b = "token_for_user_beta"

        # User A logs out
        with patch.object(supabase.auth.admin, "sign_out"):
            resp_logout_a = self.client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token_user_a}"}
            )
            self.assertEqual(resp_logout_a.status_code, 200)

        # Assert User A is revoked
        self.assertTrue(is_token_revoked(token_user_a))

        # Assert User B is NOT revoked
        self.assertFalse(is_token_revoked(token_user_b))

        # User B can still access protected routes
        mock_user_b = MagicMock()
        mock_user_b.user.id = "user_b_id"
        mock_user_b.user.email = "user_b@vtab.com"

        mock_staff_b = [{
            "id": "staff_b",
            "full_name": "User Beta",
            "email": "user_b@vtab.com",
            "role": "manager",
            "is_active": True
        }]

        with patch.object(supabase.auth, "get_user", return_value=mock_user_b), \
             patch.object(supabase, "table") as mock_table:

            mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_b
            mock_table.return_value.select.return_value.order.return_value.execute.return_value.data = []

            resp_b = self.client.get(
                "/api/candidates",
                headers={"Authorization": f"Bearer {token_user_b}"}
            )
            self.assertEqual(resp_b.status_code, 200)

    def test_logout_idempotent_and_safe_with_missing_or_expired_token(self):
        """Verify logout returns 200 OK safely even if token is already expired, missing, or malformed."""
        # 1. Missing Authorization header
        resp_no_token = self.client.post("/api/auth/logout")
        self.assertEqual(resp_no_token.status_code, 200)
        self.assertTrue(resp_no_token.json()["success"])

        # 2. Empty bearer token
        resp_empty_token = self.client.post("/api/auth/logout", headers={"Authorization": "Bearer "})
        self.assertEqual(resp_empty_token.status_code, 200)
        self.assertTrue(resp_empty_token.json()["success"])

        # 3. Repeated logout on same token
        token = "repeat_logout_token"
        resp_1 = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp_1.status_code, 200)
        resp_2 = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp_2.status_code, 200)

    def test_logout_handles_supabase_exception_gracefully(self):
        """Verify logout still succeeds and revokes locally even if Supabase Auth network fails."""
        from app import supabase, is_token_revoked

        token = "network_fail_token_999"

        with patch.object(supabase.auth.admin, "sign_out", side_effect=Exception("Supabase network timeout")):
            resp = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["success"])
            # Token was still revoked locally
            self.assertTrue(is_token_revoked(token))

    # ============================================================
    # 3. REGRESSION & INTEGRITY VERIFICATION
    # ============================================================

    def test_regression_all_auth_routes_registered(self):
        """Verify all auth endpoints are registered properly."""
        from app import app
        paths = [r.path for r in app.routes]
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/auth/logout", paths)
        self.assertIn("/api/auth/forgot-password", paths)
        self.assertIn("/api/auth/reset-password", paths)

if __name__ == "__main__":
    unittest.main()
