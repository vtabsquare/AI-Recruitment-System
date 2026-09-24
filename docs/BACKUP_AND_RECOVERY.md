# VTAB Square AI Recruitment System — Backup & Disaster Recovery Guide

This document establishes the official backup and disaster recovery procedures for the **VTAB Square AI Recruitment System**.

---

## 1. System Architecture & Inventory

The AI Recruitment System consists of four primary operational tiers:

```
┌────────────────────────────────────────────────────────┐
│                   Vite + React Frontend                │
│                 (SPA / Static Web Assets)              │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / REST
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│               (Python Application Server)              │
└──────┬────────────────────┬────────────────────┬───────┘
       │                    │                    │
┌──────▼───────┐     ┌──────▼───────┐     ┌──────▼───────┐
│   Supabase   │     │  Google APIs │     │  Brevo Email │
│  PostgreSQL  │     │   (Gmail &   │     │ (SMTP API /  │
│  & Storage   │     │   Calendar)  │     │  Invites)    │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Component Details
| Component | Technology | State / Persistence | Criticality |
| :--- | :--- | :--- | :--- |
| **Relational Database** | Supabase (PostgreSQL 15+) | All structured operational data, accounts, applications, audit logs | **Highest** |
| **Object Storage** | Supabase Storage (`candidate-documents`) | Uploaded PDF, PNG, JPEG candidate verification documents | **High** |
| **Application Server** | Python 3.12 / FastAPI / Uvicorn | Stateless runtime (configuration via environment variables) | **Medium** |
| **Frontend Client** | React 18 / Vite / TailwindCSS | Stateless static bundle | **Low** |
| **External Integrations** | Google Gmail & Calendar, Google Gemini AI, Brevo SMTP | External SaaS APIs (stateless API tokens/credentials) | **Medium** |

---

## 2. Backup Scope

### 2.1 Database (PostgreSQL / Supabase)

The system relies on 14 primary relational tables:
1. `job_roles`: Configured job role titles, minimum CGPA requirements, required skill match thresholds.
2. `job_role_skills`: Skills associated with each job role and mandatory flags.
3. `candidates`: Registered candidates, contact details, email addresses (unique constraint).
4. `applications`: Application records linking candidates to job roles, stages, statuses, and review timestamps.
5. `staff_users`: Staff accounts (Manager, HR, Admin), active status, and auth user references.
6. `ai_evaluations`: AI resume analysis evaluations, eligibility classifications, and extracted credentials.
7. `interviews`: Scheduled interviews, Google Calendar event links, and candidate slots.
8. `interview_feedback`: Manager interview evaluation ratings, comments, and recommendations.
9. `document_requests`: Active document upload tokens, expiration dates, and completion status.
10. `document_requirements`: Document types required per application (e.g. ID proof, degree certificates).
11. `documents`: Uploaded candidate documents, storage paths, AI verification results, and HR approval status.
12. `revoked_tokens`: Invalidated JWT tokens recorded upon staff session logout.
13. `audit_logs`: Immutable chronological log of staff actions, auth events, decisions, and system operations.
14. `resumes`: Extracted text and analysis records for uploaded resumes.

#### Distinguishing Backup Types:
- **Schema Backup (`--schema-only`)**: Captures DDL statements (table structures, column definitions, primary/foreign keys, unique constraints, and indexes) without any table rows.
- **Data Backup (`--data-only` / JSON Export)**: Captures table records and row contents without modifying DDL. Useful for incremental data extraction and table-level restorations.
- **Complete Backup**: Full binary or plain-SQL dump capturing both schema and data in topological order (respecting foreign key dependencies).

---

### 2.2 Candidate Documents / Object Storage

The application stores uploaded candidate verification documents in Supabase Storage under the bucket:
```text
Bucket Name: candidate-documents
```

#### Tight Coupling Between Database and Storage
- When a candidate uploads a document, the binary object is stored in `candidate-documents` with a key formatted as:
  `{application_id}/{document_type}_{hash}.{ext}`
- A corresponding database record is inserted into the `documents` table containing the column:
  `storage_path` (e.g., `app_123/id_proof_a1b2c3d4.pdf`)
- When HR or the AI verification engine inspects a document, it queries `documents.storage_path` and downloads the bytes from the `candidate-documents` bucket.
- **Critical Disaster Recovery Rule**: Database records and storage objects **must be backed up and restored together**. Restoring database records without corresponding storage objects causes broken download links and 500 errors during HR verification. Restoring storage objects without database rows results in orphaned, unmanaged files.

---

### 2.3 Configuration / Secrets

All application secrets and environment configurations must be backed up securely in a centralized secret vault (e.g. AWS Secrets Manager, HashiCorp Vault, 1Password, or Render Secret Groups).

> [!CAUTION]
> **Zero Plaintext Secrets in Repository**: Never commit real secrets, API keys, or `.env` files into Git or backup archives. Use secure placeholders only.

#### Required Environment Variables Checklist:
```bash
# ── Google Gemini AI ──────────────────────────────────────────
GEMINI_API_KEY=<restore from secure secret store>
GEMINI_MODEL=gemini-2.5-flash

