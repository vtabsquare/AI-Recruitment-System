# Monitoring & Support Operational Guide

**VTAB Square AI Recruitment System**  
*Document Version: 1.0.0*  
*Last Updated: 2026-09-23*

---

## 1. Overview & Architecture

The AI Recruitment System employs a **lightweight, fail-safe, and privacy-preserving observability architecture** designed for production cloud hosting (Render) and local environments.

### Core Principle
> **Monitoring is an observer, not a participant in the business workflow.**
> The application will continue functioning normally even if logging fails, external monitoring is down, or Sentry is unreachable. Monitoring never blocks, slows down, or fails an ongoing business transaction.

```
                  ┌────────────────────────────────────────┐
                  │            Incoming Request            │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   ASGI Middleware Timing  │
                        │ (time.perf_counter start) │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   FastAPI Route Handler   │
                        └─────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
         [Successful Completion]               [Exception Caught]
                    │                                   │
                    │                     ┌─────────────┴─────────────┐
                    │                     ▼                           ▼
                    │            [Sanitized Response]     [log_internal_error]
                    │            (generic 500 / 4xx)      (diagnostic context)
                    │                     │                           │
                    │                     └─────────────┬─────────────┘
                    │                                   │
                    ▼                                   ▼
       ┌─────────────────────────────────────────────────────────────┐
       │             Structured Logging & Error Observer             │
       │                   (STRICTLY FAIL-SAFE)                      │
       ├─────────────────────────────────────────────────────────────┤
       │ 1. Compute duration_ms                                      │
       │ 2. Sanitize query params (redact tokens/passwords)          │
       │ 3. Stream key-value structured event to stdout (Render)     │
       │ 4. Optional Sentry capture (fail-open, PII-scrubbed)        │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │  HTTP Response to Client  │
                        └───────────────────────────┘
```

---

## 2. Health Check & Status Endpoints

The application exposes lightweight, unauthenticated health and discovery endpoints with zero database queries, zero external network calls, and instant response times:

| Endpoint | Method | Purpose | Auth Required | Expected Status | Response Payload |
|---|---|---|---|---|---|
| `/health` | `GET` | Lightweight health check probe for uptime monitors & load balancers | None | `200 OK` | `{"status": "healthy"}` |
| `/` | `GET` | Root service discovery endpoint | None | `200 OK` | `{"status": "running", "service": "VTAB Square AI Recruitment API", "version": "1.2.0"}` |
| `/docs` | `GET` | Interactive OpenAPI / Swagger documentation (used by Render `healthCheckPath`) | None | `200 OK` | HTML Swagger UI |

### Health Check Operational Rules
- **Probe Frequency**: In production, configure health checks to poll `/health` or `/docs` every 30–60 seconds.
- **Fail-Open Status**: Health checks return `200 OK` as long as the FastAPI process is running and accepting event loop tasks.
- **Zero Side Effects**: Health checks never write records, mutate session state, or query the database.

---

## 3. Structured Backend Logging Specification

The application emits structured logs to `sys.stdout`. Each event is output as a single line containing standard key-value pairs designed for direct consumption by cloud log aggregators (e.g., Render Log Stream, Datadog, CloudWatch).

### Standard Log Line Format
```text
timestamp=<ISO8601> level=<LEVEL> event=<EVENT> method=<METHOD> route=<ROUTE> status=<STATUS> duration_ms=<MS> [client_ip=<IP>]
```

### Log Levels
- **`INFO`**: Normal application lifecycle events (startup, graceful shutdown), health checks, and successful API requests (`2xx`, `3xx`).
- **`WARNING`**: Client-side errors (`4xx`, e.g. `401 Unauthorized`, `404 Not Found`, `422 Validation Error`), retry attempts, or non-fatal configuration warnings.
- **`ERROR`**: Server-side failures (`5xx`), unexpected exceptions, database connection drops, or external service outages.

### Standard Events & Examples

#### A. Request Completed (Success)
```text
timestamp=2026-09-23T10:20:30Z level=INFO event=request_completed method=GET route=/health status=200 duration_ms=1.45 client_ip=198.51.100.2
```

#### B. Request Completed (Client Error)
```text
timestamp=2026-09-23T10:21:05Z level=WARNING event=request_completed method=POST route=/api/login status=401 duration_ms=38.2 client_ip=198.51.100.2
```

