import json

from supabase_db import supabase
from email_service import send_email


# ============================================================
# INTERVIEW DECISION EMAIL SERVICE
# ============================================================
#
# This service is used AFTER:
#
# Interviewer feedback
#       ↓
# Gemini interview evaluation
#       ↓
# selected / rejected / next_round
#
# It does NOT perform the AI evaluation.
# It only sends the appropriate final candidate email.
# ============================================================


# ============================================================
# GET APPLICATION DETAILS
# ============================================================

def get_application_details(application_id):
    """
    Get the application, candidate, and job-role information
    needed for the final interview decision email.
    """

    if not application_id:
        raise ValueError(
            "Application ID is required."
        )

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    application_response = (
        supabase
        .table("applications")
        .select(
            "id, application_id, candidate_id, job_role_id, status"
        )
        .eq(
            "id",
            application_id
        )
        .limit(1)
        .execute()
    )

    if not application_response.data:
        raise ValueError(
            f"No application was found for {application_id}."
        )

    application = application_response.data[0]

    # --------------------------------------------------------
    # Candidate
    # --------------------------------------------------------

    candidate_response = (
        supabase
        .table("candidates")
        .select(
            "id, candidate_name, email"
        )
        .eq(
            "id",
            application["candidate_id"]
        )
        .limit(1)
        .execute()
    )

    if not candidate_response.data:
        raise ValueError(
            "No candidate was found for the application."
        )

    candidate = candidate_response.data[0]

    # --------------------------------------------------------
    # Job role
    # --------------------------------------------------------

    role_name = "the position"

    if application.get("job_role_id"):

        role_response = (
            supabase
            .table("job_roles")
            .select("*")
            .eq(
                "id",
                application["job_role_id"]
            )
            .limit(1)
            .execute()
        )

        if role_response.data:

            role = role_response.data[0]

            role_name = str(
                role.get(
                    "role_name",
                    role.get(
                        "name",
                        "the position"
                    )
                )
            ).strip()

    return {
        "application": application,
        "candidate": candidate,
        "role_name": role_name
    }


# ============================================================
# SEND SELECTION EMAIL
# ============================================================

def send_selection_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id
):
    """
    Send the professional final selection email.
    """

    subject = (
        "VTAB Square | Interview Outcome"
    )

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Outcome</title>
</head>

<body style="
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #222222;
">

<p>Dear {candidate_name},</p>

<p>
Thank you for taking the time to interview with
<strong>VTAB Square</strong>.
</p>

<p>
We are pleased to inform you that you have been
<strong>selected</strong> following the interview process
for the <strong>{job_role}</strong> position.
</p>

<p>
Our recruitment team will contact you with the next steps
and any documentation required to proceed with the
onboarding process.
</p>

<p>
We appreciate your time and interest in joining VTAB Square.
</p>

<p>
Regards,<br>
<strong>VTAB Square Recruitment Team</strong>
</p>

<p style="font-size: 12px; color: #777777;">
Application ID: {application_id}
</p>

</body>
</html>
"""

    text_content = f"""
Dear {candidate_name},

Thank you for taking the time to interview with VTAB Square.

We are pleased to inform you that you have been selected
following the interview process for the {job_role} position.

Our recruitment team will contact you with the next steps
and any documentation required to proceed with the
onboarding process.

We appreciate your time and interest in joining VTAB Square.

Regards,
VTAB Square Recruitment Team

