# VTAB Square — Release Management

This document defines the release process for the AI Recruitment System.  
For full architecture and setup, see [docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

---

## Table of Contents

1. [Existing Release Setup](#1-existing-release-setup)
2. [CI Pipeline](#2-ci-pipeline)
3. [Branch and Release Strategy](#3-branch-and-release-strategy)
4. [Versioning](#4-versioning)
5. [Release Checklist](#5-release-checklist)
6. [Production Deployment](#6-production-deployment)
7. [Rollback Strategy](#7-rollback-strategy)
8. [Database Migration Safety](#8-database-migration-safety)
9. [Environment Separation](#9-environment-separation)
10. [Release Artifacts and Traceability](#10-release-artifacts-and-traceability)
11. [Security Rules](#11-security-rules)

---

## 1. Existing Release Setup

### What was present before Task 12

| Item | Status |
|------|--------|
| GitHub Actions | Not present |
| Docker | Not present |
| Other CI system | Not present |
| Render deployment | Active — `render.yaml` Blueprint |
| Frontend test runner | None (no Vitest/Jest) |
| Backend regression tests | 9 suites in `scratch/`, 344 tests total |
| Secret protection | `.gitignore` excludes `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key` |

### How Render currently deploys

Render reads `render.yaml` to configure two services:

| Service | Type | Build | Start |
|---------|------|-------|-------|
| `ai-recruitment-backend` | Python web service | `pip install -r requirements.txt` | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| `ai-recruitment-frontend` | Static site | `npm install && npm run build` | Served from `Frontend/dist/` |

Render can be configured to auto-deploy when its connected Git branch receives a push, **or** to require a manual deploy trigger from the Render dashboard. Check the Render dashboard to confirm which mode is active for this project.

---

## 2. CI Pipeline

### Overview

The CI pipeline (`.github/workflows/ci.yml`) validates every push and pull request before code reaches the main branch.

```
Push / Pull Request
        │
        ├── Job 1: backend-validation
        │    ├── Python 3.12 setup
        │    ├── pip install -r requirements.txt
        │    ├── python -m py_compile Backend/app.py
        │    ├── Task 1  — API Retries         (13 tests)
        │    ├── Task 2  — Password Reset       (13 tests)
        │    ├── Task 3  — Session Security      (7 tests)
        │    ├── Task 4  — Secrets Hygiene       (8 tests)
        │    ├── Task 5  — Audit Trail          (59 tests)
        │    ├── Task 6  — Error Handling      (143 tests)
        │    ├── Task 7  — Backup & Recovery    (56 tests)
        │    ├── Task 9  — Monitoring           (16 tests)
        │    └── Task 10 — Accessibility        (29 tests)
        │         Total: 344 tests
        │
        ├── Job 2: frontend-validation
        │    ├── Node.js 20 setup
        │    ├── npm install
        │    ├── npm run lint  (advisory — non-blocking)
        │    └── npm run build (MUST pass)
        │
        └── Job 3: security-checks
             ├── .env not committed
             ├── credentials.json not committed
             ├── token.json not committed
             ├── *.pem / *.key not committed
             ├── All 4 documentation files present
             └── render.yaml present with expected services
```

### What CI does NOT do

- **Does not deploy to production.** Render handles deployment separately.
- **Does not connect to the real database.** All tests use dummy env vars.
- **Does not call Gemini, Brevo, or Google APIs.** No real external service is contacted during CI.
- **Does not modify `render.yaml`** or any production configuration.

### CI environment variables

All backend CI env vars are dummy/test values defined directly in the workflow `env:` block:

```yaml
SUPABASE_URL: "https://ci-test-placeholder.supabase.co"
SUPABASE_KEY: "ci-test-placeholder-key"
GEMINI_API_KEY: "ci-test-placeholder-gemini-key"
BREVO_API_KEY: "ci-test-placeholder-brevo-key"
...
```

No GitHub Actions secrets are required for CI validation. The existing test suites are designed to work offline with dummy configuration.

### CI failure behaviour

- Any failed backend test suite → workflow fails, PR cannot be merged.
- Failed frontend build → workflow fails, PR cannot be merged.
- Any committed secret file → workflow fails.
- ESLint warnings → advisory only, does not fail CI.

---

## 3. Branch and Release Strategy

### Recommended branch model

```
feature/<name>   →  develop  →  main  →  Render production
hotfix/<name>    ↗
```

| Branch | Purpose | CI triggers |
|--------|---------|-------------|
| `main` | Production-ready code | Push + PR |
| `develop` | Integration branch | Push + PR |
| `feature/*` | Individual features | PR to `develop` |
| `hotfix/*` | Critical production fixes | PR to `main` (+ backport to `develop`) |
| `release/*` | Release stabilisation | Push + PR |

### Release flow

```
1. Developer creates feature branch from develop
         │
         ▼
2. Pull Request opened against develop
   → CI runs automatically
   → PR template checklist completed
         │
         ▼
3. CI must pass (344 tests + build + security checks)
         │
         ▼
4. Code review and approval
         │
         ▼
5. Merge to develop
         │
         ▼
6. When ready for release:
   create release/<version> branch from develop
   → Final CI validation
         │
         ▼
7. Merge release branch to main
   → Tag the release: git tag v1.x.x
         │
         ▼
8. Production deployment via Render
   (manual trigger or automatic depending on Render configuration)
         │
         ▼
9. Post-deployment health verification
```

> **Important:** Do not push directly to `main`. All changes must go through a pull request with CI passing.

---

## 4. Versioning

### Current versions

| Component | Version | Location |
|-----------|---------|---------|
| Backend API | `1.2.0` | `Backend/app.py` → `FastAPI(version="1.2.0")` |
| Frontend package | `0.0.0` | `Frontend/package.json` → `"version": "0.0.0"` |

### Versioning approach

The project uses **Git tags** as the primary release identifier. API version in `app.py` serves as the backend contract version.

When releasing a new version:

1. Update `Frontend/package.json` → `"version"` to match the release (e.g. `"1.3.0"`)
2. Update `Backend/app.py` → `FastAPI(version="1.3.0")` if the API surface changed
3. Commit the version bump
4. Tag the release: `git tag -a v1.3.0 -m "Release 1.3.0"`
5. Push the tag: `git push origin v1.3.0`

A release is uniquely identified by:

```
Version tag (e.g. v1.3.0)
+ Commit SHA
+ CI run result (pass/fail)
+ Deployment timestamp (visible in Render dashboard)
```

---

## 5. Release Checklist

Use this checklist for every production release.

### Before merging

- [ ] Feature branch is up to date with `develop` / `main`
- [ ] Pull request description completed (PR template)
- [ ] CI pipeline passes — all three jobs green
- [ ] All 344 regression tests pass locally (see commands below)
- [ ] Frontend build passes locally (`cd Frontend && npm run build`)
- [ ] Backend compile passes locally (`python -m py_compile Backend/app.py`)
- [ ] No secrets committed (`.env`, `credentials.json`, `token.json` not in diff)
- [ ] Database-impacting changes documented and coordinated
- [ ] `ALLOWED_ORIGINS` updated if frontend URL changed
- [ ] `docs/DEVELOPER_GUIDE.md` updated if behaviour changed
- [ ] Code reviewed and approved

### Before deploying to production

- [ ] Release branch / tag created: `git tag v<version>`
- [ ] Confirm Render environment variables are correct for this release
- [ ] Confirm `render.yaml` is unchanged (or explicitly reviewed if changed)
- [ ] Back up production database if the release affects schema or data
  → See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md)
- [ ] Deployment window identified (prefer off-peak hours)

### Deploying

- [ ] Trigger deployment via Render dashboard (or confirm auto-deploy on push to `main`)
- [ ] Monitor Render build logs for errors
- [ ] Wait for health check to pass (`GET /health` → `{"status": "healthy"}`)

### After deploying

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /docs` returns Swagger UI (200 OK)
- [ ] Login with a real staff account succeeds
- [ ] Manager portal loads and candidate list is accessible
- [ ] HR portal loads and offer approvals list is accessible
- [ ] Check Render logs for any unexpected errors
- [ ] Confirm structured log output is visible in Render log stream
- [ ] Record: version tag + commit SHA + deployment timestamp

---

## 6. Production Deployment

### Platform: Render

Both services deploy via Render using the Blueprint defined in `render.yaml`.

**Backend:**

```
Build:  pip install -r requirements.txt
Start:  uvicorn app:app --host 0.0.0.0 --port $PORT
Health: GET /docs
```

**Frontend:**

```
Build:  npm install && npm run build
Serve:  Static files from Frontend/dist/
Routes: /* → /index.html (SPA rewrite)
```

### Triggering a deployment

**Option A — Render auto-deploy (if connected to Git):**

When Render is connected to the Git repository and the watched branch (typically `main`) receives a push, Render automatically triggers a rebuild and deployment.

**Option B — Manual deploy via Render dashboard:**

1. Open [Render Dashboard](https://dashboard.render.com)
2. Select the service (`ai-recruitment-backend` or `ai-recruitment-frontend`)
3. Click **"Manual Deploy"** → **"Deploy latest commit"**

### Deployment order

Always deploy in this order:

1. **Backend first** — confirm health check passes
2. **Frontend second** — confirm it loads and connects to the backend

### Post-deployment verification

```bash
# Health check
curl https://ai-recruitment-backend.onrender.com/health
# Expected: {"status":"healthy"}

# API docs available
curl -I https://ai-recruitment-backend.onrender.com/docs
# Expected: HTTP/2 200
```

---

## 7. Rollback Strategy

### When to roll back

Roll back if, after deployment:

- Health check fails (`GET /health` does not return 200)
- Login is broken
- Critical API endpoints return unexpected errors
- Render logs show repeated unhandled exceptions
- External monitoring (Sentry if configured) reports a spike in errors

### Rollback procedure

```
1. Stop further changes
   └── Do not push additional commits until the issue is resolved

2. Identify the last known-good deploy
   └── Render Dashboard → Service → Deploys
       Find the most recent successful deploy before the problem

3. Redeploy the previous commit
   └── Render Dashboard → Service → Deploys
       Click "•••" on the known-good deploy → "Redeploy"

4. Verify health
   └── curl https://ai-recruitment-backend.onrender.com/health
       Expected: {"status":"healthy"}

5. Verify critical workflow
   └── Log in with a real staff account
       Confirm manager and HR portals load

6. Check monitoring
   └── Review Render log stream for errors
       Check Sentry if configured

7. Document the incident
   └── Record: what failed, when, which commit was reverted, when recovered
```

> **Note:** Database-level rollback is separate from application rollback. If a database migration was applied, rolling back the application code alone may not be sufficient. Coordinate with [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).

---

## 8. Database Migration Safety

The project currently uses Supabase with no migration files in the repository. Schema is managed directly in the Supabase dashboard.

### Rules for any future schema changes

- **Never run `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, or destructive DDL automatically** in CI or deployment pipelines.
- Always back up the database **before** applying a schema change. See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).
- Apply schema changes **before or simultaneously with** the application deployment — not after.
- Test schema changes against a non-production Supabase project first.
- Document every schema change in `docs/DEVELOPER_GUIDE.md` → Database section.

### Safe migration checklist

- [ ] Migration tested against a development/staging Supabase project
- [ ] Production database backed up (`python scripts/backup_db.py`)
- [ ] Application code is backward-compatible with both old and new schema (if possible)
- [ ] Migration applied via Supabase dashboard or SQL editor — not via automated CI
- [ ] Post-migration: verify affected API endpoints return correct data

---

## 9. Environment Separation

| Environment | Purpose | Database | External services |
|-------------|---------|----------|------------------|
| **CI** | Automated validation | Dummy placeholder values | Not connected |
| **Local development** | Developer testing | Developer's `.env` | Real or mocked |
| **Production** | Live application | Production Supabase | Real (Render env vars) |

### CI isolation guarantee

The CI workflow `env:` block sets `SUPABASE_URL=https://ci-test-placeholder.supabase.co` — a URL that does not resolve. All test suites are designed to handle database failures gracefully. No CI job connects to the real production Supabase instance.

### Never do this

```yaml
# ⛔ NEVER put real production credentials in ci.yml
SUPABASE_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI..."  # real key
GEMINI_API_KEY: "AIza..."                           # real key
```

If a test ever genuinely requires a real external service, use a **GitHub Actions encrypted secret** (`${{ secrets.SUPABASE_KEY }}`) and ensure the test operates in read-only mode with clearly scoped permissions.

---

## 10. Release Artifacts and Traceability

Every production release should be traceable via:

| Artifact | Where to find it |
|----------|-----------------|
| **Version tag** | `git tag -l` / GitHub Releases |
| **Commit SHA** | `git log --oneline -1` / Render deploy log |
| **CI run result** | GitHub Actions → Runs → `ci.yml` |
| **Deployment timestamp** | Render Dashboard → Service → Deploys |
| **Health check** | `GET /health` response timestamp in Render logs |

### Creating a release tag

```bash
# After merging to main
git checkout main
git pull origin main
git tag -a v1.3.0 -m "Release 1.3.0 — <brief description>"
git push origin v1.3.0
```

On GitHub: create a **Release** from the tag with:
- Tag: `v1.3.0`
- Title: `v1.3.0 — <brief description>`
- Body: summary of changes, linked PRs, known issues

---

## 11. Security Rules

These rules apply to every release and to CI configuration:

- **Never commit real secrets.** `.gitignore` already excludes `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key`. CI job 3 enforces this on every push.
- **Never put real API keys in `ci.yml`.** Use dummy test values (no external calls needed) or GitHub encrypted secrets.
- **Never allow CI to deploy production automatically** unless Render auto-deploy is explicitly configured and understood by the team.
- **Never run destructive SQL in automated pipelines** — no `DROP`, `TRUNCATE`, or `DELETE` without explicit approval and backup.
- **Review all `render.yaml` changes** carefully — a mistake here can break the production deployment blueprint.
- **Rotate secrets** if a secret was accidentally committed. Even if quickly removed from history, treat it as compromised.

---

## Local CI-Equivalent Validation

Run these commands locally before opening a pull request:

```bash
# 1. Backend syntax check
python -m py_compile Backend/app.py

# 2. All regression suites (from project root)
python scratch/test_task1_retries.py
python scratch/test_task2_password_reset.py
python scratch/test_task3_logout.py
python scratch/test_task4_config.py
python scratch/test_task5_audit.py
python scratch/test_task6_error_handling.py
python scratch/test_task7_backup_recovery.py
python scratch/test_task9_monitoring.py
python scratch/test_task10_accessibility.py

# 3. Frontend build
cd Frontend && npm install && npm run build

# 4. Security spot-check
# Confirm none of these exist in your working tree:
ls .env 2>/dev/null && echo "WARNING: .env present"
ls Backend/credentials.json 2>/dev/null && echo "WARNING: credentials.json present"
ls Backend/token.json 2>/dev/null && echo "WARNING: token.json present"
```

Expected baseline results:

| Suite | Tests | Expected |
|-------|-------|---------|
| Task 1 — API Retries | 13 | PASS |
| Task 2 — Password Reset | 13 | PASS |
| Task 3 — Session Security | 7 | PASS |
| Task 4 — Secrets Hygiene | 8 | PASS |
| Task 5 — Audit Trail | 59 | PASS |
| Task 6 — Error Handling | 143 | PASS |
| Task 7 — Backup & Recovery | 56 | PASS |
| Task 9 — Monitoring | 16 | PASS |
| Task 10 — Accessibility | 29 | PASS |
| Frontend build | — | PASS |
| Backend compile | — | PASS |
| **Total** | **344** | **100%** |

---

*For architecture and API details, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).*  
*For backup procedures, see [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).*  
*For monitoring, see [MONITORING_AND_SUPPORT.md](MONITORING_AND_SUPPORT.md).*
