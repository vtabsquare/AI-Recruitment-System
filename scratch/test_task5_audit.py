"""
test_task5_audit.py
===================
Comprehensive test suite for Task 5: Comprehensive Activity Logging & Audit Trail.
"""
import sys
import os
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "OneDrive", "Documents", "AI-Recruitment-System-main", "AI-Recruitment-System-main", "Backend"))
if not os.path.exists(backend_dir):
    backend_dir = r"c:\Users\moham\OneDrive\Documents\AI-Recruitment-System-main\AI-Recruitment-System-main\Backend"

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault("GEMINI_API_KEY", "dummy_key")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy_key")

from audit_service import sanitize_audit_data, is_sensitive_key, log_audit_event
from fastapi.testclient import TestClient
from app import app, supabase, require_hr

client = TestClient(app, raise_server_exceptions=False)


def run_tests():
    passed = 0
    total = 0

    def check(title, condition):
        nonlocal passed, total
        total += 1
        if condition:
            print(f"  [PASS] {title}")
            passed += 1
        else:
            print(f"  [FAIL] {title}")

    print("=== Section 1: Secrets Hygiene & Sanitization Tests ===")

    check("is_sensitive_key detects password", is_sensitive_key("password"))
    check("is_sensitive_key detects new_password", is_sensitive_key("new_password"))
    check("is_sensitive_key detects access_token", is_sensitive_key("access_token"))
    check("is_sensitive_key detects refresh_token", is_sensitive_key("refresh_token"))
    check("is_sensitive_key detects api_key", is_sensitive_key("api_key"))
    check("is_sensitive_key detects authorization", is_sensitive_key("authorization"))
    check("is_sensitive_key allows non-sensitive 'email'", not is_sensitive_key("email"))
    check("is_sensitive_key allows non-sensitive 'status'", not is_sensitive_key("status"))

    test_dict = {
        "email": "manager@vtabsquare.com",
        "password": "SuperSecretPassword123!",
        "new_password": "NewSecretPassword456!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
        "role": "manager",
        "nested": {
            "api_key": "live_key_9999",
            "candidate_id": "c1234",
            "token": "tok_abcdef123456",
        },
        "items": [
            {"secret_code": "xyz", "status": "approved"},
            "regular_string",
        ],
    }

    sanitized = sanitize_audit_data(test_dict)

    check("Password was redacted", sanitized["password"] == "[REDACTED]")
    check("New password was redacted", sanitized["new_password"] == "[REDACTED]")
    check("Access token was redacted", sanitized["access_token"] == "[REDACTED]")
    check("Nested api_key was redacted", sanitized["nested"]["api_key"] == "[REDACTED]")
    check("Nested token was redacted", sanitized["nested"]["token"] == "[REDACTED]")
    check("Nested list sensitive field redacted", sanitized["items"][0]["secret_code"] == "[REDACTED]")
    check("Email was preserved", sanitized["email"] == "manager@vtabsquare.com")
    check("Role was preserved", sanitized["role"] == "manager")
    check("Candidate ID was preserved", sanitized["nested"]["candidate_id"] == "c1234")
    check("List item status was preserved", sanitized["items"][0]["status"] == "approved")
    check("List string item was preserved", sanitized["items"][1] == "regular_string")

    bearer_str = "Authorization was Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig with data"
    sanitized_bearer = sanitize_audit_data(bearer_str)
    check("Embedded Bearer/JWT in string was redacted", "[REDACTED_TOKEN]" in sanitized_bearer and "eyJ" not in sanitized_bearer)

    print("\n=== Section 2: log_audit_event Schema & Operation Tests ===")

    recorded_inserts = []

    def mock_table_success(table_name):
        mock_t = MagicMock()
        if table_name == "audit_logs":
            def fake_insert(payload):
                mock_exec = MagicMock()
                mock_exec.execute = MagicMock(side_effect=lambda: recorded_inserts.append(payload))
                return mock_exec
            mock_t.insert = fake_insert
        return mock_t

    with patch.object(supabase, "table", side_effect=mock_table_success):
        res = log_audit_event(
            action="staff_login_success",
            staff_user_id="staff-uuid-1",
            table_name="staff_users",
            record_id="rec-uuid-1",
            new_data={"email": "hr@vtab.com", "password": "should_be_redacted"},
        )

    check("log_audit_event returned True on success", res is True)
    check("Payload inserted correctly", len(recorded_inserts) == 1)
    if recorded_inserts:
        payload = recorded_inserts[0]
        check("Action matches in payload", payload["action"] == "staff_login_success")
        check("Staff user id matches", payload["staff_user_id"] == "staff-uuid-1")
        check("Table name matches", payload["table_name"] == "staff_users")
        check("Record id matches", payload["record_id"] == "rec-uuid-1")
        check("Password in new_data was redacted before DB write", payload["new_data"]["password"] == "[REDACTED]")
        check("Email in new_data was preserved", payload["new_data"]["email"] == "hr@vtab.com")

    empty_res = log_audit_event("")
    check("Empty action returns False without raising", empty_res is False)

    print("\n=== Section 3: Non-Blocking / Fault-Tolerance Isolation Tests ===")

    def mock_table_failing_audit(table_name):
        mock_t = MagicMock()
        if table_name == "audit_logs":
            mock_t.insert.return_value.execute.side_effect = RuntimeError("Supabase connection timeout / DB down")
        elif table_name == "staff_users":
            mock_t.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"id": "staff_123", "full_name": "Test Manager", "email": "manager@vtabsquare.com", "role": "manager", "is_active": True}
            ]
            mock_t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"id": "staff_123", "email": "manager@vtabsquare.com", "is_active": True}
            ]
        return mock_t

    with patch.object(supabase, "table", side_effect=mock_table_failing_audit):
        try:
            fail_res = log_audit_event("any_action", new_data={"foo": "bar"})
            check("log_audit_event suppressed DB exception and returned False", fail_res is False)
        except Exception as e:
            check(f"log_audit_event leaked exception: {e}", False)

    mock_session = MagicMock()
    mock_session.access_token = "mock_jwt_access"
    mock_session.refresh_token = "mock_jwt_refresh"
    mock_user = MagicMock()
    mock_user.id = "user_uuid_123"
    mock_user.email = "manager@vtabsquare.com"
    mock_auth_res = MagicMock(session=mock_session, user=mock_user)

    with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
         patch.object(supabase, "table", side_effect=mock_table_failing_audit):

        response = client.post(
            "/api/auth/login",
            json={"email": "manager@vtabsquare.com", "password": "Password123!"}
        )

    check("Login endpoint returns 200 OK despite audit log failure", response.status_code == 200)
    login_data = response.json()
    check("Login returns success=True", login_data.get("success") is True)
    check("Login returns valid access token", login_data.get("access_token") == "mock_jwt_access")

    with patch.object(supabase, "table", side_effect=mock_table_failing_audit), \
         patch.object(supabase.auth, "get_user", return_value=MagicMock(user=mock_user)), \
         patch.object(supabase.auth.admin, "sign_out", return_value=None):
        logout_resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer mock_jwt_access"}
        )

    check("Logout endpoint returns 200 OK despite audit log failure", logout_resp.status_code == 200)
    check("Logout returns success=True", logout_resp.json().get("success") is True)

    with patch.object(supabase, "table", side_effect=mock_table_failing_audit), \
         patch.object(supabase.auth, "reset_password_for_email", return_value=None):

        fp_resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "manager@vtabsquare.com"}
        )

    check("Forgot password returns 200 OK despite audit log failure", fp_resp.status_code == 200)
    check("Forgot password message returned", fp_resp.json().get("success") is True)

    mock_user_obj = MagicMock()
    mock_user_obj.id = "user_uuid_123"
    mock_get_user = MagicMock(user=mock_user_obj)

    with patch.object(supabase.auth, "get_user", return_value=mock_get_user), \
         patch.object(supabase.auth.admin, "update_user_by_id", return_value=MagicMock()), \
         patch.object(supabase, "table", side_effect=mock_table_failing_audit):

        rp_resp = client.post(
            "/api/auth/reset-password",
            json={"token": "valid_recovery_token", "password": "NewValidPassword123!"}
        )

    check("Reset password returns 200 OK despite audit log failure", rp_resp.status_code == 200)
    check("Reset password returns success=True", rp_resp.json().get("success") is True)

    print("\n=== Section 4: Business Errors Not Swallowed Tests ===")

    with patch.object(supabase.auth, "sign_in_with_password", side_effect=Exception("Invalid login credentials")), \
         patch.object(supabase, "table", side_effect=mock_table_success):

        bad_login_resp = client.post(
            "/api/auth/login",
            json={"email": "hacker@example.com", "password": "WrongPassword!"}
        )

    check("Invalid login credentials returns 401 Unauthorized", bad_login_resp.status_code == 401)

    def mock_table_empty_staff(table_name):
        mock_t = MagicMock()
        mock_t.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        return mock_t

    with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
         patch.object(supabase, "table", side_effect=mock_table_empty_staff):

        inactive_resp = client.post(
            "/api/auth/login",
            json={"email": "manager@vtabsquare.com", "password": "Password123!"}
        )

    check("Inactive staff returns 403 Forbidden", inactive_resp.status_code == 403)

    short_pw_resp = client.post(
        "/api/auth/reset-password",
        json={"token": "valid_token", "password": "123"}
    )
    check("Reset password with short password rejected (400 or 422)", short_pw_resp.status_code in {400, 422})

    with patch.object(supabase.auth, "get_user", side_effect=Exception("Invalid token")), \
         patch.object(supabase.auth, "verify_otp", side_effect=Exception("Invalid OTP")):

        invalid_token_resp = client.post(
            "/api/auth/reset-password",
            json={"token": "bad_token", "password": "NewPassword123!"}
        )
    check("Reset password with invalid token returns 400 Bad Request", invalid_token_resp.status_code == 400)

    print("\n=== Section 5: End-to-End Audit Log Recording Tests ===")

    def mock_table_tracking(table_name):
        mock_t = MagicMock()
        if table_name == "audit_logs":
            def fake_insert(payload):
                mock_exec = MagicMock()
                mock_exec.execute = MagicMock(side_effect=lambda: recorded_inserts.append(payload))
                return mock_exec
            mock_t.insert = fake_insert
        elif table_name == "staff_users":
            mock_t.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"id": "staff_123", "full_name": "Test Manager", "email": "manager@vtabsquare.com", "role": "manager", "is_active": True}
            ]
            mock_t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"id": "staff_123", "email": "manager@vtabsquare.com", "is_active": True}
            ]
        return mock_t

    recorded_inserts.clear()
    with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
         patch.object(supabase, "table", side_effect=mock_table_tracking):

        resp = client.post(
            "/api/auth/login",
            json={"email": "manager@vtabsquare.com", "password": "Password123!"}
        )

    check("Successful login executed", resp.status_code == 200)
    login_events = [e for e in recorded_inserts if e.get("action") == "staff_login_success"]
    check("staff_login_success recorded in audit_logs", len(login_events) == 1)
    if login_events:
        check("Staff user ID in audit event", login_events[0]["staff_user_id"] == "staff_123")
        check("No password in login audit event", "password" not in login_events[0]["new_data"])

    recorded_inserts.clear()
    with patch.object(supabase.auth, "sign_in_with_password", side_effect=Exception("Invalid credentials")), \
         patch.object(supabase, "table", side_effect=mock_table_tracking):

        fail_login_resp = client.post(
            "/api/auth/login",
            json={"email": "unknown@example.com", "password": "SecretPassword123!"}
        )

    failed_events = [e for e in recorded_inserts if e.get("action") == "staff_login_failed"]
    check("staff_login_failed recorded in audit_logs", len(failed_events) >= 1)
    if failed_events:
        check("Failed login recorded attempted email", failed_events[0]["new_data"].get("email") == "unknown@example.com")
        check("No plaintext password recorded in failed login audit", "password" not in failed_events[0]["new_data"])

    recorded_inserts.clear()
    with patch.object(supabase, "table", side_effect=mock_table_tracking), \
         patch.object(supabase.auth, "reset_password_for_email", return_value=None):

        fp_res = client.post(
            "/api/auth/forgot-password",
            json={"email": "manager@vtabsquare.com"}
        )

    fp_events = [e for e in recorded_inserts if e.get("action") == "password_reset_requested"]
    check("password_reset_requested recorded in audit_logs", len(fp_events) == 1)
    if fp_events:
        check("Audit record references staff ID", fp_events[0]["staff_user_id"] == "staff_123")
        check("No tokens in password reset requested log", "token" not in fp_events[0]["new_data"])

    recorded_inserts.clear()
    with patch.object(supabase.auth, "get_user", return_value=mock_get_user), \
         patch.object(supabase.auth.admin, "update_user_by_id", return_value=MagicMock()), \
         patch.object(supabase, "table", side_effect=mock_table_tracking):

        rp_res = client.post(
            "/api/auth/reset-password",
            json={"token": "valid_token", "password": "NewSecretPassword123!"}
        )

    rp_events = [e for e in recorded_inserts if e.get("action") == "password_reset_completed"]
    check("password_reset_completed recorded in audit_logs", len(rp_events) == 1)
    if rp_events:
        check("Audit record references user UUID", rp_events[0]["record_id"] == "user_uuid_123")
        check("No plaintext password in audit log", "password" not in rp_events[0]["new_data"] or rp_events[0]["new_data"]["password"] == "[REDACTED]")

    mock_audit_records = [
        {"id": "log-1", "action": "staff_login_success", "created_at": "2026-09-23T10:00:00Z"},
        {"id": "log-2", "action": "final_hr_offer_approved", "created_at": "2026-09-23T11:00:00Z"},
    ]
    app.dependency_overrides[require_hr] = lambda: {"id": "hr_1", "role": "hr"}
    try:
        with patch("app.safe_select_all", return_value={"available": True, "data": mock_audit_records}):
            hr_audit_resp = client.get("/api/hr/audit-logs")

        check("GET /api/hr/audit-logs returns 200 OK", hr_audit_resp.status_code == 200)
        audit_data = hr_audit_resp.json()
        check("GET /api/hr/audit-logs returns success=True", audit_data.get("success") is True)
        check("GET /api/hr/audit-logs returns log items", len(audit_data.get("data", [])) == 2)
    finally:
        app.dependency_overrides.pop(require_hr, None)

    print(f"\n==========================================")
    print(f"Task 5 Test Results: {passed}/{total} Passed")
    print(f"==========================================")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
