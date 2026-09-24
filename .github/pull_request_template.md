# AI Recruitment System — Pull Request

## Summary

<!-- Describe what this change does and why. -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] CI/release process change
- [ ] Dependency update
- [ ] Refactor (no behaviour change)

---

## Pre-Merge Checklist

### Code

- [ ] Change is minimal and focused on a single concern
- [ ] No unrelated logic was modified
- [ ] Existing API contracts, routes, and response shapes are preserved
- [ ] Existing authentication / authorization behaviour is preserved
- [ ] No secrets, API keys, tokens, or credentials are committed

### Testing

- [ ] All existing regression suites pass locally (see commands below)
- [ ] Frontend production build passes (`npm run build`)
- [ ] Backend syntax check passes (`python -m py_compile Backend/app.py`)
- [ ] CI workflow passes on this PR

### Database

- [ ] No unintended schema changes
- [ ] Any required migrations are documented and coordinated with deployment

### Documentation

- [ ] `docs/DEVELOPER_GUIDE.md` updated if behaviour changed
- [ ] `docs/RELEASE_MANAGEMENT.md` updated if release process changed

---

## Local Regression Commands

```bash
# Backend compile
python -m py_compile Backend/app.py

# Regression suites
python scratch/test_task1_retries.py
python scratch/test_task2_password_reset.py
python scratch/test_task3_logout.py
python scratch/test_task4_config.py
python scratch/test_task5_audit.py
python scratch/test_task6_error_handling.py
python scratch/test_task7_backup_recovery.py
python scratch/test_task9_monitoring.py
python scratch/test_task10_accessibility.py

# Frontend build
cd Frontend && npm run build
```

---

## Affected Components

- [ ] Backend (`Backend/app.py`, services, config)
- [ ] Frontend (`Frontend/src/App.jsx`, styles)
- [ ] Database schema
- [ ] External integrations (Gemini / Brevo / Google APIs / Supabase)
- [ ] CI / release process
- [ ] Documentation only

---

## Reviewer Notes

<!-- Anything the reviewer should pay particular attention to. -->
