import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from resume_reader import extract_resume_text
from ai_analyzer import analyze_resume

from supabase_db import (
    get_job_role,
    create_candidate,
    create_application,
    get_existing_application,
    supabase
)

from resume_service import (
    save_resume,
    save_resume_analysis
)

from evaluation_service import evaluate_candidate

from email_service import (
    send_shortlisted_email,
    send_rejection_email
)


# ============================================================
# UPDATE APPLICATION STATUS
# ============================================================

def update_application_status(application_id, status):
    """
    Update the current status of an application.
    """

    response = (
        supabase
        .table("applications")
        .update({
            "status": status
        })
        .eq("id", application_id)
        .execute()
    )

    if not response.data:
        raise Exception(
            f"Failed to update application status to '{status}'."
        )

    return response.data[0]


# ============================================================
# FIND OR CREATE CANDIDATE
# ============================================================

def get_or_create_candidate(
    candidate_name,
    email,
    phone_number
):
    """
    Find a candidate by email.

    If the candidate exists, update their information.
    Otherwise, create a new candidate.
    """

    if not email:
        raise ValueError(
            "Candidate email is required to create an application."
        )

    existing_response = (
        supabase
        .table("candidates")
        .select(
            "id, candidate_name, email, phone_number"
        )
        .eq("email", email)
        .limit(1)
        .execute()
    )

    existing_candidates = (
        existing_response.data or []
    )

    candidate_data = {
        "candidate_name": candidate_name,
        "email": email,
        "phone_number": phone_number
    }

    # --------------------------------------------------------
    # Existing candidate
    # --------------------------------------------------------

    if existing_candidates:

        candidate_id = existing_candidates[0]["id"]

        response = (
            supabase
            .table("candidates")
            .update(candidate_data)
            .eq("id", candidate_id)
            .execute()
        )

    # --------------------------------------------------------
    # New candidate
    # --------------------------------------------------------

    else:

        response = (
            supabase
            .table("candidates")
            .insert(candidate_data)
            .execute()
        )

    if not response.data:
        raise Exception(
            "Failed to create or update candidate."
        )

    return response.data[0]


# ============================================================
# SEND RECRUITMENT EMAIL
# ============================================================

def send_recruitment_email(
    candidate,
    application,
    role,
    evaluation
):
    """
    Send the appropriate recruitment email based on
    the AI evaluation decision.

    Shortlisted -> shortlisted email
    Rejected    -> rejection email
    """

    candidate_name = candidate.get(
        "candidate_name",
        "Candidate"
    )

    candidate_email = candidate.get(
        "email",
        ""
    )

    application_id = application.get(
        "application_id",
        application.get("id", "")
    )

    role_name = role.get(
        "role_name",
        "the position"
    )

    decision = str(
        evaluation.get("decision", "")
    ).strip().lower()

    print("\nEmail notification:")

    # --------------------------------------------------------
    # SHORTLISTED
    # --------------------------------------------------------

    if decision == "shortlisted":

        print(
            "Candidate shortlisted."
        )

        print(
            f"Sending shortlisted email to: "
            f"{candidate_email}"
        )

        email_response = send_shortlisted_email(

            candidate_name=candidate_name,

            recipient_email=candidate_email,

            job_role=role_name,

            application_id=application_id
        )

        print(
            "Shortlisted email sent successfully."
        )

        return {
            "type": "shortlisted",
            "sent": True,
            "response": email_response
        }

    # --------------------------------------------------------
    # REJECTED
    # --------------------------------------------------------

    if decision == "rejected":

        print(
            "Candidate rejected."
        )

        print(
            f"Sending rejection email to: "
            f"{candidate_email}"
        )

        email_response = send_rejection_email(

            candidate_name=candidate_name,

            recipient_email=candidate_email,

            job_role=role_name,

            application_id=application_id
        )

        print(
            "Rejection email sent successfully."
        )

        return {
            "type": "rejected",
            "sent": True,
            "response": email_response
        }

    # --------------------------------------------------------
    # UNKNOWN DECISION
    # --------------------------------------------------------

    raise ValueError(
        f"Unsupported AI evaluation decision: "
        f"{evaluation.get('decision')}"
    )


# ============================================================
# MAIN RECRUITMENT PIPELINE
# ============================================================