# ── Brevo (Transactional Email Service) ───────────────────────
BREVO_API_KEY=<restore from secure secret store>
BREVO_SENDER_EMAIL=<restore from secure secret store>
BREVO_SENDER_NAME=VTAB Square Recruitment
BREVO_API_URL=https://api.brevo.com/v3/smtp/email

# ── Supabase (Database & Authentication) ──────────────────────
SUPABASE_URL=<restore from secure secret store>
SUPABASE_KEY=<restore from secure secret store>
SUPABASE_SERVICE_ROLE_KEY=<restore from secure secret store>
SUPABASE_ANON_KEY=<restore from secure secret store>

# ── Company & Recruiter Defaults ──────────────────────────────
COMPANY_EMAIL=<restore from secure secret store>
INTERVIEW_MANAGER_EMAIL=<restore from secure secret store>

# ── Frontend & CORS Configuration ─────────────────────────────
FRONTEND_URL=https://your-frontend-domain.com
ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:5173

# ── Google OAuth & Calendar / Gmail API ────────────────────────
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
GOOGLE_TOKEN_JSON=<restore from secure secret store (optional base64)>
```

---

## 3. Operational Backup Procedures

### 3.1 Automated Standalone Backup Script (`scripts/backup_db.py`)

A dedicated, non-invasive operational script is provided in the repository to export table data, document metadata, and generate SHA-256 checksums:

```bash
# Run full backup of all 14 tables into the default ./backups/db directory:
python scripts/backup_db.py

# Run backup to a specific directory and verify archive integrity:
python scripts/backup_db.py --output-dir /var/backups/recruitment --verify

# Dry-run connectivity test (tests connection and lists tables without writing files):
python scripts/backup_db.py --dry-run
```

#### Backup Archive Structure:
```text
backups/db/backup_20260923_143000/
├── metadata.json                 # Execution timestamp, record counts, SHA-256 checksums
├── applications.json             # Application records
├── candidates.json               # Candidate profiles
├── staff_users.json              # Staff accounts
├── job_roles.json                # Job roles & minimum criteria
├── job_role_skills.json          # Skill matrices
├── ai_evaluations.json           # Resume evaluation outputs
├── interviews.json               # Scheduled interview records
├── interview_feedback.json       # Manager review submissions
├── document_requests.json        # Active document tokens
├── document_requirements.json    # Required documents per role
├── documents.json                # Uploaded document metadata & verification status
├── revoked_tokens.json           # Revoked session tokens
├── audit_logs.json               # Complete immutable audit log trail
└── resumes.json                  # Parsed resume records
```

### 3.2 Native PostgreSQL Dump (`pg_dump`)

For enterprise environments requiring full binary or SQL dumps directly from PostgreSQL:

```bash
# 1. Full database backup (Schema + Data):
pg_dump -h db.<PROJECT_REF>.supabase.co -U postgres -p 5432 -d postgres \
  --format=custom \
  --file=recruitment_full_$(date +%Y%m%d_%H%M%S).dump

# 2. Schema-only backup:
pg_dump -h db.<PROJECT_REF>.supabase.co -U postgres -p 5432 -d postgres \
  --schema-only \
  --file=recruitment_schema_$(date +%Y%m%d_%H%M%S).sql

# 3. Data-only backup:
pg_dump -h db.<PROJECT_REF>.supabase.co -U postgres -p 5432 -d postgres \
  --data-only \
  --format=custom \
  --file=recruitment_data_$(date +%Y%m%d_%H%M%S).dump
