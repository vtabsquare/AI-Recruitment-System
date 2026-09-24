import sys
from pathlib import Path
import os

BACKEND_DIR = r"c:\Users\moham\OneDrive\Documents\AI-Recruitment-System-main\AI-Recruitment-System-main\Backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set dummy env vars for unconfigured services to avoid crash on import
os.environ.setdefault("GEMINI_API_KEY", "dummy_key_for_testing")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy_supabase_key")

import unittest
from unittest.mock import MagicMock, patch
import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ConnectionError
from googleapiclient.errors import HttpError

class MockGoogleResp:
    def __init__(self, status):
        self.status = status
        self.reason = "Mock Google API Status"

class TestAPIRetriesAndIdempotency(unittest.TestCase):

    # ============================================================
    # BREVO EMAIL RETRY & DUPLICATE PREVENTION TESTS
    # ============================================================

    def test_email_service_transient_retry_and_success(self):
        """Verify send_email retries on Brevo 503/429 and succeeds when Brevo recovers."""
        import email_service

        with patch.object(email_service, "BREVO_API_KEY", "test_key"), \
             patch.object(email_service, "BREVO_SENDER_EMAIL", "test@vtab.com"):

            call_count = 0
            def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_resp = MagicMock()
                if call_count < 3:
                    mock_resp.ok = False
                    mock_resp.status_code = 503
                    mock_resp.text = "Service Unavailable"
                    mock_resp.json.side_effect = ValueError()
                    return mock_resp
                else:
                    mock_resp.ok = True
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {"messageId": "<test@vtab.com>"}
                    return mock_resp

            with patch("requests.post", side_effect=mock_post):
                result = email_service.send_email("candidate@example.com", "Test", "Subject", "<p>Hello</p>")
                self.assertEqual(result, {"messageId": "<test@vtab.com>"})
                self.assertEqual(call_count, 3)

    def test_email_service_read_timeout_no_retry_duplicate_prevention(self):
        """CRITICAL: Verify send_email DOES NOT retry on ReadTimeout, preventing duplicate emails."""
        import email_service

        with patch.object(email_service, "BREVO_API_KEY", "test_key"), \
             patch.object(email_service, "BREVO_SENDER_EMAIL", "test@vtab.com"):

            call_count = 0
            def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise ReadTimeout("HTTPSConnectionPool: Read timed out")

            with patch("requests.post", side_effect=mock_post):
                with self.assertRaises(ReadTimeout):
                    email_service.send_email("candidate@example.com", "Test", "Subject", "<p>Hello</p>")
                # Must be called EXACTLY ONCE: no retry on ReadTimeout!
                self.assertEqual(call_count, 1)

    def test_email_service_connect_timeout_safe_retry(self):
        """Verify send_email SAFELY retries on ConnectTimeout (handshake never completed) and succeeds."""
        import email_service

        with patch.object(email_service, "BREVO_API_KEY", "test_key"), \
             patch.object(email_service, "BREVO_SENDER_EMAIL", "test@vtab.com"):

            call_count = 0
            def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectTimeout("Connection timed out during TCP handshake")
                mock_resp = MagicMock()
                mock_resp.ok = True
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"messageId": "<recovered@vtab.com>"}
                return mock_resp

            with patch("requests.post", side_effect=mock_post):
                result = email_service.send_email("candidate@example.com", "Test", "Subject", "<p>Hello</p>")
                self.assertEqual(result, {"messageId": "<recovered@vtab.com>"})
                self.assertEqual(call_count, 2)

    def test_email_service_permanent_failure_no_retry(self):
        """Verify send_email does NOT retry on 401 Unauthorized or invalid email format."""
        import email_service

        with patch.object(email_service, "BREVO_API_KEY", "test_key"), \
             patch.object(email_service, "BREVO_SENDER_EMAIL", "test@vtab.com"):

            # 1. Format validation error
            with self.assertRaises(ValueError):
                email_service.send_email("not-an-email", "Test", "Subject", "<p>Hi</p>")

            # 2. HTTP 401 Unauthorized
            call_count = 0
            def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_resp = MagicMock()
                mock_resp.ok = False
                mock_resp.status_code = 401
                mock_resp.text = "Key unauthorized"
                mock_resp.json.side_effect = ValueError()
                return mock_resp

            with patch("requests.post", side_effect=mock_post):
                with self.assertRaises(RuntimeError) as ctx:
                    email_service.send_email("candidate@example.com", "Test", "Subject", "<p>Hello</p>")
                self.assertIn("401", str(ctx.exception))
                self.assertEqual(call_count, 1)

    # ============================================================
    # GOOGLE CALENDAR RETRY & DUPLICATE EVENT PREVENTION TESTS
    # ============================================================

    def test_calendar_insert_timeout_no_retry_duplicate_prevention(self):
        """CRITICAL: Verify calendar insert NEVER retries on TimeoutError to prevent duplicate events."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Socket timed out waiting for Google Calendar response")

        mock_req.execute.side_effect = mock_execute
        with self.assertRaises(TimeoutError):
            interview_scheduler._execute_google_api_insert(mock_req)
        # Must be called EXACTLY ONCE: no retry on TimeoutError during insert!
        self.assertEqual(call_count, 1)

    def test_calendar_insert_connection_error_no_retry(self):
        """Verify calendar insert NEVER retries on ConnectionError/OSError during insert."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            raise ConnectionResetError("Connection reset by peer")

        mock_req.execute.side_effect = mock_execute
        with self.assertRaises(ConnectionResetError):
            interview_scheduler._execute_google_api_insert(mock_req)
        self.assertEqual(call_count, 1)

    def test_calendar_insert_503_no_retry_duplicate_prevention(self):
        """Verify calendar insert does NOT retry on ambiguous 500/503 where event creation is unknown."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            resp = MockGoogleResp(503)
            raise HttpError(resp, b"Backend error")

        mock_req.execute.side_effect = mock_execute
        with self.assertRaises(HttpError):
            interview_scheduler._execute_google_api_insert(mock_req)
        self.assertEqual(call_count, 1)

    def test_calendar_insert_429_safe_retry(self):
        """Verify calendar insert SAFELY retries on 429 Rate Limit (confirmed rejection) and succeeds."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                resp = MockGoogleResp(429)
                raise HttpError(resp, b"User Rate Limit Exceeded")
            return {"id": "event_new_123", "status": "confirmed"}

        mock_req.execute.side_effect = mock_execute
        res = interview_scheduler._execute_google_api_insert(mock_req)
        self.assertEqual(res["id"], "event_new_123")
        self.assertEqual(call_count, 3)

    def test_calendar_read_idempotent_retry_and_success(self):
        """Verify calendar read query (freebusy) safely retries on both 503 and TimeoutError."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Temporary timeout on read")
            if call_count == 2:
                resp = MockGoogleResp(503)
                raise HttpError(resp, b"Service Unavailable")
            return {"calendars": {"primary": {"busy": []}}}

        mock_req.execute.side_effect = mock_execute
        res = interview_scheduler._execute_google_api_read(mock_req)
        self.assertIn("calendars", res)
        self.assertEqual(call_count, 3)

    def test_calendar_read_permanent_error_no_retry(self):
        """Verify calendar read does NOT retry on 401 or 404."""
        import interview_scheduler

        mock_req = MagicMock()
        call_count = 0
        def mock_execute():
            nonlocal call_count
            call_count += 1
            resp = MockGoogleResp(404)
            raise HttpError(resp, b"Not Found")

        mock_req.execute.side_effect = mock_execute
        with self.assertRaises(HttpError):
            interview_scheduler._execute_google_api_read(mock_req)
        self.assertEqual(call_count, 1)

    # ============================================================
    # GEMINI AI ANALYZER RETRY TESTS
    # ============================================================

    def test_ai_analyzer_transient_retry(self):
        """Verify Gemini generate_content retries on 429 or 503 and succeeds."""
        import ai_analyzer

        mock_client = MagicMock()
        call_count = 0
        class MockAIError(Exception):
            def __init__(self, code, msg):
                self.code = code
                self.message = msg

        def mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise MockAIError(429, "Rate limit exceeded")
            mock_res = MagicMock()
            mock_res.text = "Analysis completed"
            return mock_res

        mock_client.models.generate_content.side_effect = mock_generate
        res = ai_analyzer._generate_content_with_retry(mock_client, model="gemini-2.5-flash", contents="prompt")
        self.assertEqual(res.text, "Analysis completed")
        self.assertEqual(call_count, 3)

    def test_ai_analyzer_permanent_error_no_retry(self):
        """Verify Gemini generate_content does NOT retry on ValueError or invalid request."""
        import ai_analyzer

        mock_client = MagicMock()
        call_count = 0
        def mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid prompt parameters")

        mock_client.models.generate_content.side_effect = mock_generate
        with self.assertRaises(ValueError):
            ai_analyzer._generate_content_with_retry(mock_client, model="gemini-2.5-flash", contents="prompt")
        self.assertEqual(call_count, 1)

    # ============================================================
    # FASTAPI APP IMPORT INTEGRITY TEST
    # ============================================================

    def test_app_import_clean(self):
        """Verify app module imports without any missing imports or syntax regressions."""
        import app
        self.assertTrue(hasattr(app, "app"))

if __name__ == "__main__":
    unittest.main()
