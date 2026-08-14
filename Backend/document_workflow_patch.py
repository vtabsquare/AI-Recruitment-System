from pathlib import Path
import shutil
import re

APP = Path(__file__).resolve().parent / "app.py"
if not APP.exists():
    raise SystemExit(f"ERROR: {APP} not found.")

text = APP.read_text(encoding="utf-8")
backup = APP.with_name("app.py.backup_before_document_workflow")
shutil.copy2(APP, backup)

# Required imports.
if "UploadFile" not in text:
    text = text.replace(
        "from fastapi import Depends, FastAPI, HTTPException",
        "from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form",
        1,
    )
if "import uuid" not in text:
    text = text.replace("import os", "import os\nimport uuid\nimport hashlib\nimport secrets", 1)
if "from datetime import datetime, timezone" not in text:
    text = text.replace("import os", "import os\nfrom datetime import datetime, timezone", 1)
if "from email_service import send_email" not in text:
    marker = "from interview_decision_email_service import send_final_interview_decision_email"
    if marker in text:
        text = text.replace(marker, marker + "\nfrom email_service import send_email", 1)

helper = r'''# ------------------------- DOCUMENT REQUEST EMAIL -------------------------

def send_document_request_email(candidate_name, recipient_email, job_role, application_id, token):
    candidate_name = str(candidate_name or "Candidate").strip()
    recipient_email = str(recipient_email or "").strip()
    job_role = str(job_role or "the position").strip()
    application_id = str(application_id or "").strip()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    upload_url = f"{frontend_url}/documents?token={token}"

    return send_email(
        recipient_email=recipient_email,
        recipient_name=candidate_name,
        subject="VTAB Square | Document Submission Required",
        html_content=f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;">
        <h2>Document Submission Required</h2>
        <p>Dear {candidate_name},</p>
        <p>Congratulations. You have successfully completed the interview stage
        for the <strong>{job_role}</strong> position at VTAB Square.</p>
        <p>Please use the secure link below to submit your requested documents.</p>
        <p><a href="{upload_url}" style="display:inline-block;padding:12px 18px;
        background:#6d5ce7;color:white;text-decoration:none;border-radius:8px;">
        Submit Documents</a></p>
        <p><strong>Application ID:</strong> {application_id}</p>
        <p>This secure link expires in 7 days.</p>
        <p>Regards,<br>VTAB Square HR Team</p>
        </body></html>
        """,
        text_content=f"""
Dear {candidate_name},

Congratulations. You have successfully completed the interview stage
for the {job_role} position at VTAB Square.

Submit your required documents here:
{upload_url}

Application ID: {application_id}

This secure link expires in 7 days.

Regards,
VTAB Square HR Team
""".strip(),
    )
'''

if "def send_document_request_email(" not in text:
    marker = "# ------------------------- CANDIDATE AI -------------------------"
    if marker in text:
        text = text.replace(marker, helper + "\n\n" + marker, 1)
    else:
        text += "\n\n" + helper

