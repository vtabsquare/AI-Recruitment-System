import re
from pathlib import Path
from datetime import datetime
import sys

# Keep Windows PowerShell from crashing on Unicode email subjects/bodies.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from supabase_db import (
    supabase,
    get_candidate_by_email,
    update_application_status,
)

from email_service import send_email

from interview_scheduler import (
    TIMEZONE_NAME,
    get_calendar_service,
    parse_slot_time,
    validate_slot_window,
    is_slot_available,
    create_google_calendar_event,
)


# ============================================================
# VTAB SQUARE REPLY -> INTERVIEW SCHEDULING PIPELINE
#
# Flow:
# Candidate replies AM/PM
#        ->
# AI detects session
#        ->
# Email available company slots
#        ->
# Candidate replies with exact slot
#        ->
# Validate slot
#        ->
# Google Calendar + Meet
#        ->
# Save interview in Supabase
#        ->
# Confirmation email
# ============================================================

try:
    from config import COMPANY_EMAIL, INTERVIEW_MANAGER_EMAIL
except Exception:
    COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "vitabsquare@gmail.com")
    INTERVIEW_MANAGER_EMAIL = (
        os.getenv("INTERVIEW_MANAGER_EMAIL")
        or os.getenv("INTERVIEWER_EMAIL")
        or COMPANY_EMAIL
    )

# VTAB SQUARE COMPANY INTERVIEW SLOTS
# Every interview starts before 2:00 PM.
COMPANY_SLOTS = {
    "MORNING": [
        "10:00 AM",
        "10:30 AM",
        "11:00 AM",
        "11:30 AM",
    ],
    "AFTERNOON": [
        "12:00 PM",
        "12:30 PM",
        "1:00 PM",
        "1:30 PM",
    ],
}

# These are automated senders, not candidate replies.
IGNORED_SENDER_DOMAINS = {
    "brevosend.com",
    "mailin.fr",
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "wipro.com",
    "canva.com",
    "supabase.com",
    "salesforce.com",
}

ACTIVE_APPLICATION_STATUSES = [
    "shortlisted",
    "interview_pending",
]


# ============================================================
# EMAIL HELPERS
# ============================================================

def extract_email_address(value):
    """Extract an email address from a Gmail From/To header."""

    if not value:
        return ""

    match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        str(value),
    )

    if not match:
        return ""

    return match.group(0).strip().lower()


def is_ignored_sender(email):
    """Return True for automated/non-candidate senders."""

    if not email:
        return True

    email = email.lower().strip()

    if email == COMPANY_EMAIL.lower():
        return True

    if "@" not in email:
        return True

    domain = email.rsplit("@", 1)[1]

    return (
        domain in IGNORED_SENDER_DOMAINS
        or domain.endswith(".brevosend.com")
    )


def get_header(headers, name):
    """Read one Gmail header."""

    target = name.lower()

    for header in headers:
        if header.get("name", "").lower() == target:
            return header.get("value", "")

    return ""


# ============================================================
# SESSION DETECTION
# ============================================================

def detect_interview_session(text):
    """
    Detect AM or PM from a candidate reply.

    Returns:
        MORNING
        AFTERNOON
        AMBIGUOUS
        None
    """

    if not text:
        return None

    text = str(text).lower().strip()

    morning_patterns = [
        r"\bmorning\b",
        r"\bam\b",
        r"\ba\.m\.\b",
        r"\b10\s*am\b",
        r"\b10:00\s*am\b",
        r"\b10:30\s*am\b",
        r"\b11:00\s*am\b",
        r"\b11:30\s*am\b",
    ]

    afternoon_patterns = [
        r"\bafternoon\b",
        r"\bpm\b",
        r"\bp\.m\.\b",
        r"\b12\s*pm\b",
        r"\b12:00\s*pm\b",
        r"\b12:30\s*pm\b",
        r"\b1\s*pm\b",
        r"\b1:00\s*pm\b",
        r"\b1:30\s*pm\b",
    ]

    morning_found = any(
        re.search(pattern, text)
        for pattern in morning_patterns
    )

    afternoon_found = any(
        re.search(pattern, text)
        for pattern in afternoon_patterns
    )

    if morning_found and afternoon_found:
        return "AMBIGUOUS"

    if morning_found:
        return "MORNING"

    if afternoon_found:
        return "AFTERNOON"

    return None


# ============================================================
# EXACT SLOT PARSING
# ============================================================

def detect_exact_slot(text):
    """
    Detect a company slot from a candidate reply.

    Accepted examples:
        10:00 AM
        10:30 AM
        11 AM
        12:00 PM
        12:30 PM
        1:00 PM
        1:30 PM
    """

    if not text:
        return None

    text = str(text).upper()

    # First look for a complete time with AM/PM.
    match = re.search(
        r"\b(10|11|12|1)(?::([0-5][0-9]))?\s*(AM|PM)\b",
        text,
    )

    if not match:
        return None

    hour = match.group(1)
    minute = match.group(2) or "00"
    meridiem = match.group(3)

    return f"{hour}:{minute} {meridiem}"


def normalize_slot_label(slot):
    """Normalize slot labels for reliable comparison."""

    if not slot:
        return ""

    value = str(slot).strip().upper()

    # Normalize 1:00 PM -> 1:00 PM.
    # Keep the display format used by COMPANY_SLOTS.
    match = re.fullmatch(
        r"(10|11|12|1):([0-5][0-9])\s*(AM|PM)",
        value,
    )

    if not match:
        return value

    return (
        f"{match.group(1)}:"
        f"{match.group(2)} "
        f"{match.group(3)}"
    )


