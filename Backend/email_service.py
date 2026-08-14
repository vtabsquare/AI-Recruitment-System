import os
import re
import requests


# ============================================================
# BREVO CONFIGURATION
# ============================================================

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

BREVO_API_KEY = os.getenv(
    "BREVO_API_KEY",
    ""
).strip()

BREVO_SENDER_EMAIL = os.getenv(
    "BREVO_SENDER_EMAIL",
    ""
).strip()

BREVO_SENDER_NAME = os.getenv(
    "BREVO_SENDER_NAME",
    "VTAB Square Recruitment"
).strip()


# ============================================================
# VALIDATION
# ============================================================

def _validate_email(email):

    if not email:
        return False

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            str(email).strip()
        )
    )


def _validate_configuration():

    missing = []

    if not BREVO_API_KEY:
        missing.append(
            "BREVO_API_KEY"
        )

    if not BREVO_SENDER_EMAIL:
        missing.append(
            "BREVO_SENDER_EMAIL"
        )

    if missing:

        raise RuntimeError(
            "Missing Brevo configuration: "
            + ", ".join(missing)
            + ". Set these as environment variables."
        )

    if not _validate_email(
        BREVO_SENDER_EMAIL
    ):

        raise ValueError(
            f"Invalid BREVO_SENDER_EMAIL: "
            f"{BREVO_SENDER_EMAIL}"
        )


# ============================================================
# CORE BREVO SEND FUNCTION
# ============================================================

def send_email(
    recipient_email,
    recipient_name,
    subject,
    html_content,
    text_content=None
):

    _validate_configuration()

    if not _validate_email(
        recipient_email
    ):

        raise ValueError(
            f"Invalid recipient email: "
            f"{recipient_email}"
        )

    recipient_email = (
        str(recipient_email)
        .strip()
        .lower()
    )

    recipient_name = (
        str(recipient_name or "")
        .strip()
    )

    payload = {

        "sender": {
            "name":
                BREVO_SENDER_NAME,

            "email":
                BREVO_SENDER_EMAIL
        },

        "to": [
            {
                "email":
                    recipient_email,

                "name":
                    recipient_name
            }
        ],

        "subject":
            subject,

        "htmlContent":
            html_content
    }

    if text_content:

        payload[
            "textContent"
        ] = text_content

    headers = {

        "accept":
            "application/json",

        "api-key":
            BREVO_API_KEY,

        "content-type":
            "application/json"
    }

    response = requests.post(

        BREVO_API_URL,

        headers=headers,

        json=payload,

        timeout=30
    )

    if not response.ok:

        try:

            details = response.json()

        except ValueError:

            details = response.text

        raise RuntimeError(
            f"Brevo email failed "
            f"(HTTP {response.status_code}): "
            f"{details}"
        )

    try:

        return response.json()

    except ValueError:

        return {

            "status_code":
                response.status_code,

            "response":
                response.text
        }


# ============================================================
# SHORTLISTED EMAIL
# ============================================================

def send_shortlisted_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id
):

    """
    Notify the candidate that their application
    has been shortlisted.

    IMPORTANT:
    This email does NOT contain interview timing.

    The candidate should reply with their preferred interview session: AM or PM.
    """

    candidate_name = str(
        candidate_name or "Candidate"
    ).strip()

    job_role = str(
        job_role or "the position"
    ).strip()

    application_id = str(
        application_id or ""
    ).strip()

    subject = (
        f"VTAB Square | Application Shortlisted - "
        f"{job_role}"
    )

    html_content = f"""
<!DOCTYPE html>
<html>

<head>

    <meta charset="UTF-8">

    <title>
        Application Shortlisted
    </title>

</head>

<body
    style="
        font-family: Arial, sans-serif;
        line-height: 1.6;
    "
>

    <h2>
        Application Shortlisted
    </h2>

    <p>
        Dear {candidate_name},
    </p>

    <p>
        We are pleased to inform you that your application
        for <strong>{job_role}</strong> at
        <strong>VTAB Square</strong> has been shortlisted.
    </p>

    <p>
        We would like to proceed with the next stage
        of the recruitment process.
    </p>

    <p>
        <strong>
            Please reply to this email with your preferred
            interview session: AM or PM.
        </strong>
    </p>

    <p>
        Available interview window: 10:00 AM - 2:00 PM IST.
        Reply with AM or PM. Our AI scheduler will then assign
        an available slot.
    </p>

    <p>
        <strong>Application ID:</strong>
        {application_id}
    </p>

    <p>
        Regards,<br>
        VTAB Square Recruitment Team
    </p>

</body>

</html>
"""

    text_content = f"""
Dear {candidate_name},

We are pleased to inform you that your application for
{job_role} at VTAB Square has been shortlisted.

We would like to proceed with the next stage of the
recruitment process.

Please reply to this email with your preferred interview
session: AM or PM.

Interview window: 10:00 AM - 2:00 PM IST.
Reply with AM or PM. Our AI scheduler will then assign
an available slot.

Application ID: {application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(

        recipient_email=
            recipient_email,

        recipient_name=
            candidate_name,

        subject=
            subject,

        html_content=
            html_content,

        text_content=
            text_content
    )


# ============================================================
# INTERVIEW AVAILABILITY REQUEST
# ============================================================

def send_availability_request(
    candidate_name,
    recipient_email,
    job_role,
    application_id
):

    """
    Ask a candidate who has accepted the opportunity
    to provide a specific interview date and time.
    """

    candidate_name = str(
        candidate_name or "Candidate"
    ).strip()

    job_role = str(
        job_role or "the position"
    ).strip()

    application_id = str(
        application_id or ""
    ).strip()

    subject = (
        "VTAB Square | Interview Availability Request"
    )

    html_content = f"""
