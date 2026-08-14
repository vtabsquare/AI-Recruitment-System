from email_service import send_email


# ============================================================
# VTAB SQUARE INTERVIEW CONFIRMATION EMAIL
# ============================================================

def send_interview_confirmation(
    candidate_email,
    candidate_name,
    interview_result
):
    """
    Send the final interview confirmation email.

    This email is sent only after:
        1. Candidate provided a valid date/time
        2. Google Calendar event was created
        3. Google Meet link was successfully generated

    The candidate's exact requested time is displayed.
    """

    # ========================================================
    # VALIDATION
    # ========================================================

    if not candidate_email:

        raise ValueError(
            "Candidate email is required."
        )

    if not interview_result:

        raise ValueError(
            "Interview result is required."
        )

    meet_link = (
        interview_result.get(
            "meet_link",
            ""
        )
    )

    if not meet_link:

        raise ValueError(
            "Google Meet link is missing. "
            "Interview confirmation email will not be sent."
        )

    candidate_name = str(
        candidate_name
        or "Candidate"
    ).strip()

    candidate_email = str(
        candidate_email
    ).strip().lower()

    # ========================================================
    # INTERVIEW DATE/TIME
    # ========================================================

    start_time = interview_result.get(
        "start_time"
    )

    end_time = interview_result.get(
        "end_time"
    )

    if not start_time:

        raise ValueError(
            "Interview start time is missing."
        )

    if not end_time:

        raise ValueError(
            "Interview end time is missing."
        )

    interview_date = (
        start_time.strftime(
            "%A, %d %B %Y"
        )
    )

    interview_start = (
        start_time.strftime(
            "%I:%M %p"
        )
    )

    interview_end = (
        end_time.strftime(
            "%I:%M %p"
        )
    )

    timezone_name = (
        interview_result.get(
            "timezone",
            "Asia/Kolkata"
        )
    )

    # ========================================================
    # SUBJECT
    # ========================================================

    subject = (
        "VTAB Square | Interview Confirmed"
    )

    # ========================================================
    # HTML EMAIL
    # ========================================================

    html_content = f"""
<!DOCTYPE html>

<html>

<head>

    <meta charset="UTF-8">

    <title>
        Interview Confirmed
    </title>

</head>

<body
    style="
        margin:0;
        padding:0;
        background:#f4f6f8;
        font-family:Arial, Helvetica, sans-serif;
        color:#222;
    "
>

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    border="0"
    style="
        background:#f4f6f8;
        padding:30px 0;
    "
>

<tr>

<td align="center">

<table
    width="600"
    cellpadding="0"
    cellspacing="0"
    border="0"
    style="
        background:#ffffff;
        border-radius:10px;
        overflow:hidden;
    "
>

<!-- HEADER -->

<tr>

<td
    style="
        padding:28px 32px;
        background:#111827;
        color:#ffffff;
    "
>

<h1
    style="
        margin:0;
        font-size:24px;
    "
>
    VTAB Square
</h1>

<p
    style="
        margin:8px 0 0;
        font-size:14px;
        color:#d1d5db;
    "
>
    Interview Confirmation
</p>

</td>

</tr>


<!-- CONTENT -->

<tr>

<td
    style="
        padding:32px;
    "
>

<p>
    Dear {candidate_name},
</p>

<p>
    We are pleased to confirm your interview
    with <strong>VTAB Square</strong>.
</p>

<p>
    Your preferred interview time has been
    successfully scheduled.
</p>


<!-- INTERVIEW DETAILS -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    border="0"
    style="
        margin:24px 0;
        border:1px solid #e5e7eb;
        border-radius:8px;
    "
>

<tr>

<td
    style="
        padding:18px;
    "
>

<p
    style="
        margin:0 0 12px;
        font-weight:bold;
        font-size:16px;
    "
>
    Interview Details
</p>

<p style="margin:7px 0;">

<strong>Date:</strong>
{interview_date}

</p>

<p style="margin:7px 0;">

<strong>Time:</strong>
{interview_start}
-
{interview_end}

</p>

<p style="margin:7px 0;">

<strong>Timezone:</strong>
{timezone_name}

</p>

<p style="margin:7px 0;">

<strong>Mode:</strong>
Online - Google Meet

</p>

</td>

</tr>

</table>


<!-- MEET BUTTON -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    border="0"
>

<tr>

<td align="center">

<a
    href="{meet_link}"
    style="
        display:inline-block;
        padding:14px 28px;
        background:#2563eb;
        color:#ffffff;
        text-decoration:none;
        border-radius:7px;
        font-weight:bold;
        font-size:15px;
    "
>
    Join Google Meet
</a>

</td>

</tr>

</table>


<p
    style="
        margin-top:24px;
    "
>

<strong>
Google Meet Link:
</strong>

</p>

<p
    style="
        word-break:break-all;
        background:#f3f4f6;
        padding:12px;
        border-radius:6px;
        font-size:13px;
    "
>

<a
    href="{meet_link}"
>
    {meet_link}
</a>

</p>


<p>
    Please join the meeting a few minutes
    before the scheduled interview time.
</p>


<p>
    We look forward to speaking with you.
</p>


<p>
    Regards,<br>
    <strong>
        VTAB Square Recruitment Team
    </strong>
</p>

</td>

</tr>


<!-- FOOTER -->

<tr>

<td
    style="
        padding:20px 32px;
        background:#f9fafb;
        text-align:center;
        color:#6b7280;
        font-size:12px;
    "
>

This is an automated recruitment email
from VTAB Square.

</td>

</tr>

</table>

</td>

</tr>

</table>

</body>

</html>
"""

    # ========================================================
    # PLAIN TEXT VERSION
    # ========================================================

    text_content = f"""
Dear {candidate_name},

Your interview with VTAB Square has been successfully confirmed.

Interview Details

Date:
{interview_date}

Time:
{interview_start} - {interview_end}

Timezone:
{timezone_name}

Mode:
Online - Google Meet


Google Meet:
{meet_link}


Please join the meeting a few minutes before the scheduled
interview time.

We look forward to speaking with you.

Regards,
VTAB Square Recruitment Team
""".strip()

    # ========================================================
    # SEND THROUGH BREVO
    # ========================================================

    print()
    print("=" * 60)
    print(
        "SENDING FINAL INTERVIEW EMAIL"
    )
    print("=" * 60)

    print()
    print(
        "Recipient:",
        candidate_email
    )

    print(
        "Date:",
        interview_date
    )

    print(
        "Time:",
        interview_start
    )

    print(
        "Meet:",
        meet_link
    )

    response = send_email(

        recipient_email=
            candidate_email,

        recipient_name=
            candidate_name,

        subject=
            subject,

        html_content=
            html_content,

        text_content=
            text_content
    )

    # ========================================================
    # BREVO MESSAGE ID
    # ========================================================

    message_id = ""

    if isinstance(
        response,
        dict
    ):

        message_id = (
            response.get(
                "messageId",
                ""
            )
            or
            response.get(
                "message_id",
                ""
            )
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    print()
    print("=" * 60)
    print(
        "INTERVIEW CONFIRMATION EMAIL SENT"
    )
    print("=" * 60)

    print()
    print(
        "Recipient:",
        candidate_email
    )

    print(
        "Message ID:",
        message_id
    )

    print(
        "Google Meet:",
        meet_link
    )

    return {

        "recipient":
            candidate_email,

        "message_id":
            message_id,

        "subject":
            subject,

        "meet_link":
            meet_link,

        "interview_date":
            interview_date,

        "interview_start":
            interview_start,

        "interview_end":
            interview_end,

        "timezone":
            timezone_name,

        "brevo_response":
            response
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(
        "INTERVIEW EMAIL SERVICE TEST"
    )
    print("=" * 60)

    print()
    print(
        "This module is normally called by reply_pipeline.py."
    )

    print(
        "No email will be sent by this direct test."
    )