def find_company_slot(session, requested_slot):
    """
    Check whether the requested slot belongs to the
    company's configured session.
    """

    requested = normalize_slot_label(
        requested_slot
    )

    for slot in COMPANY_SLOTS.get(
        session,
        [],
    ):
        if normalize_slot_label(slot) == requested:
            return slot

    return None


# ============================================================
# SUPABASE APPLICATION LOOKUP
# ============================================================

def get_active_application_for_candidate(
    candidate_id
):
    """
    Find the most recent active application for a candidate.

    The current supabase_db.py exposes candidate lookup and
    application-status update functions, but not an application
    lookup by candidate. Therefore this function performs the
    required Supabase query directly.
    """

    response = (
        supabase
        .table("applications")
        .select(
            "id, application_id, candidate_id, job_role_id, status"
        )
        .eq(
            "candidate_id",
            candidate_id,
        )
        .in_(
            "status",
            ACTIVE_APPLICATION_STATUSES,
        )
        .order(
            "applied_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


# ============================================================
# JOB ROLE LOOKUP
# ============================================================

def get_job_role_name(job_role_id):
    """Get the job role name for email messages."""

    response = (
        supabase
        .table("job_roles")
        .select("role_name")
        .eq(
            "id",
            job_role_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return "the position"

    return response.data[0].get(
        "role_name",
        "the position",
    )


# ============================================================
# SEND AVAILABLE SLOTS
# ============================================================

def send_available_slots_email(
    candidate_name,
    candidate_email,
    job_role,
    application_id,
    session,
):
    """
    Send the actual available company slots for the
    requested AM/PM session.

    This does not book anything.
    """

    slots = COMPANY_SLOTS.get(
        session,
        [],
    )

    if not slots:
        raise ValueError(
            f"No company slots configured for {session}."
        )

    if session == "MORNING":
        session_label = "Morning"
    else:
        session_label = "Afternoon"

    slot_lines_html = "".join(
        f"<li><strong>{slot}</strong></li>"
        for slot in slots
    )

    slot_lines_text = "\n".join(
        f"- {slot}"
        for slot in slots
    )

    subject = (
        "VTAB Square | Choose Your Interview Slot"
    )

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Slot Selection</title>
</head>

<body style="font-family: Arial, sans-serif; line-height: 1.6;">

    <h2>Interview Slot Selection</h2>

    <p>
        Dear {candidate_name},
    </p>

    <p>
        We received your preferred
        <strong>{session_label}</strong> interview session
        for the <strong>{job_role}</strong> position.
    </p>

    <p>
        Please choose one of the available slots below
        and reply to this email with the exact time.
    </p>

    <ul>
        {slot_lines_html}
    </ul>

    <p>
        <strong>Interview window:</strong>
        10:00 AM - 2:00 PM IST
    </p>

    <p>
        Example reply:
        <br>
        <strong>{slots[0]}</strong>
    </p>

    <p>
        Our system will validate your selected slot
        before creating the interview.
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

We received your preferred {session_label} interview session
for the {job_role} position.

Please choose one available slot and reply with the exact time:

{slot_lines_text}

Interview window: 10:00 AM - 2:00 PM IST.

Example reply:
{slots[0]}

Our system will validate your selected slot before creating
the interview.

Application ID: {application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(
        recipient_email=candidate_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


# ============================================================
# SAVE INTERVIEW IN SUPABASE
# ============================================================

def save_interview(
    application,
    scheduled_at,
    meeting_link,
):
    """
    Save the scheduled interview and assign the active VTAB Square
    manager as the interviewer.

    Database relationship:
        interviews.interviewer_id -> staff_users.id
    """

    application_id = application["id"]

    # --------------------------------------------------------
    # FIND ACTIVE INTERVIEW MANAGER
    # --------------------------------------------------------

    manager_email = "vitabsquare@gmail.com"

    manager_response = (
        supabase
        .table("staff_users")
        .select(
            "id, full_name, email, role, is_active"
        )
        .eq(
            "email",
            manager_email,
        )
        .eq(
            "role",
            "manager",
        )
        .eq(
            "is_active",
            True,
        )
        .limit(1)
        .execute()
    )

    if not manager_response.data:
        raise RuntimeError(
            "No active VTAB Square interview manager "
            f"was found for {manager_email}. "
            "Create the manager in staff_users first."
        )

    interviewer_id = (
        manager_response.data[0]["id"]
    )

    interviewer_name = (
        manager_response.data[0]["full_name"]
    )

    print(
        f"Interviewer assigned: "
        f"{interviewer_name} "
        f"({interviewer_id})"
    )

    # --------------------------------------------------------
    # AVOID DUPLICATE INTERVIEW
    # --------------------------------------------------------

    existing = (
        supabase
        .table("interviews")
        .select(
            "id, application_id, "
            "interviewer_id, status, "
            "scheduled_at, meeting_link"
        )
        .eq(
            "application_id",
            application_id,
        )
        .limit(1)
        .execute()
    )

    if existing.data:

        existing_interview = (
            existing.data[0]
        )

        # Repair older interviews that were
        # created before interviewer association.
        if not existing_interview.get(
            "interviewer_id"
        ):

            repaired = (
                supabase
                .table("interviews")
                .update({
                    "interviewer_id":
                        interviewer_id
                })
                .eq(
                    "id",
                    existing_interview["id"],
                )
                .execute()
            )

            if not repaired.data:
                raise RuntimeError(
                    "Existing interview was found, "
                    "but interviewer association "
                    "could not be updated."
                )

            print(
                "Existing interview repaired. "
                f"Interviewer: {interviewer_name}"
            )

            return repaired.data[0]

        return existing_interview

    # --------------------------------------------------------
    # CREATE NEW INTERVIEW
    # --------------------------------------------------------

    response = (
        supabase
        .table("interviews")
        .insert({
            "application_id":
                application_id,

            "interviewer_id":
                interviewer_id,

            "status":
                "scheduled",

            "scheduled_at":
                scheduled_at,

            "meeting_link":
                meeting_link,
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Interview was not saved in Supabase."
        )

    print(
        "Interview saved successfully."
    )

    print(
        f"Interviewer ID: {interviewer_id}"
    )

    return response.data[0]


# ============================================================
# SEND FINAL CONFIRMATION
# ============================================================

def send_interview_confirmation(
    candidate_name,
    candidate_email,
    job_role,
    application_id,
    scheduled_at,
    meeting_link,
):
    """Send the final interview confirmation."""

    if isinstance(
        scheduled_at,
        str,
    ):
        scheduled_text = scheduled_at
    else:
        scheduled_text = scheduled_at.strftime(
            "%A, %d %B %Y at %I:%M %p"
        )

    subject = (
        "VTAB Square | Interview Confirmed"
    )

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Confirmed</title>
</head>

<body style="font-family: Arial, sans-serif; line-height: 1.6;">

    <h2>Interview Confirmed</h2>

    <p>
        Dear {candidate_name},
    </p>

    <p>
        Your interview for
        <strong>{job_role}</strong>
        at <strong>VTAB Square</strong> has been scheduled.
    </p>

    <p>
        <strong>Date & Time:</strong><br>
        {scheduled_text}
    </p>

    <p>
        <strong>Timezone:</strong>
        {TIMEZONE_NAME}
    </p>

    <p>
        <strong>Google Meet:</strong><br>
        <a href="{meeting_link}">
            Join Interview
        </a>
    </p>

    <p>
        Please join a few minutes before the scheduled time.
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

Your interview for {job_role} at VTAB Square has been scheduled.

Date & Time:
{scheduled_text}

Timezone:
{TIMEZONE_NAME}

Google Meet:
{meeting_link}

Please join a few minutes before the scheduled time.

Application ID:
{application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(
        recipient_email=candidate_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


# ============================================================
# SEND MANAGER INTERVIEW CONFIRMATION
# ============================================================

def send_manager_interview_confirmation(
    candidate_name,
    manager_email,
    job_role,
    application_id,
    scheduled_at,
    meeting_link,
):
    """Send the same Google Meet details to the interviewer/manager."""

    if not manager_email:
        return None

    if isinstance(scheduled_at, str):
        scheduled_text = scheduled_at
    else:
        scheduled_text = scheduled_at.strftime(
            "%A, %d %B %Y at %I:%M %p"
        )

    subject = "VTAB Square | Interview Scheduled - Manager Copy"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Scheduled</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Interview Scheduled</h2>
    <p>Dear Interview Manager,</p>
    <p>A candidate interview has been scheduled by the VTAB Square AI Recruitment System.</p>
    <p><strong>Candidate:</strong> {candidate_name}</p>
    <p><strong>Role:</strong> {job_role}</p>
    <p><strong>Date &amp; Time:</strong><br>{scheduled_text}</p>
    <p><strong>Timezone:</strong> {TIMEZONE_NAME}</p>
    <p><strong>Google Meet:</strong><br>
        <a href="{meeting_link}">Join Interview</a>
    </p>
    <p><strong>Application ID:</strong> {application_id}</p>
    <p>Please use the Meet link above to conduct the interview.</p>
    <p>Regards,<br>VTAB Square Recruitment Team</p>
</body>
</html>
"""

    text_content = f"""
Dear Interview Manager,

A candidate interview has been scheduled by the VTAB Square AI Recruitment System.

Candidate: {candidate_name}
Role: {job_role}
Date & Time: {scheduled_text}
Timezone: {TIMEZONE_NAME}
Google Meet: {meeting_link}
Application ID: {application_id}

Please use the Meet link above to conduct the interview.

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(
        recipient_email=manager_email,
        recipient_name="Interview Manager",
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )



# ============================================================
# SEND INTERVIEW PREFERENCE / ALL AVAILABLE SLOTS
# ============================================================

def send_interview_preference_email(
    candidate_name,
    candidate_email,
    job_role,
    application_id,
):
    """
    Send the first interview-stage email after a shortlisted
    candidate confirms interest.

    This email shows all currently configured company slots.
    The candidate can reply with an exact slot.
    No interview is booked at this stage.
    """

    morning_slots = COMPANY_SLOTS.get("MORNING", [])
    afternoon_slots = COMPANY_SLOTS.get("AFTERNOON", [])
    all_slots = morning_slots + afternoon_slots

    if not all_slots:
        raise ValueError(
            "No company interview slots are configured."
        )

    slot_lines_html = "".join(
        f"<li><strong>{slot}</strong></li>"
        for slot in all_slots
    )

    slot_lines_text = "\n".join(
        f"- {slot}"
        for slot in all_slots
    )

    subject = "VTAB Square | Choose Your Interview Slot"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Interview Slot Selection</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Interview Slot Selection</h2>

    <p>Dear {candidate_name},</p>

    <p>
        Thank you for confirming your interest in the
        <strong>{job_role}</strong> position at
        <strong>VTAB Square</strong>.
    </p>

    <p>
        Please choose one of the available interview slots below
        and reply to this email with the exact time.
    </p>

    <ul>
        {slot_lines_html}
    </ul>

    <p>
        <strong>Interview window:</strong>
        10:00 AM - 2:00 PM IST
    </p>

    <p>
        Example reply:
        <br>
        <strong>{all_slots[0]}</strong>
    </p>

    <p>
        Your selected slot will be validated before the interview
        is scheduled and the Google Meet link is created.
    </p>

    <p>
        <strong>Application ID:</strong> {application_id}
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

Thank you for confirming your interest in the {job_role}
position at VTAB Square.

Please choose one available interview slot and reply with
the exact time:

{slot_lines_text}

Interview window: 10:00 AM - 2:00 PM IST.

Example reply:
{all_slots[0]}

Your selected slot will be validated before the interview
is scheduled and the Google Meet link is created.

Application ID: {application_id}

Regards,
VTAB Square Recruitment Team
""".strip()

    return send_email(
        recipient_email=candidate_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


# ============================================================
# PROCESS SHORTLISTED CANDIDATE INTEREST REPLY
# ============================================================

def process_interest_reply(
    sender_email,
    reply_text,
):
    """
    Process a shortlisted candidate's confirmation of interest.

    Example:
        "Yes, I'm interested in this position."

    Result:
        The existing application is moved to interview_pending
        and the candidate receives the interview slot-selection
        email containing all configured company slots.
    """

    sender_email = extract_email_address(sender_email)

    if not sender_email:
        raise ValueError(
            "Candidate email could not be extracted."
        )

    candidate = get_candidate_by_email(sender_email)

    if not candidate:
        raise ValueError(
            f"No candidate found for {sender_email}."
        )

    application = get_active_application_for_candidate(
        candidate["id"]
    )

    if not application:
        raise ValueError(
            "No shortlisted/interview-pending application "
            "was found for this candidate."
        )

    current_status = application.get("status")

    # A candidate's "Yes" reply is meaningful only after
    # the existing application has reached the shortlisted stage.
    if current_status not in (
        "shortlisted",
        "interview_pending",
    ):
        raise ValueError(
            "Candidate interest reply was received, but the "
            f"application is currently '{current_status}'. "
            "Expected 'shortlisted' or 'interview_pending'."
        )

    # Keep the application linked to the same database UUID.
    # Do not create another candidate/application.
    if current_status == "shortlisted":
        update_application_status(
            application["id"],
            "interview_pending",
        )

    job_role = get_job_role_name(
        application["job_role_id"]
    )

    application_public_id = (
        application.get("application_id")
        or application["id"]
    )

    email_result = send_interview_preference_email(
        candidate_name=candidate["candidate_name"],
        candidate_email=candidate["email"],
        job_role=job_role,
        application_id=application_public_id,
    )

    print()
    print("INTERVIEW SLOT SELECTION EMAIL SENT")
    print("Candidate:", candidate["email"])
    print("Application:", application_public_id)
    print("Email result:", email_result)

    return {
        "success": True,
        "stage": "interest_received",
        "candidate": candidate,
        "application": application,
        "email": email_result,
    }

# ============================================================
# PROCESS AM/PM REPLY
# ============================================================

def process_session_reply(
    sender_email,
    reply_text,
):
    """
    Process the first candidate reply.

    Example:
        "AM"

    Result:
        Sends the configured AM slots to the candidate.
    """

    sender_email = (
        extract_email_address(
            sender_email
        )
    )

    if not sender_email:
        raise ValueError(
            "Candidate email could not be extracted."
        )

    candidate = get_candidate_by_email(
        sender_email
    )

    if not candidate:
        raise ValueError(
            f"No candidate found for {sender_email}."
        )

    application = (
        get_active_application_for_candidate(
            candidate["id"]
        )
    )

    if not application:
        raise ValueError(
            "No shortlisted/interview-pending "
            "application was found for this candidate."
        )

    session = detect_interview_session(
        reply_text
    )

    if session == "AMBIGUOUS":
        raise ValueError(
            "Candidate mentioned both AM and PM. "
            "Ask the candidate to reply with only AM or PM."
        )

    if session not in (
        "MORNING",
        "AFTERNOON",
    ):
        raise ValueError(
            "Could not detect AM or PM from the candidate reply."
        )

    update_application_status(
        application["id"],
        "interview_pending",
    )

    job_role = get_job_role_name(
        application["job_role_id"]
    )

    application_public_id = (
        application.get(
            "application_id"
        )
        or application["id"]
    )

    email_result = (
        send_available_slots_email(
            candidate_name=
                candidate["candidate_name"],

            candidate_email=
                candidate["email"],

            job_role=
                job_role,

            application_id=
                application_public_id,

            session=
                session,
        )
    )

    print()
    print("SLOT EMAIL RESULT:")
    print(email_result)

    return {
        "success": True,
        "stage": "session_received",
        "candidate": candidate,
        "application": application,
        "session": session,
        "available_slots":
            COMPANY_SLOTS[session],
        "email": email_result,
    }


# ============================================================
# PROCESS EXACT SLOT REPLY
# ============================================================

def process_slot_reply(
    sender_email,
    reply_text,
):
    """
    Process the candidate's second reply.

    Example:
        "10:30 AM"

    The requested slot must exactly match one of the company's
    configured slots.
    """

    sender_email = (
        extract_email_address(
            sender_email
        )
    )

    candidate = get_candidate_by_email(
        sender_email
    )

    if not candidate:
        raise ValueError(
            f"No candidate found for {sender_email}."
        )

    application = (
        get_active_application_for_candidate(
            candidate["id"]
        )
    )

    if not application:
        raise ValueError(
            "No active interview application was found."
        )

    requested_slot = detect_exact_slot(
        reply_text
    )

    if not requested_slot:
        raise ValueError(
            "Could not detect an exact interview slot. "
            "Reply using a slot such as 10:30 AM."
        )

    # IMPORTANT: once an exact slot has been detected, derive the
    # session from THAT slot only. Do not run AM/PM detection against
    # the full reply again because Gmail replies can contain quoted
    # emails with other AM/PM values.
    if requested_slot.upper().endswith("AM"):
        session = "MORNING"
    elif requested_slot.upper().endswith("PM"):
        session = "AFTERNOON"
    else:
        raise ValueError(
            f"Could not determine AM or PM from slot: {requested_slot}"
        )

    company_slot = find_company_slot(
        session,
        requested_slot,
    )

    if not company_slot:
        raise ValueError(
            f"{requested_slot} is not a valid "
            f"{session.lower()} company slot."
        )

    # --------------------------------------------------------
    # Use today's date as the first date to check.
    # Scheduler will search the next available weekday.
    # --------------------------------------------------------

    from datetime import timedelta, timezone

    IST = timezone(
        timedelta(
            hours=5,
            minutes=30,
        )
    )

    now = datetime.now(IST)

    # --------------------------------------------------------
    # Search next 14 weekdays for this exact company slot.
    # --------------------------------------------------------

    service = get_calendar_service()

    selected_start = None
    selected_end = None

    for day_offset in range(
        0,
        14,
    ):

        interview_date = (
            now.date()
            + timedelta(
                days=day_offset
            )
        )

        # Monday-Friday only.
        if interview_date.weekday() >= 5:
            continue

        start_time = parse_slot_time(
            interview_date,
            company_slot,
        )

        end_time = (
            start_time
            + timedelta(
                minutes=30
            )
        )

        if start_time <= now:
            continue

        if not validate_slot_window(
            start_time
        ):
            continue

        if is_slot_available(
            service,
            start_time,
            end_time,
        ):

            selected_start = start_time
            selected_end = end_time
            break

    if selected_start is None:
        raise ValueError(
            f"The requested slot {company_slot} "
            "is not currently available on the next "
            "available interview dates."
        )

    # --------------------------------------------------------
    # Build proposal for existing calendar helper.
    # --------------------------------------------------------

    proposal = {
        "success": True,
        "candidate_name":
            candidate["candidate_name"],
        "session":
            session,
        "start_time":
            selected_start,
        "end_time":
            selected_end,
        "duration_minutes":
            30,
        "timezone":
            TIMEZONE_NAME,
    }

    # --------------------------------------------------------
    # Create Calendar + Meet.
    # --------------------------------------------------------

    calendar_result = (
        create_google_calendar_event(
            proposal=
                proposal,

            candidate_email=
                candidate["email"],

            test_event=
                False,

            application_id=
                application["id"],
        )
    )

    meeting_link = calendar_result[
        "meet_link"
    ]

    # --------------------------------------------------------
    # Save interview.
    # --------------------------------------------------------

    interview = save_interview(
        application=
            application,

        scheduled_at=
            selected_start.isoformat(),

        meeting_link=
            meeting_link,
    )

    # --------------------------------------------------------
    # Update application.
    # --------------------------------------------------------

    update_application_status(
        application["id"],
        "interview_scheduled",
    )

    job_role = get_job_role_name(
        application["job_role_id"]
    )

    application_public_id = (
        application.get(
            "application_id"
        )
        or application["id"]
    )

    # --------------------------------------------------------
    # Send confirmation.
    # --------------------------------------------------------

    email_result = (
        send_interview_confirmation(
            candidate_name=
                candidate["candidate_name"],

            candidate_email=
                candidate["email"],

            job_role=
                job_role,

            application_id=
                application_public_id,

            scheduled_at=
                selected_start,

            meeting_link=
                meeting_link,
        )
    )

    manager_email_result = (
        send_manager_interview_confirmation(
            candidate_name=
                candidate["candidate_name"],

            manager_email=
                INTERVIEW_MANAGER_EMAIL,

            job_role=
                job_role,

            application_id=
                application_public_id,

            scheduled_at=
                selected_start,

            meeting_link=
                meeting_link,
        )
    )

    print()
    print("INTERVIEW CONFIRMATION SENT TO CANDIDATE")
    print("Candidate:", candidate["email"])
    print("INTERVIEW MANAGER COPY SENT TO:", INTERVIEW_MANAGER_EMAIL)

    return {
        "success": True,
        "stage": "interview_scheduled",
        "candidate": candidate,
        "application": application,
        "interview": interview,
        "session": session,
        "selected_slot": company_slot,
        "scheduled_at":
            selected_start.isoformat(),
        "meeting_link":
            meeting_link,
        "email":
            email_result,
    }


# ============================================================
# CLASSIFY A REPLY
# ============================================================

def classify_reply(reply_text):
    """
    Decide whether a reply is:
        1. Exact slot selection
        2. AM/PM session selection
        3. Candidate interest/confirmation
        4. Ambiguous
        5. Unknown

    Exact slot is checked first because a quoted email can contain
    AM/PM text from earlier messages.
    """

    exact_slot = detect_exact_slot(reply_text)

    if exact_slot:
        return "EXACT_SLOT"

    session = detect_interview_session(reply_text)

    if session in (
        "MORNING",
        "AFTERNOON",
    ):
        return "SESSION"

    if session == "AMBIGUOUS":
        return "AMBIGUOUS"

    text = str(reply_text or "").strip().lower()

    # Candidate confirmation after a shortlist email.
    # Keep this intentionally broad enough to handle normal
    # human replies, while avoiding treating arbitrary text as YES.
    interest_patterns = [
        r"\byes\b",
        r"\byes[,!.\s]*i(?:'m| am)\s+interested\b",
        r"\bi(?:'m| am)\s+interested\b",
        r"\bi(?:'d| would)\s+like\s+to\s+proceed\b",
        r"\binterested\s+in\s+(?:this|the)\s+(?:position|opportunity|role)\b",
        r"\bplease\s+proceed\b",
        r"\bi\s+would\s+like\s+to\s+proceed\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in interest_patterns
    ):
        return "INTEREST"

    return "UNKNOWN"


# ============================================================
# GMAIL REPLY PROCESSOR
# ============================================================

def get_registered_candidate_emails():
    """Return candidate email addresses currently known to Supabase."""

    response = (
        supabase
        .table("candidates")
        .select("email")
        .execute()
    )

    emails = []

    for row in (response.data or []):
        email = extract_email_address(row.get("email", ""))
        if email and email != COMPANY_EMAIL.lower():
            emails.append(email)

    return sorted(set(emails))


def is_google_calendar_notification(subject):
    """Return True for Google Calendar-generated response notifications."""
    text = str(subject or "").strip().lower()

    prefixes = (
        "accepted:",
        "declined:",
        "tentative:",
        "updated invitation:",
        "canceled event:",
        "cancelled event:",
    )

    if text.startswith(prefixes):
        return True

    phrases = (
        "has accepted this invitation",
        "has declined this invitation",
        "has responded to the invitation",
    )

    return any(phrase in text for phrase in phrases)


def get_candidate_replies(service):
    """
    Read recent Gmail messages and identify real candidate replies.

    We deliberately search broadly instead of relying only on:
        to:COMPANY_EMAIL

    Gmail headers can contain display names, aliases, and different
    recipient formatting. We therefore inspect From/To ourselves.

    Only messages from candidates already registered in Supabase
    are returned.
    """

    print()
    print("=" * 60)
    print("GMAIL MESSAGE SCAN")
    print("=" * 60)

    # IMPORTANT: do not scan the entire mailbox.
    # First obtain candidate senders from Supabase, then ask Gmail
    # for ONLY Inbox messages sent by those known candidates.
    candidate_emails = get_registered_candidate_emails()

    print(
        "Registered candidate senders allowed:",
        len(candidate_emails),
    )

    if not candidate_emails:
        print("No registered candidates found in Supabase.")
        return []

    # Gmail search strings have practical length limits, so query
    # candidates in small batches and deduplicate message IDs.
    all_messages_by_id = {}
    batch_size = 20

    for start in range(0, len(candidate_emails), batch_size):

        batch_emails = candidate_emails[start:start + batch_size]

        sender_query = "{" + " ".join(
            f"from:{email}"
            for email in batch_emails
        ) + "}"

        query = (
            f"in:inbox to:{COMPANY_EMAIL} "
            f"newer_than:2d {sender_query}"
        )

        page_token = None

        while True:
            request = (
                service
                .users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=100,
                    pageToken=page_token,
                )
            )

            response = request.execute()

            for message in response.get("messages", []):
                all_messages_by_id[message["id"]] = message

            page_token = response.get("nextPageToken")

            if not page_token:
                break

    all_messages = list(all_messages_by_id.values())

    print(
        "Candidate Inbox messages found:",
        len(all_messages),
    )

    replies = []

    for message in all_messages:

        msg = (
            service
            .users()
            .messages()
            .get(
                userId="me",
                id=message["id"],
                format="full",
            )
            .execute()
        )

        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        sender = get_header(headers, "From")
        recipient = get_header(headers, "To")
        cc = get_header(headers, "Cc")
        subject = get_header(headers, "Subject")
        date_header = get_header(headers, "Date")

        sender_email = extract_email_address(sender)

        recipient_addresses = [
            extract_email_address(recipient),
            extract_email_address(cc),
        ]

        recipient_addresses = [
            address
            for address in recipient_addresses
            if address
        ]

        # --------------------------------------------------------
        # DEBUG INFORMATION
        # --------------------------------------------------------

        print()
        print("-" * 60)
        print("GMAIL MESSAGE")
        print("From   :", sender)
        print("To     :", recipient)
        if cc:
            print("Cc     :", cc)
        print("Subject:", subject)
        print("Date   :", date_header)

        # --------------------------------------------------------
        # Ignore automated/system senders.
        # --------------------------------------------------------

        if is_ignored_sender(sender_email):
            print("Action :", "IGNORED AUTOMATED/SYSTEM SENDER")
            continue

        # --------------------------------------------------------
        # The company mailbox must appear in To/Cc.
        # --------------------------------------------------------

        company_email = COMPANY_EMAIL.lower()

        if company_email not in recipient_addresses:
            print("Action :", "IGNORED - NOT SENT TO COMPANY MAILBOX")
            continue

        # --------------------------------------------------------
        # Ignore Google Calendar system notifications.
        # These can come from the candidate's own email address,
        # but they are NOT candidate replies.
        # --------------------------------------------------------

        if is_google_calendar_notification(subject):
            print(
                "Action :",
                "IGNORED GOOGLE CALENDAR SYSTEM NOTIFICATION"
            )
            continue

        # --------------------------------------------------------
        # Only a candidate already registered in Supabase can
        # enter the recruitment workflow.
        # --------------------------------------------------------

        candidate = get_candidate_by_email(sender_email)

        if not candidate:
            print("Action :", "IGNORED - SENDER IS NOT A REGISTERED CANDIDATE")
            continue

        print(
            "Candidate:",
            candidate.get("candidate_name", sender_email)
        )
        print("Action   :", "VALID CANDIDATE MESSAGE")

        body = extract_message_body(payload)
        body = clean_reply_body(body)

        if not body.strip():
            print("Action   :", "IGNORED - EMPTY BODY")
            continue

        replies.append(
            {
                "message_id": message["id"],
                "sender": sender_email,
                "subject": subject,
                "body": body,
                "date": date_header,
            }
        )

    print()
    print("=" * 60)
    print("VALID CANDIDATE MESSAGES:", len(replies))
    print("=" * 60)

    return replies


def extract_message_body(
    payload
):
    """
    Recursively extract plain text from a Gmail payload.
    """

    if not payload:
        return ""

    body = payload.get(
        "body",
        {}
    )

    data = body.get(
        "data"
    )

    if data:
        import base64

        try:
            padding = (
                "="
                * (
                    4
                    - len(data) % 4
                )
            )

            decoded = (
                base64.urlsafe_b64decode(
                    data + padding
                )
            )

            return decoded.decode(
                "utf-8",
                errors="ignore",
            )
        except Exception:
            pass

    parts = payload.get(
        "parts",
        []
    )

    collected = []

    for part in parts:

        text = extract_message_body(
            part
        )

        if text:
            collected.append(text)

    return "\n".join(
        collected
    )


def clean_reply_body(
    body
):
    """
    Keep only the candidate's NEW reply and remove Gmail quoted
    content. This is critical for AM/PM and exact-slot detection.

    Gmail can return a reply like:

        AM

        On Tue, 11 Aug 2026, 5:46 pm VTAB Square Recruitment ...
        <previous email>

    The previous email may contain PM slot text. We must stop before
    that quoted section so the candidate's ``AM`` is not classified
    as AM + PM.
    """

    if not body:
        return ""

    body = str(body)
    body = body.replace("\r\n", "\n")
    body = body.replace("\r", "\n")
    body = body.replace("\u00a0", " ")
    body = body.replace("\u202f", " ")

    # Remove HTML comments if HTML survived extraction.
    body = re.sub(
        r"<!--.*?-->",
        "",
        body,
        flags=re.DOTALL,
    )

    # Remove obvious HTML quote blocks before line processing.
    body = re.sub(
        r"<blockquote\b[^>]*>.*?</blockquote>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )

    body = re.sub(
        r'<div[^>]+class=["\'][^"\']*gmail_quote[^"\']*["\'][^>]*>.*',
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Convert common HTML breaks to newlines and remove tags.
    body = re.sub(
        r"<br\s*/?>",
        "\n",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"</(?:div|p|li|tr|h[1-6])\s*>",
        "\n",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<[^>]+>",
        " ",
        body,
    )

    import html as _html
    body = _html.unescape(body)

    lines = []

    for raw_line in body.splitlines():

        stripped = raw_line.strip()

        if not stripped:
            continue

        lower = stripped.lower()

        # Traditional Gmail quoted lines.
        if stripped.startswith(">"):
            continue

        # Gmail's common reply header. Some clients include "wrote:",
        # others expose only the date/time and sender line.
        if (
            lower.startswith("on ")
            and (
                "wrote:" in lower
                or "vtab square" in lower
                or "gmail.com" in lower
                or "recruitment" in lower
            )
        ):
            break

        # Other standard quoted-message headers.
        if lower in {
            "---------- forwarded message ----------",
            "-----original message-----",
            "-------- original message --------",
        }:
            break

        if re.match(r"^(from|sent|to|subject):\s*", stripped, re.I):
            break

        # VTAB's own previous email content.
        if "vtab square |" in lower:
            break

        if "vtab square recruitment team" in lower:
            break

        if "application shortlisted" in lower:
            break

        if "interview availability" in lower:
            break

        if "interview slot selection" in lower:
            break

        if "available interview slots" in lower:
            break

        if "interview window:" in lower:
            break

        lines.append(stripped)

    # Final safety pass: stop at a standalone Gmail-style quote line
    # even if the first pass did not recognize its exact wording.
    cleaned = "\n".join(lines).strip()

    for marker in (
        "\nOn ",
        "\nFrom:",
        "\nSent:",
        "\nTo:",
        "\nSubject:",
    ):
        position = cleaned.lower().find(marker.lower())
        if position >= 0:
            cleaned = cleaned[:position].strip()

    return cleaned


# ============================================================
# LOCAL MESSAGE DEDUPLICATION
# ============================================================

PROCESSED_MESSAGES_FILE = "processed_reply_messages.txt"


def load_processed_message_ids():
    """Load message IDs already handled by this local pipeline."""

    path = Path(PROCESSED_MESSAGES_FILE)

    if not path.exists():
        return set()

    try:
        return {
            line.strip()
            for line in path.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        }
    except Exception:
        return set()


def mark_message_processed(message_id):
    """Remember a Gmail message after it has been handled."""

    if not message_id:
        return

    path = Path(PROCESSED_MESSAGES_FILE)

    with path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(message_id + "\n")



# ============================================================
# PROCESS RECENT REPLIES
# ============================================================

def process_candidate_replies():
    """
    Read recent candidate replies and process them.

    Important:
    This function schedules only when an exact configured
    company slot is explicitly provided by the candidate.
    """

    print()
    print("=" * 60)
    print(
        "VTAB SQUARE CANDIDATE REPLY PIPELINE"
    )
    print("=" * 60)

    from googleapiclient.discovery import build
    from google_auth import get_google_credentials

    try:
        credentials = get_google_credentials()
    except Exception:
        print("[Reply Pipeline] Google authentication unavailable. Skipping reply check.")
        return []

    if not credentials:
        print("[Reply Pipeline] No Google credentials found. Skipping reply check.")
        return []

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )

    replies = get_candidate_replies(
        service
    )

    if not replies:

        print()
        print(
            "No valid candidate replies found."
        )
        print(
            "Automated Brevo/LinkedIn/Indeed/etc. emails "
            "were ignored."
        )

        return []

    results = []

    processed_ids = load_processed_message_ids()

    for reply in replies:

        if reply["message_id"] in processed_ids:
            print()
            print("-" * 60)
            print(
                "Skipping already processed message:",
                reply["message_id"],
            )
            continue

        body = clean_reply_body(
            reply["body"]
        )

        classification = classify_reply(
            body
        )

        print()
        print("-" * 60)
        print(
            "Candidate:",
            reply["sender"]
        )
        print(
            "Subject:",
            reply["subject"]
        )
        print(
            "Detected:",
            classification
        )

        try:

            if classification == "INTEREST":

                result = process_interest_reply(
                    sender_email=
                        reply["sender"],

                    reply_text=
                        body,
                )

                print()
                print(
                    "CANDIDATE INTEREST CONFIRMED"
                )

                print(
                    "Interview slot selection email sent."
                )

            elif classification == "SESSION":

                result = process_session_reply(
                    sender_email=
                        reply["sender"],

                    reply_text=
                        body,
                )

                print(
                    "Available slots sent:"
                )

                for slot in result[
                    "available_slots"
                ]:
                    print(
                        "  ",
                        slot
                    )

            elif classification == "EXACT_SLOT":

                result = process_slot_reply(
                    sender_email=
                        reply["sender"],

                    reply_text=
                        body,
                )

                print()
                print(
                    "INTERVIEW SCHEDULED"
                )

                print(
                    "Date:",
                    result[
                        "scheduled_at"
                    ]
                )

                print(
                    "Google Meet:",
                    result[
                        "meeting_link"
                    ]
                )

            elif classification == "AMBIGUOUS":

                raise ValueError(
                    "Reply contains both AM and PM."
                )

            else:

                # Unknown messages are not considered successfully
                # handled. Do not mark them as processed, so they can
                # be retried after the routing logic is improved.
                print(
                    "No supported recruitment instruction "
                    "detected in this reply. Message was NOT "
                    "marked as processed."
                )

                result = {
                    "success": False,
                    "stage": "unknown",
                }

                results.append(
                    {
                        "message_id":
                            reply["message_id"],

                        "result":
                            result,
                    }
                )

                continue

            results.append(
                {
                    "message_id":
                        reply["message_id"],

                    "result":
                        result,
                }
            )

            # Mark the Gmail message only after its actual business
            # workflow completed successfully.
            if result.get("success"):
                mark_message_processed(
                    reply["message_id"]
                )
            else:
                print(
                    "Message was NOT marked as processed because "
                    "the workflow did not succeed."
                )

        except Exception as error:

            print()
            print(
                "REPLY PROCESSING ERROR:"
            )

            print(
                str(error)
            )

            results.append(
                {
                    "message_id":
                        reply["message_id"],

                    "result":
                        {
                            "success": False,
                            "error":
                                str(error),
                        },
                }
            )

    print()
    print("=" * 60)
    print(
        "REPLY PIPELINE COMPLETED"
    )
    print(
        "New candidate replies are now filtered from "
        "automated/system emails and duplicate Gmail messages."
    )
    print("=" * 60)

    return results


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    process_candidate_replies()