endpoints = r'''# ------------------------- DOCUMENT WORKFLOW -------------------------

DOCUMENT_BUCKET = "candidate-documents"
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def _hash_document_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@app.get("/api/document-request")
def get_document_request(token: str):
    try:
        response = (
            supabase.table("document_requests")
            .select("id,candidate_id,application_id,status,expires_at")
            .eq("token_hash", _hash_document_token(token.strip()))
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Invalid document submission link.")

        request = response.data[0]
        if request.get("status") != "pending":
            raise HTTPException(status_code=400, detail="This submission link is no longer active.")

        candidate = select_one("candidates", request.get("candidate_id"))
        requirements = (
            supabase.table("document_requirements")
            .select("id,document_name,description,is_required")
            .eq("is_active", True)
            .order("document_name")
            .execute()
        )
        return {
            "success": True,
            "candidate": {
                "id": candidate.get("id") if candidate else None,
                "name": candidate.get("candidate_name") if candidate else None,
                "email": candidate.get("email") if candidate else None,
            },
            "requirements": requirements.data or [],
            "request": request,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/document-upload")
async def public_document_upload(
    token: str = Form(...),
    document_name: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        response = (
            supabase.table("document_requests")
            .select("*")
            .eq("token_hash", _hash_document_token(token.strip()))
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Invalid document submission link.")

        request = response.data[0]
        if request.get("status") != "pending":
            raise HTTPException(status_code=400, detail="This submission link is no longer active.")

        filename = file.filename or "document"
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only PDF, PNG, JPG, and JPEG files are allowed.")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="The uploaded document is empty.")
        if len(content) > MAX_DOCUMENT_SIZE:
            raise HTTPException(status_code=400, detail="Maximum document size is 10 MB.")

        document_id = str(uuid.uuid4())
        safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
        storage_path = f"{request['candidate_id']}/{document_id}_{safe_filename}"

        supabase.storage.from_(DOCUMENT_BUCKET).upload(
            storage_path,
            content,
            file_options={
                "content-type": file.content_type or "application/octet-stream",
                "upsert": "false",
            },
        )

        req = (
            supabase.table("document_requirements")
            .select("id")
            .eq("document_name", document_name.strip())
            .limit(1)
            .execute()
        )
        requirement_id = req.data[0]["id"] if req.data else None

        saved = (
            supabase.table("documents")
            .insert({
                "id": document_id,
                "candidate_id": request["candidate_id"],
                "application_id": request["application_id"],
                "requirement_id": requirement_id,
                "document_name": document_name.strip(),
                "storage_path": storage_path,
                "verification_status": "uploaded",
            })
            .execute()
        )
        if not saved.data:
            raise ValueError("Document record could not be created.")

        supabase.table("applications").update(
            {"status": "documents_verifying"}
        ).eq("id", request["application_id"]).execute()

        return {"success": True, "message": "Document uploaded successfully.", "document": saved.data[0]}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/api/hr/document-verification")
def hr_document_verification(staff=Depends(require_hr)):
    try:
        response = (
            supabase.table("documents")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return {"success": True, "count": len(response.data or []), "items": response.data or []}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/documents/{document_id}/verify")
def hr_verify_document(document_id: str, staff=Depends(require_hr)):
    try:
        existing = (
            supabase.table("documents").select("*")
            .eq("id", document_id).limit(1).execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Document not found.")

        updated = (
            supabase.table("documents")
            .update({
                "verification_status": "hr_review_required",
                "verification_result": {
                    "status": "hr_review_required",
                    "verified_by_ai": False,
                    "message": "Document is ready for HR review.",
                },
            })
            .eq("id", document_id)
            .execute()
        )
        return {"success": True, "document": updated.data[0] if updated.data else None}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/documents/{document_id}/approve")
def hr_approve_document(document_id: str, staff=Depends(require_hr)):
    try:
        existing = (
            supabase.table("documents").select("*")
            .eq("id", document_id).limit(1).execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Document not found.")

        updated = (
            supabase.table("documents")
            .update({
                "verification_status": "approved",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", document_id)
            .execute()
        )
        return {"success": True, "document": updated.data[0] if updated.data else None}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
'''

if "def public_document_upload(" not in text:
    marker = "# ------------------------- RUN DIRECTLY -------------------------"
    if marker in text:
        text = text.replace(marker, endpoints + "\n\n" + marker, 1)
    else:
        text += "\n\n" + endpoints

# Automatic document-request email after the already-working selected decision.
if "DOCUMENT_REQUEST_SENT" not in text:
    needle = '''        email_result = send_final_interview_decision_email(
            application_id=feedback.application_id,
            final_decision=final_decision,
        )'''
    hook = '''        email_result = send_final_interview_decision_email(
            application_id=feedback.application_id,
            final_decision=final_decision,
        )

        document_email_result = None
        if decision == "selected":
            application_row = (
                supabase.table("applications").select("*")
                .eq("id", feedback.application_id).limit(1).execute()
            )
            application_data = application_row.data[0] if application_row.data else {}
            candidate_data = select_one("candidates", application_data.get("candidate_id", "")) or {}
            role_data = select_one("job_roles", application_data.get("job_role_id", "")) or {}

            raw_token = secrets.token_urlsafe(32)
            supabase.table("document_requests").insert({
                "candidate_id": application_data.get("candidate_id"),
                "application_id": feedback.application_id,
                "token_hash": _hash_document_token(raw_token),
            }).execute()

            document_email_result = send_document_request_email(
                candidate_name=candidate_data.get("candidate_name"),
                recipient_email=candidate_data.get("email"),
                job_role=role_data.get("role_name"),
                application_id=application_data.get("application_id"),
                token=raw_token,
            )
            print("DOCUMENT_REQUEST_SENT")'''
    if needle in text:
        text = text.replace(needle, hook, 1)
    else:
        print("WARNING: final decision email call not found; automatic request email was not hooked.")

APP.write_text(text, encoding="utf-8")
print("DOCUMENT WORKFLOW PATCH APPLIED SUCCESSFULLY")
print(f"Updated: {APP}")
print(f"Backup:  {backup}")