Application ID: {application_id}
""".strip()

    return send_email(
        recipient_email=recipient_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )


# ============================================================
# SEND REJECTION EMAIL
# ============================================================

def send_interview_rejection_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id
):
    """
    Send the professional final rejection email.

    Do not expose internal AI scores or evaluation reasoning
    to the candidate.
    """

    subject = (
        "VTAB Square | Interview Outcome"
    )

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Outcome</title>
</head>

<body style="
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #222222;
">

<p>Dear {candidate_name},</p>

<p>
Thank you for taking the time to interview with
<strong>VTAB Square</strong> and for your interest in the
<strong>{job_role}</strong> position.
</p>

<p>
After careful consideration of the interview feedback,
we regret to inform you that we will not be moving forward
with your application at this time.
</p>

<p>
We sincerely appreciate the time and effort you invested
in the interview process and wish you every success in
your future career.
</p>

<p>
Regards,<br>
<strong>VTAB Square Recruitment Team</strong>
</p>

<p style="font-size: 12px; color: #777777;">
Application ID: {application_id}
</p>

</body>
</html>
"""

    text_content = f"""
Dear {candidate_name},

Thank you for taking the time to interview with VTAB Square
and for your interest in the {job_role} position.

After careful consideration of the interview feedback,
we regret to inform you that we will not be moving forward
with your application at this time.

We sincerely appreciate the time and effort you invested
in the interview process and wish you every success in
your future career.

Regards,
VTAB Square Recruitment Team

Application ID: {application_id}
""".strip()

    return send_email(
        recipient_email=recipient_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )


# ============================================================
# SEND FINAL INTERVIEW DECISION EMAIL
# ============================================================

def send_final_interview_decision_email(
    application_id,
    final_decision
):
    """
    Send the appropriate candidate email based on the
    already-completed AI interview evaluation.

    Supported decisions:

        selected
        rejected
        next_round

    next_round does NOT send a final candidate email.
    """

    decision = str(
        final_decision or ""
    ).strip().lower()

    if decision not in {
        "selected",
        "rejected",
        "next_round"
    }:
        raise ValueError(
            "Final decision must be selected, rejected, "
            "or next_round."
        )

    # --------------------------------------------------------
    # NEXT ROUND
    # --------------------------------------------------------

    if decision == "next_round":

        print()
        print(
            "NEXT ROUND: No final candidate email sent."
        )

        return {
            "decision": "next_round",
            "sent": False,
            "reason": (
                "Candidate requires another review/round."
            )
        }

    # --------------------------------------------------------
    # Get candidate/application details
    # --------------------------------------------------------

    details = get_application_details(
        application_id
    )

    candidate = details["candidate"]

    candidate_name = str(
        candidate.get(
            "candidate_name",
            "Candidate"
        )
    ).strip()

    candidate_email = str(
        candidate.get(
            "email",
            ""
        )
    ).strip().lower()

    role_name = details["role_name"]

    application = details["application"]

    public_application_id = str(
        application.get(
            "application_id",
            application_id
        )
    )

    if not candidate_email:

        raise ValueError(
            "Candidate email is missing."
        )

    # --------------------------------------------------------
    # SELECTED
    # --------------------------------------------------------

    if decision == "selected":

        print()
        print(
            "Sending final selection email..."
        )

        response = send_selection_email(
            candidate_name=candidate_name,
            recipient_email=candidate_email,
            job_role=role_name,
            application_id=public_application_id
        )

        print(
            "Selection email sent successfully."
        )

        return {
            "decision": "selected",
            "sent": True,
            "recipient": candidate_email,
            "response": response
        }

    # --------------------------------------------------------
    # REJECTED
    # --------------------------------------------------------

    print()
    print(
        "Sending final rejection email..."
    )

    response = send_interview_rejection_email(
        candidate_name=candidate_name,
        recipient_email=candidate_email,
        job_role=role_name,
        application_id=public_application_id
    )

    print(
        "Rejection email sent successfully."
    )

    return {
        "decision": "rejected",
        "sent": True,
        "recipient": candidate_email,
        "response": response
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(
        "VTAB SQUARE FINAL INTERVIEW EMAIL TEST"
    )
    print("=" * 60)

    application_id = input(
        "\nEnter application UUID: "
    ).strip()

    decision = input(
        "Enter decision (selected/rejected/next_round): "
    ).strip().lower()

    result = send_final_interview_decision_email(
        application_id=application_id,
        final_decision=decision
    )

    print()
    print("=" * 60)
    print("FINAL EMAIL RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=4
        )
    )