#### C. Request Completed with Sanitized Query Parameters
```text
timestamp=2026-09-23T10:21:40Z level=INFO event=request_completed method=GET route="/api/candidates?token=[REDACTED]&page=1" status=200 duration_ms=14.1 client_ip=198.51.100.2
```

#### D. Application Error (Internal Server Failure)
```text
timestamp=2026-09-23T10:22:15Z level=ERROR event=application_error error_type=OperationalError context="GET /api/candidates" message="database connection dropped"
```

#### E. External Service Failure
```text
timestamp=2026-09-23T10:23:00Z level=ERROR event=external_service_failure service=Gemini status=503 error_type=ResourceExhausted message="The model is currently overloaded. Please retry later."
```

#### F. Application Lifecycle
```text
timestamp=2026-09-23T10:00:00Z level=INFO event=application_started service="VTAB Square AI Recruitment API" version=1.2.0
```

---

## 4. Privacy & Excluded Sensitive Data

To ensure complete compliance with privacy standards and credential hygiene, the logging layer enforces strict redaction boundaries:

### Intentionally Excluded & Redacted Information
1. **Passwords & Credentials**: Plaintext passwords, bcrypt hashes, and reset tokens are **never** logged.
2. **Tokens & JWTs**: Authorization headers (Bearer tokens), access tokens, refresh tokens, and cookies are completely redacted or stripped.
3. **API Keys**: Gemini API keys, Brevo API keys, Supabase Service Role keys, and OAuth client secrets are never printed.
4. **Candidate Documents & Resumes**: Extracted resume text, PDF file payloads, candidate personal letters, and document contents are strictly excluded from logs.
5. **Request & Response Bodies**: Full POST/PUT JSON request bodies are never dumped into request logs to prevent accidental exposure of candidate contact information or form inputs.
6. **Query String Secrets**: Any URL containing query parameters matching `token`, `password`, `key`, `secret`, `auth`, or `bearer` is automatically replaced with `[REDACTED]`.

---

## 5. Fail-Safe / Fail-Open Architecture

Monitoring is strictly decoupled from the core business workflow:

1. **Non-Blocking Execution**: Log formatting and emission are executed synchronously via lightweight Python string operations with negligible CPU overhead (< 0.5 ms per request).
2. **Exception Isolation**: All monitoring code paths (`structured_logging_middleware`, `log_request_summary`, `log_structured`, `capture_exception`) are wrapped in explicit `try...except Exception:` blocks.
3. **No Cascading Failures**:
   - If stdout logging throws an I/O error, the error is caught and discarded; the client still receives the complete HTTP response.
   - If Sentry is unreachable or times out, the call fails silently in the background; application requests are not delayed.
   - If the database is completely offline, error logs are written to stdout without attempting a database write.
4. **Audit vs. Monitoring Separation**:
   - **Audit Logs** (`audit_logs` table): Record business transactions (e.g., candidate status updates, interview schedules, logins).
   - **Monitoring Logs** (`sys.stdout`): Record technical runtime metrics (response times, HTTP status codes, error traces).

---

## 6. Error Investigation Runbook

When an incident occurs or an alert fires, follow this triage procedure:

### Step 1: Check Health & Process Status
```bash
# Check if backend process is alive
curl -I https://ai-recruitment-backend.onrender.com/health
```
- **Expected**: `HTTP/1.1 200 OK`
- **If timeout or connection refused**: Process has crashed or is deploying. Proceed to Step 2 (Render Logs).

### Step 2: Filter Render Platform Logs
1. Navigate to the **Render Dashboard** -> **Services** -> **ai-recruitment-backend** -> **Logs**.
2. Search for `level=ERROR`.
3. Locate recent `event=application_error` or `event=external_service_failure` entries.
4. Note the `error_type`, `context`, and `message` values.

### Step 3: Specific Error Triage Runbooks

#### Incident A: HTTP 500 on Candidate Listing or Application Updates
- **Symptom**: `route=/api/candidates status=500` with `error_type=PostgrestError` or `OperationalError`.
- **Diagnosis**: Supabase PostgreSQL database connectivity issue or connection pool exhaustion.
- **Action**:
  1. Check Supabase project status in the Supabase Dashboard.
  2. Verify database connection string and API keys in Render environment variables.
  3. Verify that database connection pooling limits have not been exceeded.

