# VTAB Square — AI Recruitment System

**VTAB Square** is an end-to-end AI-assisted recruitment platform for managing the full candidate lifecycle: from document collection and resume evaluation to interview scheduling, manager/HR approval, and employee onboarding.

---

## Quick Start

| Step | Command |
|------|---------|
| Backend (Python 3.12+) | `cd Backend && pip install -r requirements.txt && uvicorn app:app --reload` |
| Frontend (Node 18+) | `cd Frontend && npm install && npm run dev` |

Copy `Backend/.env.example` → `Backend/.env` and fill in your secrets before starting.

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** | Complete developer reference — architecture, setup, API, auth, database, deployment, testing, troubleshooting |
| **[docs/BACKUP_AND_RECOVERY.md](docs/BACKUP_AND_RECOVERY.md)** | Disaster recovery procedures and backup CLI tool |
| **[docs/MONITORING_AND_SUPPORT.md](docs/MONITORING_AND_SUPPORT.md)** | Structured logging, health checks, error monitoring, operational support |

---

## High-Level Architecture

```
Browser (React + Vite SPA)
        │  HTTPS / CORS
        ▼
FastAPI Backend (Python / Uvicorn)
  ├── Authentication  ──────────────► Supabase Auth
  ├── Business Logic
  ├── Audit Logging   ──────────────► Supabase PostgreSQL (audit_logs)
  ├── AI Evaluation   ──────────────► Google Gemini API
  ├── Email           ──────────────► Brevo (transactional email)
  └── Calendar/Gmail  ──────────────► Google Calendar & Gmail APIs
        │
        ▼
Supabase
  ├── PostgreSQL database (14 tables)
  └── Storage bucket  (candidate-documents)
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8 |
| Backend | Python, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth (JWT bearer tokens) |
| AI | Google Gemini (`gemini-2.5-flash`) |
| Email | Brevo (formerly Sendinblue) |
| Calendar / Gmail | Google APIs (OAuth 2.0) |
| Deployment | Render (free tier — backend web service + static frontend) |

---

## Repository Structure

```
AI-Recruitment-System/
├── Backend/
│   ├── app.py                    # FastAPI application (main entry point)
│   ├── config.py                 # Centralised environment configuration
│   ├── audit_service.py          # Non-blocking audit logging
│   ├── logging_config.py         # Structured logging + optional Sentry
│   ├── supabase_db.py            # Supabase client initialisation
│   ├── ai_analyzer.py            # Gemini resume analysis
│   ├── email_service.py          # Brevo email sending
│   ├── interview_scheduler.py    # Google Calendar integration
│   ├── gmail_reader.py           # Gmail inbox processing
│   ├── requirements.txt          # Python dependencies
│   └── .env.example              # Environment variable template
├── Frontend/
│   ├── src/
│   │   ├── App.jsx               # Entire React application (single-file)
│   │   ├── App.css               # All component styles
│   │   └── index.css             # Root reset styles
│   ├── index.html                # SPA entry point
│   ├── package.json              # Node dependencies
│   └── vite.config.js            # Vite build configuration
├── docs/
│   ├── DEVELOPER_GUIDE.md        # ← You are here (comprehensive reference)
│   ├── BACKUP_AND_RECOVERY.md    # Disaster recovery procedures
│   └── MONITORING_AND_SUPPORT.md # Monitoring and operational support
├── scripts/
│   └── backup_db.py              # Standalone database backup CLI tool
├── scratch/
│   └── test_task*.py             # Regression test suites (Tasks 1–10)
├── database/                     # (Empty — schema managed in Supabase)
├── render.yaml                   # Render deployment blueprint
└── .gitignore
```

---

## Deployment

Deployed on **Render** using `render.yaml`. Two services:

- **`ai-recruitment-backend`** — Python web service, starts with `uvicorn app:app`
- **`ai-recruitment-frontend`** — Static site built with `npm run build`, served from `Frontend/dist/`

Health check: `GET /docs` (FastAPI Swagger UI — returns 200 when backend is healthy).

See **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** for full deployment instructions.

---

## License

Internal project — VTAB Square.
