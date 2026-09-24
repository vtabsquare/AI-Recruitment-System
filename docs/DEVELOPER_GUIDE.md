# VTAB Square — Developer Guide

Comprehensive technical reference for the AI Recruitment System.  
Start here after reading [README.md](../README.md).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Local Development Setup](#4-local-development-setup)
5. [Environment Variables](#5-environment-variables)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [API Reference](#7-api-reference)
8. [Database](#8-database)
9. [Candidate & Recruitment Workflow](#9-candidate--recruitment-workflow)
10. [External Integrations](#10-external-integrations)
11. [Monitoring & Support](#11-monitoring--support)
12. [Backup & Recovery](#12-backup--recovery)
13. [Deployment](#13-deployment)
14. [Testing](#14-testing)
15. [Security Considerations](#15-security-considerations)
16. [Troubleshooting](#16-troubleshooting)
17. [Developer Workflow](#17-developer-workflow)

---

## 1. Project Overview

**VTAB Square AI Recruitment System** automates the full candidate recruitment lifecycle:

- **Candidates** submit applications and documents through a public-facing AI assistant.
- **Managers** review AI-evaluated applications, conduct interviews, and record feedback.
- **HR staff** verify documents, approve offer letters, and onboard successful candidates.
- **Automation** handles email notifications, interview scheduling (Google Calendar), Gmail monitoring, and AI-driven resume/document evaluation (Google Gemini).

### Main Components

| Component | Role |
|-----------|------|
| React SPA | Single-page frontend for candidates, managers, and HR |
| FastAPI backend | All business logic, authentication, and API endpoints |
| Supabase | PostgreSQL database + object storage + Supabase Auth |
| Google Gemini | AI resume analysis and candidate chat |
| Brevo | Transactional email (invitations, decisions, resets) |
| Google APIs | Gmail monitoring and Google Calendar interview scheduling |

---

## 2. Architecture

### 2.1 High-Level

```
Browser (React + Vite SPA)
        │
        │  HTTP/HTTPS — CORS-controlled
        ▼
FastAPI Backend  ─────────────────────────────────────────────────
  │                                                               │
  ├── CORSMiddleware (origin allow-list from ALLOWED_ORIGINS)     │
  ├── HTTP Logging Middleware (structured, fail-safe)             │
  ├── Global Exception Handlers (sanitised 4xx/5xx responses)     │
  │                                                               │
  ├── /api/auth/*         Supabase Auth (JWT bearer tokens)       │
  ├── /api/candidates/*   Candidate data (Supabase PostgreSQL)    │
  ├── /api/manager/*      Manager decisions & analytics           │
  ├── /api/hr/*           HR offer approvals, docs, employees     │
  ├── /api/document-*     Document upload & verification          │
  ├── /api/interview-*    Interview management & feedback         │
  ├── /api/candidate-ai   Gemini AI chat                          │
  └── /api/recruitment/*  Background recruitment pipeline sync    │
        │                                                         │
        ├── Supabase DB (PostgreSQL) ◄────────── All data        │
        ├── Supabase Storage ◄──────────── candidate-documents    │
        ├── Google Gemini API ◄──────────── AI evaluation        │
        ├── Brevo API ◄─────────────────── Email notifications   │
        └── Google Calendar/Gmail API ◄─── Scheduling & inbox   │
─────────────────────────────────────────────────────────────────
```

### 2.2 Frontend Architecture

- **Framework:** React 19 with Vite 8 (no router — screen switching via `screen` state machine)
- **Single file:** All components live in `Frontend/src/App.jsx` (4 235 lines)
- **Styling:** `Frontend/src/App.css` (minified, 23 lines) + `Frontend/src/index.css` (1 line)
- **API communication:** `apiRequest()` helper function at the top of `App.jsx` — wraps `fetch()`, adds `Authorization: Bearer <token>` header, reads `VITE_API_BASE_URL` from environment
- **State:** React `useState` / `useEffect` only — no Redux or React Router
- **Build output:** `Frontend/dist/` (served as a Render static site)

Key screens / components in `App.jsx`:

| Component | Lines | Role |
|-----------|-------|------|
| `App` | 49–231 | Root — state machine, routing, header |
| `Home` | 245–295 | Public landing page |
| `Menu` | 297–355 | Navigation drawer (slide-in) |
| `Login` | 357–470 | Staff login form |
| `ForgotPassword` | 472–578 | Password reset request |
| `ResetPassword` | 580–700 | New password form |
| `CandidateAI` | 702–853 | Candidate-facing AI chat assistant |
| `DocumentSubmission` | 855–1785 | Candidate document upload portal |
| `PortalLayout` | 1790–1900 | Shared sidebar + header shell for portals |
| `ManagerPortal` / `ManagerQueue` | 1900–2810 | Manager review of candidates |
| `Feedback` | 2815–3110 | Interview feedback form |
| `Analytics` | 3115–3220 | Manager analytics view |
| `HRPortal` / `OfferApprovals` | 3222–4075 | HR offer review and document verification |
| `EmployeeRecords` | 4077–4170 | HR employee list |
| `AuditLogs` | 4174–4255 | HR audit trail view |

### 2.3 Backend Architecture

- **Framework:** FastAPI (Python)
- **Entry point:** `Backend/app.py` (2 927 lines)
- **ASGI server:** Uvicorn (production) / Uvicorn `--reload` (development)
- **Configuration:** `Backend/config.py` — single source of truth for all environment variables
- **Database client:** `Backend/supabase_db.py` — initialises and exports the Supabase Python client

Key backend modules:

| Module | Role |
|--------|------|
| `app.py` | FastAPI app, all routes, middleware, auth helpers |
| `config.py` | Centralised env var loading via `python-dotenv` |
| `supabase_db.py` | Supabase client singleton |
| `audit_service.py` | Non-blocking `log_audit_event()` — writes to `audit_logs` table |
| `logging_config.py` | Structured logging helpers (`log_structured`, `log_request_summary`, `capture_exception`, `init_monitoring`) |
| `ai_analyzer.py` | Google Gemini client + resume analysis logic |
| `email_service.py` | Brevo-backed `send_email()` helper |
| `email_sender.py` | Lower-level Brevo REST caller |
| `interview_scheduler.py` | Google Calendar interview creation |
| `gmail_reader.py` | Gmail OAuth inbox reading |
| `google_auth.py` | Google OAuth2 credential management |
| `recruitment_service.py` | Core recruitment pipeline orchestration |
| `reply_pipeline.py` | Email reply parsing and pipeline |
| `interview_feedback_service.py` | Interview feedback persistence |
| `interview_ai_evaluator.py` | AI evaluation of interview feedback |
| `interview_decision_email_service.py` | Final decision email dispatch |
| `resume_service.py` | Resume extraction helpers |
| `evaluation_service.py` | AI evaluation service |

---

## 3. Repository Structure

```
AI-Recruitment-System/
├── Backend/
│   ├── app.py                     # FastAPI application — main entry point
│   ├── config.py                  # All environment variables (single source)
│   ├── supabase_db.py             # Supabase client initialisation
│   ├── audit_service.py           # Non-blocking audit logging
│   ├── logging_config.py          # Structured logging + optional Sentry
│   ├── ai_analyzer.py             # Gemini AI resume analysis
│   ├── email_service.py           # Brevo email sending
│   ├── email_sender.py            # Brevo REST API caller
│   ├── gmail_reader.py            # Gmail inbox reading (Google API)
│   ├── google_auth.py             # Google OAuth2 credential management
│   ├── interview_scheduler.py     # Google Calendar scheduling
│   ├── interview_feedback_service.py   # Interview feedback persistence
│   ├── interview_ai_evaluator.py  # AI interview feedback evaluation
│   ├── interview_decision_email_service.py # Final decision emails
│   ├── recruitment_service.py     # Recruitment pipeline
│   ├── reply_pipeline.py          # Email reply pipeline
│   ├── resume_service.py          # Resume extraction helpers
│   ├── evaluation_service.py      # AI evaluation service
│   ├── application_service.py     # Application helpers
│   ├── company_rules.py           # Company-specific rules
│   ├── id_generator.py            # ID generation utility
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Environment variable template
├── Frontend/
│   ├── src/
│   │   ├── App.jsx                # Entire React SPA (single file, ~4 235 lines)
│   │   ├── App.css                # All component styles
│   │   └── index.css              # Root body/html reset
│   ├── index.html                 # SPA entry — lang="en", skip link
│   ├── package.json               # Node dependencies
│   ├── vite.config.js             # Vite configuration
│   └── dist/                      # Production build output (git-ignored)
├── docs/
│   ├── DEVELOPER_GUIDE.md         # This file
│   ├── BACKUP_AND_RECOVERY.md     # Backup and disaster recovery
│   └── MONITORING_AND_SUPPORT.md  # Monitoring and support guide
├── scripts/
│   └── backup_db.py               # Standalone database backup CLI
├── scratch/
│   ├── test_task1_retries.py      # API retry regression tests
│   ├── test_task2_password_reset.py
│   ├── test_task3_logout.py
│   ├── test_task4_config.py
│   ├── test_task5_audit.py
│   ├── test_task6_error_handling.py
│   ├── test_task7_backup_recovery.py
│   ├── test_task9_monitoring.py
│   └── test_task10_accessibility.py
├── database/                      # Empty — schema managed in Supabase
├── render.yaml                    # Render deployment blueprint
└── README.md                      # Project overview and quick start
```

> **Note:** `Backend/app.py.backup_*` files are historic backup snapshots. `Backend/app_backup.py` is a smaller early backup. These are not runtime files.

---

## 4. Local Development Setup

### 4.1 Prerequisites

| Tool | Notes |
|------|-------|
| Python 3.12+ | Tested with Python 3.12.3 |
| pip | Included with Python |
| Node.js 18+ | Required for Vite 8 / React 19 |
| npm | Included with Node.js |
| Supabase project | Database and auth credentials required |

### 4.2 Backend Setup

```bash
cd Backend

# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your actual credentials

# Start the development server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The backend is accessible at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

### 4.3 Frontend Setup

```bash
cd Frontend

# Install dependencies
npm install

# Configure environment (if your backend is not at the default)
# Create Frontend/.env.local with:
# VITE_API_BASE_URL=http://localhost:8000

# Start the development server
npm run dev
```

The frontend is accessible at `http://localhost:5173`.

### 4.4 Environment Configuration

Copy `Backend/.env.example` to `Backend/.env` and fill in each value.  
**Never commit `.env` to version control.** (`.gitignore` already excludes it.)

See [Section 5 — Environment Variables](#5-environment-variables) for the full variable reference.

---

## 5. Environment Variables

All environment variables are loaded through `Backend/config.py` using `python-dotenv`.

### Backend Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key for AI evaluation |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model name |
| `BREVO_API_KEY` | Yes | — | Brevo transactional email API key |
| `BREVO_SENDER_EMAIL` | Yes | — | From-address for all outgoing emails |
| `BREVO_SENDER_NAME` | No | `VTAB Square Recruitment` | From-name |
| `BREVO_API_URL` | No | Brevo v3 SMTP URL | Override Brevo API endpoint |
| `SUPABASE_URL` | Yes | — | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes (preferred) | — | Service-role key (full DB access) |
| `SUPABASE_KEY` | Fallback | — | Anon/service key fallback |
| `SUPABASE_ANON_KEY` | Fallback | — | Anon key fallback |
| `COMPANY_EMAIL` | No | `vitabsquare@gmail.com` | Default recruiter/sender inbox |
| `INTERVIEW_MANAGER_EMAIL` | No | Same as `COMPANY_EMAIL` | Interview manager email |
| `FRONTEND_URL` | No | `http://localhost:5173` | Used for password reset redirect URLs |
| `ALLOWED_ORIGINS` | Yes (prod) | localhost origins | Comma-separated CORS allow-list |
| `GOOGLE_CREDENTIALS_FILE` | Optional | `credentials.json` | Path to Google OAuth credentials |
| `GOOGLE_TOKEN_FILE` | Optional | `token.json` | Path to Google OAuth token |
| `GOOGLE_TOKEN_JSON` | Optional | — | Base64-encoded token for cloud deployments |
| `SENTRY_DSN` | Optional | — | Sentry error monitoring DSN |
| `ENVIRONMENT` | Optional | `production` on Render | Environment label (`development`/`production`) |

> **Key resolution order for `SUPABASE_KEY`:**  
> `SUPABASE_SERVICE_ROLE_KEY` → `SUPABASE_KEY` → `SUPABASE_ANON_KEY` (first non-empty wins)

### Frontend Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_BASE_URL` | Yes (prod) | Empty string (same origin) | Backend API base URL |

> In development, if `VITE_API_BASE_URL` is not set, `apiRequest()` prefixes calls with an empty string (same-origin). For production, set this to your Render backend URL.

---

## 6. Authentication & Authorization

### 6.1 Authentication Flow

```
1. Staff member POSTs credentials to POST /api/auth/login
2. Backend calls Supabase Auth sign_in_with_password()
3. Supabase validates credentials and returns session + user
4. Backend checks staff_users table: user must be active + role in {manager, hr, admin}
5. Backend returns {access_token, refresh_token, staff: {...}}
6. Frontend stores access_token in React state (not localStorage)
7. Every subsequent API request includes: Authorization: Bearer <access_token>
```

### 6.2 Token Verification

There is **no custom JWT verification middleware**. Protected endpoints call `supabase.auth.get_user(token)` directly, which validates the token against Supabase Auth on each request.

Tokens are **not stored in localStorage** — they live in React component state and are cleared on page reload or explicit logout.

### 6.3 Server-Side Session Revocation

When a user logs out (`POST /api/auth/logout`):

1. The backend calls `supabase.auth.sign_out()` to invalidate the Supabase session.
2. The token hash (SHA-256) is added to an **in-memory revocation cache** (`_revoked_token_hashes`) with a 2-hour TTL.
3. The cache is checked in `is_token_revoked()` before processing requests on sensitive endpoints.

> **Note:** The in-memory cache does not persist across process restarts. On Render free tier, the process may restart; in that case, only Supabase Auth invalidation (step 1) persists.

### 6.4 Password Reset Flow

```
1. Staff clicks "Forgot password" and submits their email
2. POST /api/auth/forgot-password — backend attempts Supabase reset email
3. If Supabase reset email fails, backend generates an admin link via Supabase Admin API
   and sends it through Brevo as a fallback
4. User clicks the link in email → lands on /#type=recovery (frontend hash route)
5. Frontend detects the recovery token in the URL hash and displays the ResetPassword form
6. POST /api/auth/reset-password — backend validates token and updates password via Supabase Admin
```

### 6.5 Authorization Roles

| Role | Access |
|------|--------|
| `manager` | Candidate queue, interview feedback, analytics |
| `hr` | Offer approvals, employee records, document verification, audit logs |
| `admin` | Same as manager + hr (both portal logins work) |

Role is checked in `staff_users.role` after Supabase Auth success.

### 6.6 Candidate Access

Candidates do not log in. They access:

- **`/api/candidate-ai`** — public AI chat (no auth required)
- **Document submission** — via a time-limited token embedded in the invite URL (validated through `document_requests` table)

---

## 7. API Reference

> **Interactive docs** are available at `http://localhost:8000/docs` (Swagger UI) when the backend is running.

The API title is **"VTAB Square AI Recruitment API"**, version **1.2.0**.

### 7.1 Authentication Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/login` | None | Staff login — returns JWT access/refresh tokens |
| `POST` | `/api/auth/forgot-password` | None | Request password reset email |
| `POST` | `/api/auth/reset-password` | None | Submit new password with reset token |
| `POST` | `/api/auth/logout` | Bearer | Revoke session server-side + in Supabase Auth |

**Login request body:**
```json
{ "email": "staff@example.com", "password": "yourpassword" }
```

**Login success response:**
```json
{
  "success": true,
  "message": "Login successful.",
  "staff": { "id": "...", "full_name": "...", "email": "...", "role": "manager" },
  "access_token": "<JWT>",
  "refresh_token": "<token>",
  "token_type": "bearer"
}
```

### 7.2 Health & Status Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | None | Root — returns `{"message": "VTAB Square AI Recruitment API is running."}` |
| `GET` | `/health` | None | Health check — returns `{"status": "healthy"}` |
| `GET` | `/docs` | None | Swagger UI (also used as Render health check path) |

### 7.3 Candidate Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/candidates` | Bearer | List all candidates with AI evaluations and applications |
| `GET` | `/api/candidates/{candidate_id}` | Bearer | Get single candidate detail |
| `POST` | `/api/candidate-ai` | None | Candidate AI chat (Gemini) |

### 7.4 Manager Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/manager/candidate-decision` | Bearer | Approve or reject a candidate application |
| `GET` | `/api/manager/analytics` | Bearer | Aggregated recruitment analytics |
| `GET` | `/api/interviews` | Bearer | List all interviews |
| `GET` | `/api/interviews/{interview_id}` | Bearer | Get single interview |
| `POST` | `/api/interview-feedback` | Bearer | Submit interview feedback form |

### 7.5 HR Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/hr/offer-approvals` | Bearer | List applications pending offer approval |
| `POST` | `/api/hr/offer-approvals/{application_id}/approve` | Bearer | Approve offer and onboard candidate |
| `POST` | `/api/hr/offer-approvals/{application_id}/reject` | Bearer | Reject candidate at HR stage |
| `GET` | `/api/hr/employees` | Bearer | List onboarded employees |
| `GET` | `/api/hr/audit-logs` | Bearer | Retrieve audit log entries |
| `GET` | `/api/hr/document-verification` | Bearer | List documents pending verification |
| `POST` | `/api/documents/{document_id}/verify` | Bearer | Trigger AI verification of a document |
| `POST` | `/api/documents/{document_id}/approve` | Bearer | Manually approve a document |

### 7.6 Document Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/document-request/create/{application_id}` | Bearer | Create a document request for a candidate |
| `GET` | `/api/document-request` | Token param | Candidate fetches their document request (via token) |
| `POST` | `/api/document-upload` | Token param | Candidate uploads a document file |
| `POST` | `/api/document-submit` | Token param | Candidate marks documents as submitted |

### 7.7 Recruitment Pipeline

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/recruitment/sync` | Bearer | Trigger a manual recruitment pipeline sync (Gmail / email processing) |

### 7.8 Error Responses

All 4xx business errors return the original `detail` message verbatim.  
All 500 internal errors return a sanitised generic message — **never stack traces or DB details**:

```json
{ "detail": "An internal error occurred. Please try again later." }
```

---

## 8. Database

### 8.1 Technology

- **Supabase** (hosted PostgreSQL)
- Accessed via the Supabase Python client (`supabase-py`)
- Schema managed in the Supabase dashboard — no migration files in this repository

### 8.2 Tables

| Table | Purpose |
|-------|---------|
| `candidates` | Candidate personal information |
| `applications` | Application records linking candidates to job roles |
| `job_roles` | Available positions |
| `job_role_skills` | Skills required per role |
| `staff_users` | Manager, HR, and admin user accounts |
| `ai_evaluations` | AI-generated resume evaluation results |
| `interviews` | Scheduled interview records |
| `interview_feedback` | Manager feedback on interviews |
| `document_requests` | Document collection requests sent to candidates |
| `document_requirements` | Per-role required document definitions |
| `documents` | Uploaded candidate documents with verification status |
| `resumes` | Uploaded resume files |
| `revoked_tokens` | (Supplementary) persistent token revocation if used |
| `audit_logs` | Audit trail of all important system actions |

### 8.3 Storage

Supabase Storage bucket: **`candidate-documents`**

Uploaded files (resumes, supporting documents) are stored here. The `documents.storage_path` column references the file path within this bucket.

> **Important:** Database records and storage files are tightly coupled. Both must be backed up and restored together. See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).

### 8.4 Audit Logs

Every important action is recorded in the `audit_logs` table via `audit_service.log_audit_event()`.

Schema:

| Column | Type | Description |
|--------|------|-------------|
| `action` | string | Event name (e.g. `staff_login_success`, `candidate_approved`) |
| `staff_user_id` | string \| null | ID of the staff member who performed the action |
| `table_name` | string \| null | Affected table |
| `record_id` | string \| null | Affected record ID |
| `new_data` | JSON \| null | Sanitised event data (passwords/tokens redacted) |

Audit logging is **non-blocking** and **fail-safe** — a database failure during audit logging never affects the primary operation.

---

## 9. Candidate & Recruitment Workflow

```
1. Candidate submits application (email or direct submission)
          │
          ▼
2. Gmail reader processes inbound emails → creates candidate + application records
          │
          ▼
3. Gemini AI evaluates the resume → writes ai_evaluations record
          │
          ▼
4. Manager reviews candidate in Manager Portal (Candidate Queue view)
   - Reviews AI evaluation (decision, eligibility, reason)
   - Approves or rejects via POST /api/manager/candidate-decision
          │
          ▼
5. If approved: interview is scheduled via Google Calendar
   Candidate receives invite email (Brevo)
          │
          ▼
6. Manager records interview feedback via POST /api/interview-feedback
   AI evaluates the feedback
          │
          ▼
7. HR receives application in Offer Approvals view
   HR verifies candidate documents (upload + AI verification)
   HR approves offer → POST /api/hr/offer-approvals/{id}/approve
          │
          ▼
8. Candidate onboarded → status becomes "onboarding"
   Appears in Employee Records view
```

### Application Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Application received, awaiting manager review |
| `under_review` | Manager actively reviewing |
| `shortlisted` | Moved forward after initial review |
| `interview_scheduled` | Interview arranged |
| `interviewed` | Interview completed |
| `offer_pending` | Awaiting HR offer approval |
| `onboarding` | Offer accepted, candidate being onboarded |
| `rejected` | Application rejected at any stage |

---

## 10. External Integrations

### 10.1 Google Gemini (AI)

- **Purpose:** Resume analysis, document verification, candidate AI chat, interview feedback evaluation
- **Module:** `Backend/ai_analyzer.py`
- **Configuration:** `GEMINI_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.5-flash`)
- **Failure handling:** If Gemini is unavailable, `gemini_client` is set to `None`; endpoints gracefully return an error without crashing
- **Retry behaviour:** HTTP-level retries are implemented via `tenacity` in key AI call wrappers

### 10.2 Brevo (Email)

- **Purpose:** All transactional email — invitations, decision notifications, password resets, document requests
- **Modules:** `Backend/email_service.py`, `Backend/email_sender.py`
- **Configuration:** `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`
- **API version:** Brevo v3 SMTP email API (`sib-api-v3-sdk`)
- **Failure handling:** Email failures are logged and do not block the primary business operation

### 10.3 Google Calendar & Gmail

- **Purpose:**
  - Gmail: Reads inbound candidate emails to create application records
  - Calendar: Creates interview events and sends invites
- **Modules:** `Backend/gmail_reader.py`, `Backend/google_auth.py`, `Backend/interview_scheduler.py`
- **Authentication:** OAuth 2.0 with token stored locally (`token.json`) or as base64 in `GOOGLE_TOKEN_JSON` for cloud deployments
- **Configuration:** `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_TOKEN_FILE`, `GOOGLE_TOKEN_JSON`
- **Note:** Requires a Google Cloud project with Gmail API and Calendar API enabled

### 10.4 Supabase

- **Purpose:** Primary database (PostgreSQL), file storage, and staff authentication (Supabase Auth)
- **Module:** `Backend/supabase_db.py`
- **Configuration:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (+ fallbacks)
- **Auth mechanism:** Service role key for backend operations; Supabase Auth JWT for user sessions

---

## 11. Monitoring & Support

See **[docs/MONITORING_AND_SUPPORT.md](MONITORING_AND_SUPPORT.md)** for the full guide.

### Quick Reference

| Feature | Implementation |
|---------|---------------|
| HTTP request logging | `structured_logging_middleware` in `app.py` — logs every request with method, path, status, duration |
| Structured log format | `logging_config.py` — `log_structured()` emits key=value pairs to stdout |
| Error logging | `log_internal_error()` in `app.py` — safe, redacted, with optional Sentry capture |
| Health check endpoint | `GET /health` → `{"status": "healthy"}` |
| Render health check | `GET /docs` (set in `render.yaml` `healthCheckPath`) |
| Optional Sentry | `SENTRY_DSN` env var — if set, exceptions are sent to Sentry |

All logs are written to **stdout** and are visible in Render's log dashboard.

---

## 12. Backup & Recovery

See **[docs/BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md)** for the full procedure.

### Quick Reference

```bash
# Dry-run (verify connectivity, no files written)
python scripts/backup_db.py --dry-run --tables candidates applications

# Full backup of all 14 tables
python scripts/backup_db.py --output ./backup_output

# Verify an existing backup
python scripts/backup_db.py --verify ./backup_output/backup_<timestamp>
```

The backup script is **completely standalone** — it does not import `app.py` and has zero impact on the running application.

---

## 13. Deployment

### 13.1 Render Blueprint

The project deploys on **Render** using `render.yaml` (Render Blueprint):

```yaml
services:
  - type: web          # Backend
    name: ai-recruitment-backend
    runtime: python
    rootDir: Backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /docs

  - type: web          # Frontend
    name: ai-recruitment-frontend
    runtime: static
    rootDir: Frontend
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

Both services deploy to **Oregon (us-west-2)** on the Render **free tier**.

### 13.2 Environment Variables on Render

Set the following in the Render dashboard for the **backend** service:

```
GEMINI_API_KEY
BREVO_API_KEY
BREVO_SENDER_EMAIL
SUPABASE_URL
SUPABASE_KEY              (or SUPABASE_SERVICE_ROLE_KEY)
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_ANON_KEY
ALLOWED_ORIGINS           (set to your Render frontend URL)
GOOGLE_TOKEN_JSON         (base64-encoded token.json for Gmail/Calendar)
```

Set the following for the **frontend** service:

```
VITE_API_BASE_URL         (set to your Render backend URL)
```

### 13.3 Deployment Order

1. Deploy the **backend** first — note its URL (e.g. `https://ai-recruitment-backend.onrender.com`)
2. Set `VITE_API_BASE_URL` on the frontend service to the backend URL
3. Set `ALLOWED_ORIGINS` on the backend to include the frontend URL
4. Deploy the **frontend**

### 13.4 Health Check Verification

After deployment:

```bash
curl https://ai-recruitment-backend.onrender.com/health
# Expected: {"status": "healthy"}

curl https://ai-recruitment-backend.onrender.com/docs
# Expected: Swagger UI HTML (200 OK)
```

### 13.5 Rollback

There are no database migrations. Rollback means redeploying the previous commit via Render's deployment history:

1. Go to **Render dashboard → Service → Deploys**
2. Find the last known-good deploy
3. Click **Redeploy**

---

## 14. Testing

### 14.1 Regression Test Suites

All test suites are in the `scratch/` directory and use Python's `unittest` framework.

Run all suites from the project root:

```bash
python scratch/test_task1_retries.py        # API retry behaviour (13 tests)
python scratch/test_task2_password_reset.py # Password reset flow (13 tests)
python scratch/test_task3_logout.py         # Server-side logout (7 tests)
python scratch/test_task4_config.py         # Secrets hygiene and config (8 tests)
python scratch/test_task5_audit.py          # Audit trail logging (59 tests)
python scratch/test_task6_error_handling.py # Error sanitisation (143 tests)
python scratch/test_task7_backup_recovery.py# Backup/recovery (56 tests)
python scratch/test_task9_monitoring.py     # Monitoring/logging (16 tests)
python scratch/test_task10_accessibility.py # WCAG accessibility (29 tests)
```

Or use pytest (where compatible):

```bash
python -m pytest scratch/test_task1_retries.py scratch/test_task2_password_reset.py \
  scratch/test_task3_logout.py scratch/test_task4_config.py \
  scratch/test_task9_monitoring.py scratch/test_task10_accessibility.py -v
```

### 14.2 Frontend Build Verification

```bash
cd Frontend
npm run build
# Expected: Build completes with no errors
# Output: Frontend/dist/
```

### 14.3 Backend Compile Check

```bash
python -m py_compile Backend/app.py
# Expected: No output (exit code 0 = success)
```

### 14.4 Accessibility Tests

The accessibility suite (`test_task10_accessibility.py`) performs static-analysis of the source files — no browser or Selenium required. It checks for WCAG 2.2 AA attributes including `aria-label`, `role="dialog"`, `:focus-visible`, skip links, and `aria-live` regions.

### 14.5 Test Results (Baseline)

| Task | Tests | Status |
|------|-------|--------|
| Task 1 — API Retries | 13/13 | PASS |
| Task 2 — Password Reset | 13/13 | PASS |
| Task 3 — Session Security | 7/7 | PASS |
| Task 4 — Secrets Hygiene | 8/8 | PASS |
| Task 5 — Audit Trail | 59/59 | PASS |
| Task 6 — Error Handling | 143/143 | PASS |
| Task 7 — Backup & Recovery | 56/56 | PASS |
| Task 9 — Monitoring | 16/16 | PASS |
| Task 10 — Accessibility | 29/29 | PASS |
| Frontend build | — | PASS |
| Backend py_compile | — | PASS |
| **Total** | **344/344** | **100%** |

---

## 15. Security Considerations

### 15.1 Secrets Management

- All secrets are loaded from environment variables — **never hard-coded**
- `Backend/.env` is git-ignored
- `Backend/config.py` is the single location where secrets are read
- Secret values are never logged; `audit_service.sanitize_audit_data()` redacts sensitive keys before any persistence

### 15.2 Error Sanitisation

- All 500 errors return a generic message to the client: `"An internal error occurred. Please try again later."`
- Stack traces, SQL statements, file paths, and credentials are **never** returned to the client
- `LEAK_INDICATORS` list in `app.py` catches common leakage patterns

### 15.3 Password & Token Handling

- Passwords are never stored in the application — Supabase Auth handles hashing
- JWT tokens are stored in React state only (not localStorage/sessionStorage)
- Logout calls `supabase.auth.sign_out()` and adds the token hash to an in-memory revocation cache
- Token hashes (SHA-256 digest) — never raw tokens — are stored in the revocation cache

### 15.4 CORS

- Only origins listed in `ALLOWED_ORIGINS` are permitted
- `allow_credentials=False` — prevents cookie-based cross-origin attacks
- For local development, `http://localhost:5173` and `http://127.0.0.1:5173` are included by default

### 15.5 Audit Logging

- All significant actions are audited: login success/failure, password reset, candidate decisions, document approvals
- Audit logs are fail-safe — a logging failure never affects the primary operation
- Sensitive fields (passwords, tokens, API keys) are redacted before audit log persistence

### 15.6 Rate Limiting

- `slowapi` is installed as a dependency; rate limiting can be applied per-endpoint if required

### 15.7 Backup Security

- Backup files must be stored securely (encrypted at rest)
- Backup metadata does not include credential values — only placeholder references
- See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) §Security for the full backup security policy

---

## 16. Troubleshooting

### 16.1 Backend Does Not Start

**Symptoms:** `uvicorn` exits immediately or returns an import error.

**Check:**
1. Is the virtual environment activated? (`which python` should point to `venv/`)
2. Are all dependencies installed? (`pip install -r requirements.txt`)
3. Is `.env` present and populated? (`SUPABASE_URL` and `SUPABASE_KEY` are required at import time)
4. Check for Python syntax errors: `python -m py_compile Backend/app.py`
5. Review stdout for import errors

### 16.2 Frontend Does Not Start / Build Fails

**Symptoms:** `npm run dev` or `npm run build` fails.

**Check:**
1. Is Node.js 18+ installed? (`node --version`)
2. Run `npm install` in the `Frontend/` directory
3. Check for JSX syntax errors in `App.jsx`
4. Check `vite.config.js` is not corrupted
5. Review the Vite build output for specific error messages

### 16.3 Login Fails (401 / 403)

**Symptom:** Login returns 401 "Invalid email or password" or 403 "not an active staff member".

**Check:**
1. Is the user's account in the `staff_users` table with `is_active = true`?
2. Is the user's `role` one of `manager`, `hr`, `admin`?
3. Is the user's `auth_user_id` or `email` correctly linked to their Supabase Auth account?
4. Check Supabase Auth dashboard for the user's account status

### 16.4 Authentication Token Errors (401 on Protected Routes)

**Symptom:** API returns 401 after login appeared to succeed.

**Check:**
1. Is the token being sent as `Authorization: Bearer <token>`? (Check browser network tab)
2. Has the Supabase session expired? (Default 1-hour lifetime)
3. Was the server restarted (clearing in-memory revocation cache)? Re-login should fix this.
4. Check Supabase dashboard → Authentication → Users for session status

### 16.5 Gemini AI Not Working

**Symptom:** AI chat returns an error or `/api/candidate-ai` returns 500.

**Check:**
1. Is `GEMINI_API_KEY` set and valid?
2. Is the model name correct? Default: `gemini-2.5-flash`
3. Check Gemini API quotas in Google Cloud Console
4. Check backend logs for `[SERVER ERROR]` lines with `gemini` context

### 16.6 Email Not Sending

**Symptom:** Password reset emails or candidate notifications are not received.

**Check:**
1. Is `BREVO_API_KEY` set and valid?
2. Is `BREVO_SENDER_EMAIL` a verified sender in your Brevo account?
3. Check Brevo dashboard → Transactional → Email Logs for delivery status
4. Check backend logs for `send_email` failures
5. Check spam/junk folder

### 16.7 Google Calendar / Gmail Not Working

**Symptom:** Interview scheduling fails or Gmail emails are not processed.

**Check:**
1. Is `GOOGLE_TOKEN_JSON` (cloud) or `token.json` (local) present and valid?
2. Has the OAuth token expired? Re-authorize via `google_auth.py`
3. Are the Gmail API and Calendar API enabled in Google Cloud Console?
4. Check the scopes on the OAuth token match the required APIs

### 16.8 Deployment Fails on Render

**Symptom:** Render build fails or health check does not pass.

**Check:**
1. Review Render build logs for pip install errors or npm build errors
2. Confirm all required environment variables are set in the Render dashboard
3. Backend health check: `GET /docs` must return 200
4. For the static frontend: confirm `dist/` is being generated by `npm run build`
5. Check `ALLOWED_ORIGINS` includes the deployed frontend URL

### 16.9 Database Connection Errors

**Symptom:** Any endpoint returns a database-related error (caught and returned as 500).

**Check:**
1. Is `SUPABASE_URL` correct and reachable?
2. Is `SUPABASE_SERVICE_ROLE_KEY` valid and not expired?
3. Check Supabase dashboard → Project Status for any outages
4. Review backend logs for `[SERVER ERROR]` messages with `supabase` or `psycopg2` context

---

## 17. Developer Workflow

Follow this workflow for all changes to ensure the existing application remains stable:

```
1.  Understand the change
    ├── Inspect the existing code relevant to the feature
    ├── Identify all files that will be affected
    └── Confirm no unintended side effects

2.  Implement the minimal change
    ├── Make the smallest safe modification
    ├── Preserve all existing function signatures and API contracts
    └── Add, do not replace, unless explicitly required

3.  Verify syntax
    ├── python -m py_compile Backend/app.py
    └── cd Frontend && npm run build

4.  Run focused tests
    └── python scratch/test_task<N>_<name>.py

5.  Run full regression suite
    ├── python scratch/test_task1_retries.py
    ├── python scratch/test_task2_password_reset.py
    ├── python scratch/test_task3_logout.py
    ├── python scratch/test_task4_config.py
    ├── python scratch/test_task5_audit.py
    ├── python scratch/test_task6_error_handling.py
    ├── python scratch/test_task7_backup_recovery.py
    ├── python scratch/test_task9_monitoring.py
    └── python scratch/test_task10_accessibility.py

6.  Verify frontend build
    └── cd Frontend && npm run build

7.  Review changes
    ├── Confirm no runtime files were accidentally changed for documentation tasks
    └── Confirm no secrets appear in any committed file

8.  Document the change
    └── Update DEVELOPER_GUIDE.md or specialist docs as appropriate
```

> **Safety rule:** Existing application stability always takes priority over new features or improvements. If a change risks breaking existing functionality, stop and reassess.

---

*This guide reflects the application as of Sprint 1 completion (Tasks 1–10).*  
*For backup procedures, see [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).*  
*For monitoring, see [MONITORING_AND_SUPPORT.md](MONITORING_AND_SUPPORT.md).*
