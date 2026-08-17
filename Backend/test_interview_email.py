from datetime import datetime, timedelta, timezone

from interview_email_service import (
    send_interview_confirmation
)


# ============================================================
# TEST INTERVIEW EMAIL
# ============================================================

print()
print("=" * 60)
print("VTAB SQUARE INTERVIEW CONFIRMATION EMAIL TEST")
print("=" * 60)


# ------------------------------------------------------------
# Test candidate
# ------------------------------------------------------------

candidate_email = (
    "vitabsquare@gmail.com"
)

candidate_name = (
    "VASANTH KUMAR T"
)


# ------------------------------------------------------------
# Test interview time
# ------------------------------------------------------------

IST = timezone(
    timedelta(
        hours=5,
        minutes=30
    )
)

start_time = datetime(
    2026,
    8,
    9,
    16,
    0,
    tzinfo=IST
)

end_time = (
    start_time
    + timedelta(
        minutes=30
    )
)


# ------------------------------------------------------------
# Test Calendar result
# ------------------------------------------------------------

interview_result = {

    "start_time":
        start_time,

    "end_time":
        end_time,

    "meet_link":
        "https://meet.google.com/yuu-yowt-hkh"

}


# ============================================================
# SEND EMAIL
# ============================================================

print()
print(
    "Sending interview confirmation..."
)

result = send_interview_confirmation(
    candidate_email=
        candidate_email,

    candidate_name=
        candidate_name,

    interview_result=
        interview_result
)


# ============================================================
# RESULT
# ============================================================

print()
print("=" * 60)
print("EMAIL TEST COMPLETED")
print("=" * 60)

print()

print(
    "Recipient:",
    result["recipient"]
)

print(
    "Message ID:",
    result["message_id"]
)

print(
    "Interview Date:",
    result["interview_date"]
)

print(
    "Interview Time:",
    result["interview_time"]
)

print(
    "Meet Link:",
    result["meet_link"]
)

print()