<!DOCTYPE html>
<html>

<head>

    <meta charset="UTF-8">

    <title>
        Interview Availability Request
    </title>

</head>

<body
    style="
        font-family: Arial, sans-serif;
        line-height: 1.6;
    "
>

    <h2>
        Interview Availability
    </h2>

    <p>
        Dear {candidate_name},
    </p>

    <p>
        Thank you for confirming your interest in the
        <strong>{job_role}</strong> opportunity at
        <strong>VTAB Square</strong>.
    </p>

    <p>
        Please reply to this email with your preferred
        interview session: <strong>AM</strong> or <strong>PM</strong>.
    </p>

    <p>
        Interview window:
        <strong>10:00 AM - 2:00 PM IST</strong>
        <br><br>
        Example reply: <strong>"AM"</strong> or <strong>"PM"</strong>
    </p>

    <p>
        Once your availability is received, our system
        will schedule the interview and send you the
        Google Meet details.
    </p>

    <p>
        <strong>Application ID:</strong>
        {application_id}
    </p>

    <p>
        Regards,<br>
        VTAB Square Recruitment Team
    </p>

</body>

</html>
"""

    text_content = f"""
Dear {candidate_name},

Thank you for confirming your interest in the
{job_role} opportunity at VTAB Square.

Please reply to this email with your preferred
interview session: AM or PM.

For example:

"AM" or "PM"

Once your AM/PM preference is received, our AI scheduling
system will assign an available slot and send you the Google Meet details.

Application ID: {application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(

        recipient_email=
            recipient_email,

        recipient_name=
            candidate_name,

        subject=
            subject,

        html_content=
            html_content,

        text_content=
            text_content
    )


# ============================================================
# REJECTION EMAIL
# ============================================================

def send_rejection_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id
):

    candidate_name = str(
        candidate_name or "Candidate"
    ).strip()

    job_role = str(
        job_role or "the position"
    ).strip()

    application_id = str(
        application_id or ""
    ).strip()

    subject = (
        f"VTAB Square | Application Update - "
        f"{job_role}"
    )

    html_content = f"""
<!DOCTYPE html>
<html>

<head>

    <meta charset="UTF-8">

    <title>
        Application Update
    </title>

</head>

<body
    style="
        font-family: Arial, sans-serif;
        line-height: 1.6;
    "
>

    <h2>
        Application Update
    </h2>

    <p>
        Dear {candidate_name},
    </p>

    <p>
        Thank you for your interest in the
        <strong>{job_role}</strong> position
        at VTAB Square.
    </p>

    <p>
        After reviewing your application, we will not
        be proceeding with your application at this stage.
    </p>

    <p>
        We appreciate your time and interest in VTAB Square
        and wish you success in your future opportunities.
    </p>

    <p>
        <strong>Application ID:</strong>
        {application_id}
    </p>

    <p>
        Regards,<br>
        VTAB Square Recruitment Team
    </p>

</body>

</html>
"""

    text_content = f"""
Dear {candidate_name},

Thank you for your interest in the {job_role}
position at VTAB Square.

After reviewing your application, we will not be
proceeding with your application at this stage.

We appreciate your time and interest in VTAB Square
and wish you success in your future opportunities.

Application ID: {application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(

        recipient_email=
            recipient_email,

        recipient_name=
            candidate_name,

        subject=
            subject,

        html_content=
            html_content,

        text_content=
            text_content
    )