def process_candidate(
    resume_file_path,
    role_name,
    candidate_email=None,
    candidate_name=None
):
    """
    Run the complete AI recruitment screening pipeline.

    Flow:

    Resume
        ↓
    Gemini analysis
        ↓
    Candidate
        ↓
    Application
        ↓
    Resume storage
        ↓
    Resume analysis
        ↓
    AI evaluation
        ↓
    Application status
        ↓
    Recruitment email
    """

    print("=" * 60)
    print("VTAB AI RECRUITMENT PIPELINE")
    print("=" * 60)

    # ========================================================
    # 1. READ RESUME
    # ========================================================

    print("\n[1/8] Reading resume...")

    resume_text = extract_resume_text(
        resume_file_path
    )

    if not resume_text.strip():

        raise ValueError(
            "Resume contains no readable text."
        )

    print(
        "Resume extracted successfully."
    )

    # ========================================================
    # 2. ANALYZE RESUME WITH GEMINI
    # ========================================================

    print(
        "\n[2/8] Analyzing resume with Gemini..."
    )

    analysis = analyze_resume(
        resume_text,
        candidate_email=candidate_email
    )

    print(
        "Gemini analysis completed."
    )

    extracted_name = str(
        analysis.get(
            "candidate_name",
            ""
        )
    ).strip()

    if not candidate_name or candidate_name.lower() in ("", "candidate"):
        candidate_name = extracted_name or candidate_name or "Candidate"
    elif extracted_name and extracted_name.lower() != "candidate":
        candidate_name = extracted_name

    candidate_email = str(
        candidate_email or analysis.get("email", "")
    ).strip().lower()

    phone_number = str(
        analysis.get(
            "phone_number",
            ""
        )
    ).strip()

    if not candidate_name:

        raise ValueError(
            "Gemini could not identify the candidate name."
        )

    if not candidate_email:

        raise ValueError(
            "Gemini could not identify the candidate email."
        )

    print(
        f"Candidate email: {candidate_email}"
    )

    # ========================================================
    # 3. FIND OR CREATE CANDIDATE
    # ========================================================

    print(
        "\n[3/8] Creating/updating candidate..."
    )

    candidate = get_or_create_candidate(

        candidate_name,

        candidate_email,

        phone_number
    )

    print("Candidate:")
    print(candidate)

    # ========================================================
    # 4. GET JOB ROLE
    # ========================================================

    print(
        "\n[4/8] Getting job role requirements..."
    )

    role = get_job_role(
        role_name
    )

    if not role:

        raise ValueError(
            f"Job role '{role_name}' was not found."
        )

    print("Role:")
    print(role)

    # ========================================================
    # 5. CREATE OR GET APPLICATION
    # ========================================================

    print(
        "\n[5/8] Checking existing applications..."
    )

    existing_app = get_existing_application(
        candidate["id"],
        role["id"]
    )

    if existing_app:
        print("Candidate already has an application for this role. Skipping evaluation.")
        return {
            "skipped": True,
            "reason": "Duplicate application",
            "candidate": candidate,
            "application": existing_app
        }

    print("Creating new application...")

    application = create_application(

        candidate["id"],

        role["id"]
    )

    application_id = application["id"]

    print("Application:")
    print(application)

    # ========================================================
    # 6. SAVE RESUME AND ANALYSIS
    # ========================================================

    print(
        "\n[6/8] Saving resume and analysis..."
    )

    resume_record = save_resume(

        application_id=application_id,

        file_name=resume_file_path.split("\\")[-1],

        extracted_text=resume_text
    )

    print(
        "Resume saved."
    )

    analysis_record = save_resume_analysis(

        application_id=application_id,

        analysis=analysis
    )

    print(
        "Resume analysis saved."
    )

    # ========================================================
    # 7. EVALUATE CANDIDATE
    # ========================================================

    print(
        "\n[7/8] Evaluating candidate..."
    )

    evaluation = evaluate_candidate(

        application_id,

        analysis,

        role
    )

    print(
        "AI Evaluation:"
    )

    print(
        evaluation
    )

    # ========================================================
    # UPDATE APPLICATION STATUS
    # ========================================================

    final_status = str(
        evaluation.get(
            "decision",
            ""
        )
    ).strip().lower()

    if not final_status:

        raise ValueError(
            "AI evaluation did not return a decision."
        )

    application_status = (
        update_application_status(

            application_id,

            final_status
        )
    )

    print(
        "\nApplication status updated:"
    )

    print(
        application_status
    )

    # ========================================================
    # 8. SEND EMAIL
    # ========================================================

    print(
        "\n[8/8] Sending recruitment email..."
    )

    email_notification = send_recruitment_email(

        candidate=candidate,

        application=application_status,

        role=role,

        evaluation=evaluation
    )

    print(
        "Email notification completed."
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {

        "candidate": candidate,

        "application": application_status,

        "resume": resume_record,

        "resume_analysis": analysis_record,

        "ai_evaluation": evaluation,

        "email_notification": email_notification
    }

    print(
        "\n" + "=" * 60
    )

    print(
        "RECRUITMENT PIPELINE COMPLETED"
    )

    print(
        "=" * 60
    )

    return result