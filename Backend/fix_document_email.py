from pathlib import Path
import shutil

APP = Path(__file__).resolve().parent / "app.py"

if not APP.exists():
    raise SystemExit(f"ERROR: {APP} not found.")

text = APP.read_text(encoding="utf-8")

# ---------------------------------------------------------
# BACKUP
# ---------------------------------------------------------

backup = APP.with_name("app.py.backup_before_document_email_fix")
shutil.copy2(APP, backup)

print("Backup created:")
print(backup)


# ---------------------------------------------------------
# REQUIRED IMPORT
# ---------------------------------------------------------

if "from email_service import send_email" not in text:

    marker = "from interview_decision_email_service import send_final_interview_decision_email"

    if marker in text:
        text = text.replace(
            marker,
            marker + "\nfrom email_service import send_email",
            1
        )

    else:
        # Fallback: add after supabase import
        marker = "from supabase_db import supabase"

        if marker in text:
            text = text.replace(
                marker,
                marker + "\nfrom email_service import send_email",
                1
            )

        else:
            raise SystemExit(
                "ERROR: Could not find a suitable import location."
            )


# ---------------------------------------------------------
# DOCUMENT EMAIL FUNCTION
# ---------------------------------------------------------

document_email_function = r'''

# ------------------------- DOCUMENT REQUEST EMAIL -------------------------

def send_document_request_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id,
    token
):
    """
    Send the secure document submission request
    after a candidate is selected.
    """

    candidate_name = str(
        candidate_name or "Candidate"
    ).strip()

    recipient_email = str(
        recipient_email or ""
    ).strip()

    job_role = str(
        job_role or "the position"
    ).strip()

    application_id = str(
        application_id or ""
    ).strip()

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173"
    ).rstrip("/")

    upload_url = (
        f"{frontend_url}/documents?token={token}"
    )

    return send_email(
        recipient_email=recipient_email,
        recipient_name=candidate_name,

        subject="VTAB Square | Document Submission Required",

        html_content=f"""
<html>
<body
    style="
        font-family:Arial,sans-serif;
        line-height:1.6;
    "
>

<h2>Document Submission Required</h2>

<p>
Dear {candidate_name},
</p>

<p>
Congratulations. You have successfully completed
the interview stage for the
<strong>{job_role}</strong> position at VTAB Square.
</p>

<p>
Please use the secure link below to submit
your required documents.
</p>

<p>
<a
    href="{upload_url}"
    style="
        display:inline-block;
        padding:12px 18px;
        background:#6d5ce7;
        color:white;
        text-decoration:none;
        border-radius:8px;
    "
>
Submit Documents
</a>
</p>

<p>
<strong>Application ID:</strong>
{application_id}
</p>

<p>
This secure link expires in 7 days.
</p>

<p>
Regards,<br>
VTAB Square HR Team
</p>

</body>
</html>
""",

        text_content=f"""
Dear {candidate_name},

Congratulations. You have successfully completed
the interview stage for the {job_role} position
at VTAB Square.

Please submit your required documents here:

{upload_url}

Application ID: {application_id}

This secure link expires in 7 days.

Regards,
VTAB Square HR Team
""".strip()
    )

'''

# Only add the function if it does not already exist.
if "def send_document_request_email(" not in text:

    # Put it before the document workflow section.
    marker = "# ------------------------- DOCUMENT WORKFLOW -------------------------"

    if marker in text:

        text = text.replace(
            marker,
            document_email_function + "\n" + marker,
            1
        )

    else:

        # Safe fallback: append to the file.
        text += "\n" + document_email_function

else:
    print("Document email function already exists.")


# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

APP.write_text(
    text,
    encoding="utf-8"
)

print()
print("=" * 60)
print("DOCUMENT EMAIL FUNCTION FIXED")
print("=" * 60)
print()
print(f"Updated: {APP}")
print(f"Backup:  {backup}")
print()
print("The following function now exists:")
print("send_document_request_email()")
print()
print("Next:")
print("python -m uvicorn app:app --reload --port 8000")