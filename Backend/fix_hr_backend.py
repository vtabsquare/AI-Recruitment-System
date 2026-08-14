from pathlib import Path
import re

APP = Path(__file__).resolve().parent / "app.py"
if not APP.exists():
    raise SystemExit(f"Could not find {APP}. Put this file inside your Backend folder and run it there.")

text = APP.read_text(encoding="utf-8")
backup = APP.with_suffix(".py.backup_before_hr_fix")
backup.write_text(text, encoding="utf-8")

if "def require_hr(" not in text:
    anchors = [
        '''def require_staff_portal(staff=Depends(get_current_staff)):\n    return staff\n''',
        '''def require_staff(staff=Depends(get_current_staff)):\n    return staff\n''',
    ]
    for anchor in anchors:
        if anchor in text:
            addition = '''\n\ndef require_hr(staff=Depends(get_current_staff)):\n    role = str(staff.get("role", "")).lower()\n    if role not in {"hr", "admin"}:\n        raise HTTPException(status_code=403, detail="HR/Admin access required.")\n    return staff\n'''
            text = text.replace(anchor, anchor + addition, 1)
            break
    else:
        raise SystemExit("Could not find the staff dependency section. Backup was created; no changes were saved.")

text = re.sub(
    r'(@app\.get\("/api/hr/employees"\)\s*\ndef hr_employees\(staff=Depends\()([A-Za-z_][A-Za-z0-9_]*)(\)\):)',
    r'\1require_hr\3', text, count=1)
text = re.sub(
    r'(@app\.get\("/api/hr/audit-logs"\)\s*\ndef hr_audit_logs\(staff=Depends\()([A-Za-z_][A-Za-z0-9_]*)(\)\):)',
    r'\1require_hr\3', text, count=1)

if '"/api/hr/offer-approvals"' not in text:
    endpoint = '''\n\n@app.get("/api/hr/offer-approvals")\ndef hr_offer_approvals(staff=Depends(require_hr)):\n    """Return applications that have reached the HR offer stage."""\n    try:\n        applications = select_all("applications", order_column="updated_at")\n        candidates = select_all("candidates")\n        roles = select_all("job_roles")\n\n        candidate_map = {item.get("id"): item for item in candidates}\n        role_map = {item.get("id"): item for item in roles}\n        application_ids = [item.get("id") for item in applications if item.get("id")]\n        evaluation_map = get_evaluations_for_applications(application_ids)\n\n        hr_statuses = {"approved", "selected", "manager_approved"}\n        items = []\n\n        for application in applications:\n            status = str(application.get("status", "")).lower()\n            if status not in hr_statuses:\n                continue\n\n            candidate = candidate_map.get(application.get("candidate_id"), {})\n            role = role_map.get(application.get("job_role_id"), {})\n            evaluation = evaluation_map.get(application.get("id"))\n\n            items.append(\n                enrich_application(application, candidate, role, evaluation)\n            )\n\n        return {\n            "success": True,\n            "count": len(items),\n            "items": items,\n            "requested_by": staff.get("role"),\n        }\n    except Exception as error:\n        raise HTTPException(status_code=500, detail=str(error))\n'''
    markers = [
        "# ------------------------- HR -------------------------",
        "# ============================================================\n# HR EMPLOYEES / AUDIT LOGS",
    ]
    for marker in markers:
        if marker in text:
            text = text.replace(marker, endpoint + "\n\n" + marker, 1)
            break
    else:
        raise SystemExit("Could not find the HR section. Backup was created; no changes were saved.")

APP.write_text(text, encoding="utf-8")
print("HR backend patch applied successfully.")
print(f"Backup: {backup}")
print("Restart FastAPI: python -m uvicorn app:app --reload --port 8000")