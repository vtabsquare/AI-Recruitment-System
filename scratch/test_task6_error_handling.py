"""
Task 6: Error Handling / API Error Sanitization Test Suite
----------------------------------------------------------
Comprehensive verification that internal implementation details:
- Python stack traces
- database errors / SQL details
- filesystem paths
- internal library / SDK errors
- service credentials, secrets, and tokens
are NEVER exposed to the frontend/client, while:
- Successful API responses (200 OK) remain completely unchanged
- Intentional business errors (400, 401, 403, 404, 422) are strictly preserved
- Diagnostic error information is safely logged server-side with secrets redacted.
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import io

backend_dir = Path(__file__).resolve().parent.parent / "Backend"
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("GEMINI_API_KEY", "dummy_key")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy_key")

from fastapi.testclient import TestClient
from app import (
    app,
    supabase,
    log_internal_error,
    sanitize_error_detail,
    safe_select_all,
    require_manager,
    require_hr,
    require_staff,
    get_current_staff,
    GENERIC_INTERNAL_ERROR,
    LEAK_INDICATORS,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

client = TestClient(app, raise_server_exceptions=False)

passed_count = 0
failed_count = 0


def check(name: str, condition: bool, details: str = ""):
    global passed_count, failed_count
    if condition:
        print(f"  [PASS] {name}")
        passed_count += 1
    else:
        print(f"  [FAIL] {name} - {details}")
        failed_count += 1


print("================================================================")
print("TASK 6: ERROR HANDLING / API ERROR SANITIZATION TEST SUITE")
print("================================================================")

# ==============================================================================
# SECTION 1: SUCCESSFUL API RESPONSES UNCHANGED (HTTP 200)
# ==============================================================================
print("\n=== Section 1: Successful API Responses Unchanged (HTTP 200) ===")

# Test 1.1: Login success response schema
mock_auth_res = MagicMock()
mock_auth_res.session.access_token = "valid_access_token_123"
mock_auth_res.session.refresh_token = "valid_refresh_token_456"
mock_auth_res.user.id = "user_mgr_001"

mock_staff_data = [{
    "id": "user_mgr_001",
    "email": "manager@vtab.com",
    "full_name": "Test Manager",
    "role": "Manager",
    "is_active": True,
}]

with patch.object(supabase.auth, "sign_in_with_password", return_value=mock_auth_res), \
     patch.object(supabase, "table") as mock_table:
    mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value.execute.return_value.data = mock_staff_data
    resp = client.post("/api/auth/login", json={"email": "manager@vtab.com", "password": "Password123!"})
    check("Successful login returns 200 OK", resp.status_code == 200)
    data = resp.json()
    check("Successful login schema has success=True", data.get("success") is True)
    check("Successful login schema has staff dict", isinstance(data.get("staff"), dict))
    check("Successful login schema has access_token", data.get("access_token") == "valid_access_token_123")
    check("Successful login schema has refresh_token", data.get("refresh_token") == "valid_refresh_token_456")
    check("Successful login schema has token_type bearer", data.get("token_type") == "bearer")

# Test 1.2: GET /api/candidates success response schema
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_all", return_value=[{"id": "c1", "name": "Alice"}]):
    resp = client.get("/api/candidates", headers={"Authorization": "Bearer token"})
    check("Successful GET /api/candidates returns 200 OK", resp.status_code == 200)
    data = resp.json()
    check("Successful GET /api/candidates has success=True", data.get("success") is True)
    check("Successful GET /api/candidates has items list", "items" in data)
    check("Successful GET /api/candidates has requested_by role", data.get("requested_by") == "Manager")
app.dependency_overrides.clear()

# Test 1.3: GET /api/hr/employees success response schema
app.dependency_overrides[require_hr] = lambda: {"id": "staff_hr", "role": "HR", "is_active": True}
with patch("app.select_all", return_value=[]):
    resp = client.get("/api/hr/employees", headers={"Authorization": "Bearer token"})
    check("Successful GET /api/hr/employees returns 200 OK", resp.status_code == 200)
    data = resp.json()
    check("Successful GET /api/hr/employees has success=True", data.get("success") is True)
    check("Successful GET /api/hr/employees has employees list", isinstance(data.get("employees"), list))
    check("Successful GET /api/hr/employees has requested_by role", data.get("requested_by") == "HR")
app.dependency_overrides.clear()

# Test 1.4: POST /api/recruitment/sync success response schema
with patch.dict("sys.modules", {
    "email_recruitment_pipeline": MagicMock(main=MagicMock()),
    "reply_pipeline": MagicMock(process_candidate_replies=MagicMock()),
}):
    resp = client.post("/api/recruitment/sync")
    check("Successful POST /api/recruitment/sync returns 200 OK", resp.status_code == 200)
    data = resp.json()
    check("Successful POST /api/recruitment/sync has success=True", data.get("success") is True)
    check("Successful POST /api/recruitment/sync has message", "message" in data)


# ==============================================================================
# SECTION 2: INTERNAL SERVER ERROR SANITIZATION (HTTP 500)
# ==============================================================================
print("\n=== Section 2: Internal Server Error Sanitization (HTTP 500) ===")

def verify_clean_500(resp, endpoint_name):
    check(f"{endpoint_name} returns status 500", resp.status_code == 500)
    body = resp.json()
    detail = body.get("detail", "")
    
    is_safe_detail = (
        detail == GENERIC_INTERNAL_ERROR or
        detail in {
            "Application decision could not be saved.",
            "AI document verification service failed.",
            "Unable to retrieve document from storage.",
            "AI assistant is temporarily unavailable. Please try again later.",
        }
    )
    check(f"{endpoint_name} returns clean safe detail message", is_safe_detail, f"Got: {detail}")
    
    detail_lower = detail.lower()
    check(f"{endpoint_name} does not leak traceback", "traceback" not in detail_lower)
    check(f"{endpoint_name} does not leak file paths (.py / Backend)", ".py" not in detail_lower and "backend" not in detail_lower)
    check(f"{endpoint_name} does not leak line numbers", "line " not in detail_lower)
    check(f"{endpoint_name} does not leak SQL syntax or errors", not any(s in detail_lower for s in ["select ", "insert ", "relation ", "psycopg2"]))
    check(f"{endpoint_name} does not leak errno", "errno" not in detail_lower)


# Test 2.1: Database crash on GET /api/candidates
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_all", side_effect=Exception('psycopg2.OperationalError: connection to server at "db.supabase.co" failed: [Errno 11001]')):
    resp = client.get("/api/candidates", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/candidates (DB crash)")
app.dependency_overrides.clear()

# Test 2.2: Python runtime crash (FileNotFoundError / OS path leak) on GET /api/candidates/{id}
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_one", side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'C:\\Users\\moham\\AI-Recruitment\\secrets.json'")):
    resp = client.get("/api/candidates/cand_123", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/candidates/{id} (Path/OS error)")
app.dependency_overrides.clear()

# Test 2.3: Syntax/Attribute crash in POST /api/manager/candidate-decision
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch.object(supabase, "table", side_effect=TypeError("object of type 'NoneType' has no len() at line 456 in Backend/app.py")):
    resp = client.post(
        "/api/manager/candidate-decision",
        json={"application_id": "app_1", "decision": "approve"},
        headers={"Authorization": "Bearer token"}
    )
    verify_clean_500(resp, "POST /api/manager/candidate-decision (Runtime crash)")
app.dependency_overrides.clear()

# Test 2.4: Internal crash in GET /api/interviews
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_all", side_effect=RuntimeError("SQL: SELECT * FROM interviews WHERE deleted_at IS NULL failed")):
    resp = client.get("/api/interviews", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/interviews (SQL crash)")
app.dependency_overrides.clear()

# Test 2.5: Internal crash in GET /api/interviews/{id}
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_one", side_effect=Exception("Database query timeout in interview_scheduler.py:89")):
    resp = client.get("/api/interviews/int_1", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/interviews/{id} (Timeout crash)")
app.dependency_overrides.clear()

# Test 2.6: Internal crash in POST /api/interview-feedback
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.save_interview_feedback", side_effect=Exception("supabase connection dropped during INSERT")):
    resp = client.post(
        "/api/interview-feedback",
        json={
            "application_id": "app_1",
            "reviewer_name": "Manager",
            "technical_skills": 5,
            "communication": 5,
            "problem_solving": 5,
            "overall_performance": 5,
            "recommendation": "strong_hire"
        },
        headers={"Authorization": "Bearer token"}
    )
    verify_clean_500(resp, "POST /api/interview-feedback (Internal crash)")
app.dependency_overrides.clear()

# Test 2.7: Internal crash in GET /api/manager/analytics
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_all", side_effect=Exception("Division by zero at line 1052 in analytics.py")):
    resp = client.get("/api/manager/analytics", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/manager/analytics (Analytics crash)")
app.dependency_overrides.clear()

# Test 2.8: Internal crash in GET /api/hr/offer-approvals
app.dependency_overrides[require_hr] = lambda: {"id": "staff_1", "role": "HR", "is_active": True}
with patch("app.select_all", side_effect=Exception("Failed to query applications table: column 'offer_status' does not exist")):
    resp = client.get("/api/hr/offer-approvals", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/hr/offer-approvals (Table query crash)")
app.dependency_overrides.clear()

# Test 2.9: Internal crash in GET /api/hr/employees
app.dependency_overrides[require_hr] = lambda: {"id": "staff_1", "role": "HR", "is_active": True}
with patch("app.select_all", side_effect=Exception("Failed to load employee records from Supabase")):
    resp = client.get("/api/hr/employees", headers={"Authorization": "Bearer token"})
    verify_clean_500(resp, "GET /api/hr/employees (Employee crash)")
app.dependency_overrides.clear()

# Test 2.10: Internal crash in POST /api/candidate-ai
with patch("app.gemini_client") as mock_gemini:
    mock_gemini.models.generate_content.side_effect = Exception("google.api_core.exceptions.GoogleAPIError: Resource has been exhausted (quota)")
    resp = client.post("/api/candidate-ai", json={"question": "What is the interview process?"})
    verify_clean_500(resp, "POST /api/candidate-ai (AI crash)")

# Test 2.11: Internal crash in POST /api/recruitment/sync
with patch.dict("sys.modules", {
    "email_recruitment_pipeline": MagicMock(main=MagicMock(side_effect=Exception("imaplib.IMAP4.error: LOGIN failed"))),
    "reply_pipeline": MagicMock(),
}):
    resp = client.post("/api/recruitment/sync")
    verify_clean_500(resp, "POST /api/recruitment/sync (IMAP crash)")


# ==============================================================================
# SECTION 3: INTENTIONAL BUSINESS ERRORS PRESERVED (HTTP 4xx)
# ==============================================================================
print("\n=== Section 3: Intentional Business Errors Preserved (HTTP 4xx) ===")

# Test 3.1: 400 Bad Request on invalid email format
resp = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
check("Forgot password invalid email returns 400 Bad Request", resp.status_code == 400)
check("Forgot password invalid email has informative detail", resp.json().get("detail") == "Invalid email address format.")

# Test 3.2: 400 Bad Request on missing reset token
resp = client.post("/api/auth/reset-password", json={"token": "", "password": "NewPassword123!"})
check("Reset password empty token returns 400 Bad Request", resp.status_code == 400)
check("Reset password empty token detail preserved", resp.json().get("detail") == "Password reset token is required.")

# Test 3.3: 400 Bad Request or 422 on short password
resp = client.post("/api/auth/reset-password", json={"token": "some_token", "password": "123"})
check("Reset password short password rejected (400 or 422)", resp.status_code in {400, 422})
check("Reset password short password detail preserved", "detail" in resp.json())

# Test 3.4: 400 Bad Request on invalid candidate decision
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
resp = client.post(
    "/api/manager/candidate-decision",
    json={"application_id": "app_1", "decision": "invalid_decision_type"},
    headers={"Authorization": "Bearer token"}
)
check("Invalid candidate decision returns 400 Bad Request", resp.status_code == 400)
check("Invalid candidate decision detail preserved", "Decision must be" in resp.json().get("detail", ""))
app.dependency_overrides.clear()

# Test 3.5: 400 Bad Request on invalid feedback rating (ValueError)
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.save_interview_feedback", side_effect=ValueError("Score must be between 1 and 5")):
    resp = client.post(
        "/api/interview-feedback",
        json={
            "application_id": "app_1",
            "reviewer_name": "Manager",
            "technical_skills": 5,
            "communication": 5,
            "problem_solving": 5,
            "overall_performance": 5,
            "recommendation": "strong_hire"
        },
        headers={"Authorization": "Bearer token"}
    )
    check("Interview feedback ValueError returns 400 Bad Request", resp.status_code == 400)
    check("Interview feedback ValueError detail preserved", "Score must be between 1 and 5" in resp.json().get("detail", ""))
app.dependency_overrides.clear()

# Test 3.6: 401 Unauthorized on missing Authorization header
resp = client.get("/api/candidates")
check("Missing Authorization header returns 401 Unauthorized", resp.status_code == 401)
check("Missing Authorization header detail preserved", resp.json().get("detail") == "Authorization header is required.")

# Test 3.7: 401 Unauthorized on invalid access token
with patch.object(supabase.auth, "get_user", side_effect=Exception("Invalid JWT signature")):
    resp = client.get("/api/candidates", headers={"Authorization": "Bearer invalid_token_xyz"})
    check("Invalid access token returns 401 Unauthorized", resp.status_code == 401)
    detail_msg = resp.json().get("detail", "")
    check("Invalid access token detail clean and informative", "Authentication failed" in detail_msg or "Invalid" in detail_msg)

# Test 3.8: 401 Unauthorized on failed login
with patch.object(supabase.auth, "sign_in_with_password", side_effect=Exception("Invalid login credentials")):
    resp = client.post("/api/auth/login", json={"email": "mgr@vtab.com", "password": "WrongPassword"})
    check("Failed login returns 401 Unauthorized", resp.status_code == 401)
    check("Failed login detail is clean and contains 'Login failed'", "Login failed" in resp.json().get("detail", ""))

# Test 3.9: 403 Forbidden on role requirement (non-manager accessing manager route)
app.dependency_overrides[get_current_staff] = lambda: {"id": "staff_hr", "role": "HR", "is_active": True}
resp = client.get("/api/manager/analytics", headers={"Authorization": "Bearer token"})
check("Non-manager accessing manager route returns 403 Forbidden", resp.status_code == 403)
check("Non-manager route detail preserved", "Manager/Admin access required." in resp.json().get("detail", ""))
app.dependency_overrides.clear()

# Test 3.10: 403 Forbidden on role requirement (non-HR accessing HR route)
app.dependency_overrides[get_current_staff] = lambda: {"id": "staff_mgr", "role": "Manager", "is_active": True}
resp = client.get("/api/hr/employees", headers={"Authorization": "Bearer token"})
check("Non-HR accessing HR route returns 403 Forbidden", resp.status_code == 403)
check("Non-HR route detail preserved", "HR/Admin access required." in resp.json().get("detail", ""))
app.dependency_overrides.clear()

# Test 3.11: 403 Forbidden on inactive staff member
mock_user_res = MagicMock()
mock_user_res.user.id = "user_inactive"
mock_user_res.user.email = "inactive@vtab.com"
mock_staff_query = MagicMock()
mock_staff_query.execute.return_value = MagicMock(data=[])
with patch.object(supabase.auth, "get_user", return_value=mock_user_res), \
     patch.object(supabase, "table") as mock_table:
    mock_table.return_value.select.return_value.or_.return_value.eq.return_value.limit.return_value = mock_staff_query
    resp = client.get("/api/candidates", headers={"Authorization": "Bearer token"})
    check("Inactive/missing staff returns 403 Forbidden", resp.status_code == 403)
    check("Inactive staff detail preserved", "Staff account not found or inactive." in resp.json().get("detail", ""))

# Test 3.12: 404 Not Found on missing candidate
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_one", return_value=None):
    resp = client.get("/api/candidates/non_existent_id", headers={"Authorization": "Bearer token"})
    check("Missing candidate returns 404 Not Found", resp.status_code == 404)
    check("Missing candidate detail preserved", resp.json().get("detail") == "Candidate not found.")
app.dependency_overrides.clear()

# Test 3.13: 404 Not Found on missing interview
app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
with patch("app.select_one", return_value=None):
    resp = client.get("/api/interviews/non_existent_interview", headers={"Authorization": "Bearer token"})
    check("Missing interview returns 404 Not Found", resp.status_code == 404)
    check("Missing interview detail preserved", resp.json().get("detail") == "Interview not found.")
app.dependency_overrides.clear()

# Test 3.14: 422 Unprocessable Entity on schema validation failure
resp = client.post("/api/auth/login", json={"only_one_field": "val"})
check("Pydantic validation failure returns 422 Unprocessable Entity", resp.status_code == 422)
check("Validation failure contains field errors", "detail" in resp.json())


# ==============================================================================
# SECTION 4: SECRETS AND SENSITIVE INFORMATION LEAKAGE PREVENTION
# ==============================================================================
print("\n=== Section 4: Secrets and Sensitive Information Leakage Prevention ===")

# Test 4.1: Simulated exception containing secrets does not leak to client
secret_exceptions = [
    Exception("Error connecting with service_role secret key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSJ9.secret"),
    Exception("Failed authenticate with password=SuperSecretPassword123! at localhost:5432"),
    Exception("API call failed using gemini_api_key=AIzaSyA_SecretKeyForGeminiApi123"),
    Exception("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token expired"),
]

app.dependency_overrides[require_manager] = lambda: {"id": "staff_1", "role": "Manager", "is_active": True}
for idx, sec_exc in enumerate(secret_exceptions, 1):
    with patch("app.select_all", side_effect=sec_exc):
        resp = client.get("/api/candidates", headers={"Authorization": "Bearer token"})
        check(f"Endpoint with secret exception #{idx} returns 500", resp.status_code == 500)
        detail = resp.json().get("detail", "")
        check(f"Endpoint with secret exception #{idx} does NOT leak secret", "eyJ" not in detail and "SuperSecret" not in detail and "AIza" not in detail)
        check(f"Endpoint with secret exception #{idx} returned generic message", detail == GENERIC_INTERNAL_ERROR)
app.dependency_overrides.clear()

# Test 4.2: log_internal_error redacts secrets when logging
log_capture = io.StringIO()
with patch("sys.stdout", log_capture):
    log_internal_error(
        Exception("Failed to connect using apiKey=AIzaSySecretApiKey123 and password=SecretPass!"),
        context="test_context"
    )
captured_log = log_capture.getvalue()
check("log_internal_error ran without raising", True)
check("log_internal_error masked sensitive keywords", "[REDACTED]" in captured_log or "apiKey" not in captured_log)


# ==============================================================================
# SECTION 5: SAFE_SELECT_ALL AND FALLBACKS
# ==============================================================================
print("\n=== Section 5: Safe Select Fallbacks ===")

with patch("app.select_all", side_effect=Exception('psycopg2.OperationalError: connection refused to "db.supabase.co"')):
    result = safe_select_all("candidates")
    check("safe_select_all returns available=False on error", result.get("available") is False)
    check("safe_select_all returns empty data list", result.get("data") == [])
    check("safe_select_all returns generic database error message", result.get("error") == "Database service unavailable.")
    check("safe_select_all does NOT leak psycopg2 or server hostname", "psycopg2" not in result.get("error", "") and "supabase.co" not in result.get("error", ""))


# ==============================================================================
# SECTION 6: GLOBAL FASTAPI EXCEPTION HANDLER VERIFICATION
# ==============================================================================
print("\n=== Section 6: Global Exception Handlers Verification ===")

# Test 6.1: StarletteHTTPException with 500 containing leak indicator gets sanitized
sanitized_test_detail = sanitize_error_detail("psycopg2.DatabaseError: column candidates.name does not exist at /Backend/app.py:123")
check("sanitize_error_detail scrubs SQL and path details", sanitized_test_detail == GENERIC_INTERNAL_ERROR)

# Test 6.2: StarletteHTTPException with clean business detail is preserved
clean_test_detail = sanitize_error_detail("Application decision could not be saved.")
check("sanitize_error_detail preserves clean domain error", clean_test_detail == "Application decision could not be saved.")

# Test 6.3: LEAK_INDICATORS covers all critical categories
critical_indicators = ["traceback", "syntaxerror", "psycopg2", "select ", "insert ", ".py", "line ", "password", "token", "secret", "errno"]
indicators_present = all(any(crit in ind for ind in LEAK_INDICATORS) for crit in critical_indicators)
check("LEAK_INDICATORS comprehensively covers stack, SQL, file, errno, and credentials", indicators_present)


# ==============================================================================
# FINAL RESULTS
# ==============================================================================
print("\n================================================================")
print(f"Task 6 Test Results: {passed_count}/{passed_count + failed_count} Passed ({failed_count} Failed)")
print("================================================================")

if failed_count > 0:
    sys.exit(1)