```

### 3.3 Candidate Document Storage Backup

To back up files from the `candidate-documents` bucket:
1. **Via Supabase CLI / S3 API**:
   ```bash
   # Synchronize bucket files to local backup storage
   aws s3 sync s3://<PROJECT_REF>/candidate-documents /var/backups/candidate-documents/ \
     --endpoint-url https://<PROJECT_REF>.supabase.co/storage/v1/s3
   ```
2. **Via Standalone Python Script**:
   Query all non-null `storage_path` entries from `documents.json` and download each file using `supabase.storage.from_("candidate-documents").download(path)`.

---

## 4. Step-by-Step Recovery Procedure

Follow these 10 sequential steps to restore the system from scratch or in a replacement environment:

### Step 1 — Prepare Replacement Environment
1. Provision a host server running Ubuntu 22.04 LTS / Debian 12 / Windows Server.
2. Install system runtimes:
   - Python 3.12+ (`python3 --version`)
   - Node.js 20+ / 24+ (`node --version`) and npm (`npm --version`)
   - Git (`git --version`)
3. Clone or deploy the application repository into the target workspace:
   ```bash
   git clone <REPO_URL> /app/recruitment-system
   cd /app/recruitment-system
   ```

### Step 2 — Restore Configuration & Secrets
1. Retrieve environment secrets from the secure vault.
2. Populate `Backend/.env` with production values (Supabase credentials, Gemini key, Brevo key, CORS origins).
3. If Google Calendar/Gmail integrations are enabled, place `credentials.json` and `token.json` in `Backend/` (or populate `GOOGLE_TOKEN_JSON` with the base64 token string).

### Step 3 — Restore Database
1. Connect to the replacement Supabase or PostgreSQL instance.
2. If restoring schema from SQL:
   ```bash
   psql -h <DB_HOST> -U postgres -d postgres -f recruitment_schema_YYYYMMDD.sql
   ```
3. If restoring data from custom dump:
   ```bash
   pg_restore -h <DB_HOST> -U postgres -d postgres --data-only recruitment_data_YYYYMMDD.dump
   ```
4. If restoring from JSON backup archive, execute the table loader script to insert records in topological order (`job_roles` -> `candidates` -> `applications` -> `documents` -> `audit_logs`).

### Step 4 — Restore Candidate Documents
1. Ensure the `candidate-documents` storage bucket exists in Supabase.
2. Configure bucket access policies (private bucket with service role access).
3. Restore the binary document objects matching the `storage_path` values in the `documents` table:
   ```bash
   aws s3 sync /var/backups/candidate-documents/ s3://<PROJECT_REF>/candidate-documents \
     --endpoint-url https://<PROJECT_REF>.supabase.co/storage/v1/s3
   ```

### Step 5 — Restore Application Code
1. Checkout the known-good release commit or Git release tag:
   ```bash
   git checkout tags/v1.0.0
   ```
2. Set up Python virtual environment and install backend dependencies:
   ```bash
   cd Backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Install frontend dependencies:
   ```bash
   cd ../Frontend
   npm install
   ```