#### Incident B: External Service Failure — Gemini AI (Resume Evaluation)
- **Symptom**: `event=external_service_failure service=Gemini status=429` or `status=503`.
- **Diagnosis**: Google Gemini API quota exceeded or model temporarily overloaded.
- **Action**:
  1. The application's Task 1 retry mechanism automatically retries transient errors with exponential backoff.
  2. If persistent, check Google Cloud Console / AI Studio for quota limits or billing status.
  3. Verify that `GEMINI_API_KEY` in Render environment variables is valid.

#### Incident C: External Service Failure — Brevo (Email Delivery)
- **Symptom**: `event=external_service_failure service=Brevo status=401` or `status=402`.
- **Diagnosis**: Brevo API key expired or monthly transactional email credit exhausted.
- **Action**:
  1. Check Brevo Dashboard for credit balance.
  2. Confirm `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` in Render environment variables match the verified sender.

#### Incident D: Google OAuth / Calendar Sync Failure
- **Symptom**: `event=external_service_failure service=Google error_type=RefreshError`.
- **Diagnosis**: Google refresh token revoked or expired.
- **Action**:
  1. Re-authenticate locally to generate a fresh `token.json`.
  2. Update the base64-encoded `GOOGLE_TOKEN_JSON` variable in Render dashboard.

---

## 7. Render Deployment Monitoring

The application is deployed on Render as defined in `render.yaml`.

### Monitoring Features in Render
1. **Live Log Streaming**:
   - Streamed directly from stdout.
   - Preserves timestamps and structured event attributes.
   - Retained in Render according to plan retention limits.
2. **Metrics Dashboard**:
   - Real-time CPU Utilization (keep average below 70%).
   - Memory Usage (Render Free/Starter tier has 512 MB limit; inspect for leaks if usage trends steadily upward).
   - HTTP Request Volume and Latency percentiles (p50, p95, p99).
3. **Deployment Health Check**:
   - Render automatically queries `healthCheckPath: /docs` after build completion.
   - If the health check does not respond within the timeout window, Render cancels the deployment and retains the prior active version (zero-downtime deployment).

### Setting Up Render Alerts
1. In Render Dashboard, go to **Account Settings** -> **Notifications**.
2. Configure **Slack** or **Email** notifications for:
   - Deploy Failed
   - Service Crashed / Unhealthy

---

## 8. Optional Sentry Error Monitoring

Sentry integration is fully implemented as an **optional, fail-open module**.

### Configuration
To activate Sentry, provide the DSN via environment variable:
```bash
SENTRY_DSN="https://your_public_key@o0.ingest.sentry.io/your_project_id"
ENVIRONMENT="production"
```

### Safety & Verification Guarantees
- **No Hardcoded Secrets**: The DSN is read exclusively from `os.getenv("SENTRY_DSN")`.
- **Zero Hard Dependency**: If `SENTRY_DSN` is omitted, the application runs purely with stdout structured logging.
- **Missing SDK Tolerance**: If `sentry-sdk` is not installed, the application catches `ImportError` safely and logs an informational notice without halting startup.
- **PII Scrubbing (`before_send`)**: Sentry events are intercepted before dispatch:
  - `Authorization`, `Cookie`, and `Proxy-Authorization` headers are replaced with `[REDACTED]`.
  - Sensitive query parameters are scrubbed.
  - Candidate resume bodies and document buffers are never attached to Sentry event scopes.

---

## 9. Operational Status Summary

| Capability | Status | Notes |
|---|---|---|
| HTTP Request Structured Logging | **Implemented and verified** | Formatted key-value stdout logs on every request with timing & status |
| Query Parameter Redaction | **Implemented and verified** | Redacts tokens, passwords, and secrets in URL paths |
| Health Check Endpoint (`/health`) | **Implemented and verified** | Unauthenticated, instant 200 OK probe |
| Root Endpoint (`/`) | **Implemented and verified** | Returns API running status and version 1.2.0 |
| Render Health Check (`/docs`) | **Implemented and verified** | Preserved from existing `render.yaml` configuration |
| Error Sanitization & Safe Logging | **Implemented and verified** | 500 errors sanitized to client; diagnostic context logged internally |
| Fail-Open Middleware | **Implemented and verified** | Logging/monitoring failures never fail API requests |
| External Service Failure Helper | **Implemented and verified** | Standardized logging for Supabase, Brevo, Gemini, Google failures |
| Optional Sentry Integration | **Implemented and verified** | Fully fail-open via `SENTRY_DSN`; runs safely without Sentry installed |
| Third-party APM (Datadog/NewRelic) | **Recommended but not configured** | Optional future enhancement if advanced APM tracing is needed |