### Step 6 — Start Backend
1. Start the FastAPI backend service:
   ```bash
   cd ../Backend
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
2. Verify startup in logs:
   - Check that database connection initializes without error.
   - Confirm background inbox listener thread starts cleanly.
3. Verify backend health endpoint:
   ```bash
   curl -I http://localhost:8000/docs
   # Expected: HTTP/1.1 200 OK
   ```

### Step 7 — Start Frontend
1. Build production static bundle:
   ```bash
   cd ../Frontend
   npm run build
   ```
   Confirm build succeeds with zero errors into `Frontend/dist/`.
2. Serve static assets via Web Server (Nginx / Caddy / Render Static Host):
   ```bash
   npm run preview -- --port 5173
   ```

### Step 8 — Validate Authentication
1. Perform test login via `POST /api/auth/login` with an active staff account.
2. Verify JWT access token and refresh token are returned.
3. Perform test logout via `POST /api/auth/logout` and verify token is revoked.
4. Verify password reset request via `POST /api/auth/forgot-password`.

### Step 9 — Validate Database Connectivity
1. Perform authenticated request to `GET /api/candidates` with a Manager bearer token.
2. Verify response status is `200 OK` and candidate count matches expected restored count.
3. Perform authenticated request to `GET /api/hr/audit-logs` and verify audit events are visible.

### Step 10 — Validate Critical Workflows
1. **Candidate Review**: Verify candidate profiles, CGPA scores, and AI evaluations display accurately.
2. **Interview Management**: Check that existing scheduled interviews load on `/api/interviews`.
3. **Document Verification**: Open an existing document verification record and verify that download/view loads the correct document from Supabase Storage.
4. **Audit Trail**: Confirm that validation actions generate new audit records in `audit_logs`.

---

## 5. Disaster Recovery Scenarios

### Scenario A — Database Loss or Corruption
- **Trigger**: Accidental data deletion, corrupted tables, or database cluster outage.
- **Action**:
  1. Freeze incoming write traffic (set backend to maintenance mode if feasible).
  2. Identify the most recent valid backup timestamp in `backups/db/`.
  3. Recreate clean tables if corrupted, or restore to a new Supabase project.
  4. Restore table data using `pg_restore` or `scripts/backup_db.py` restore loader.
  5. Cross-verify record counts between `metadata.json` and PostgreSQL tables.
  6. Reconnect backend and resume traffic.

### Scenario B — Application Server Loss
- **Trigger**: Server hardware failure, cloud VM termination, or host operating system failure.
- **Action**:
  1. Provision a new server instance.
  2. Reinstall Python 3.12 and Node.js.
  3. Pull application code from Git.
  4. Inject configuration from the secure vault into `Backend/.env`.
  5. Launch backend via Uvicorn and build frontend static bundle.
  6. Point DNS / reverse proxy to the new server IP.

### Scenario C — Candidate Document / Storage Loss
- **Trigger**: Storage bucket deletion, object corruption, or cloud storage outage.
- **Action**:
  1. Recreate the `candidate-documents` bucket in Supabase Storage.
  2. Restore object files from the offsite storage backup sync.
  3. Run an audit query matching `documents.storage_path` against bucket keys to verify zero missing files.
  4. Verify that HR document approval and candidate submission links load successfully.

### Scenario D — Configuration / Secret Loss
- **Trigger**: Lost `.env` file or corrupted deployment environment variables.
- **Action**:
  1. Access the organization's master credential vault.
  2. If Supabase keys were compromised or lost, rotate keys in the Supabase Dashboard and copy the new `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_ANON_KEY`.
  3. Update `Backend/.env` with the restored credentials.
  4. Restart the backend process (`systemctl restart recruitment-backend` or restart Uvicorn).

### Scenario E — Full Environment Loss (Bare-Metal Disaster)
- **Trigger**: Complete datacenter outage, loss of primary cloud provider account.
- **Execution Order**:
  ```text
  1. Provision new Cloud Provider / Host
                  ↓
  2. Restore Application Code (Git)
                  ↓
  3. Restore Environment & Secrets (Vault)
                  ↓
  4. Provision replacement Supabase Project & Restore Database
                  ↓
  5. Restore Storage Bucket & Document Objects
                  ↓
  6. Start Backend (Verify /docs)
                  ↓
  7. Build & Deploy Frontend (Vite)
                  ↓
  8. Execute End-to-End Smoke Tests
  ```

---

## 6. Recovery Objectives

### RPO — Recovery Point Objective
> **Status:** To be defined by system owner.

*Operational Guidance / Recommendation*:
- For recruitment transactions and interview scheduling, a recommended RPO target is **\le 24 hours** using daily automated database backups, or **\le 1 hour** if continuous Write-Ahead Log (WAL) archiving / Point-in-Time Recovery (PITR) is enabled on Supabase Pro.

### RTO — Recovery Time Objective
> **Status:** To be defined by system owner.

*Operational Guidance / Recommendation*:
- For stateless application server restoration: **< 30 minutes**.
- For full database and storage restoration from backup: **< 2 hours**.

---

## 7. Backup Frequency & Retention Policy

> **Status:** To be decided by the deployment/operations owner.

### Recommended Operational Baseline:
| Asset | Frequency | Storage Location | Retention Period |
| :--- | :--- | :--- | :--- |
| **Database Data** | Daily at 02:00 UTC | Encrypted Offsite S3 Bucket | 30 days daily, 12 months monthly |
| **Database Schema** | On every deployment / code release | Version-controlled Git + S3 | Retained with release history |
| **Candidate Documents** | Continuous / Daily Differential Sync | Encrypted Object Storage | 90 days after recruitment cycle |
| **Application Configuration** | On every change / rotation | Encrypted Secrets Vault | Revision history retained in vault |
| **Audit Logs** | Daily incremental archive | WORM (Write Once Read Many) Storage | 1–3 years per compliance policy |

---

## 8. Backup Security & Access Control

1. **Access Control**: Backup archives must be stored in private, restricted-access storage locations accessible only to authorized DevOps/Site Reliability Engineers.
2. **Encryption in Transit & at Rest**:
   - Backups transferred over network must use TLS 1.3.
   - Backup files stored on disk or in cloud buckets must use AES-256 or AWS KMS server-side encryption.
3. **Hygiene & Redaction**: Backups of database records must never be stored alongside plaintext master passwords or private encryption keys.
4. **Immutability**: Audit logs and historical backups should be protected against deletion or tampering using object lock policies.

---

## 9. Backup Verification & Safe Drill Protocol

> [!IMPORTANT]
> **Non-Production Testing Rule**: Never test database restore procedures by overwriting the production database. All restore drills must be performed in an isolated staging or local test environment.

### Verification Checklist for Every Backup Run:
1. Verify the backup archive file exists at the destination path.
2. Verify file size is greater than zero and matches expected baseline.
3. Verify `metadata.json` SHA-256 hashes match table file contents.
4. Validate that exported JSON files are well-formed and can be deserialized.
5. In scheduled quarterly disaster drills:
   - Restore the backup archive into a separate staging Supabase database.
   - Run automated test suite (`scratch/test_task7_backup_recovery.py`).
   - Confirm all 14 tables report identical record counts.
