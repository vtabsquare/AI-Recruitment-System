import os

from email_service import (
    send_shortlisted_email,
    send_rejection_email
)


# ============================================================
# TEST RECIPIENT
# ============================================================

TEST_EMAIL = os.getenv(
    "BREVO_TEST_RECIPIENT",
    ""
).strip()


if not TEST_EMAIL:
    raise RuntimeError(
        "BREVO_TEST_RECIPIENT is not configured."
    )


# ============================================================
# TEST START
# ============================================================

print("=" * 60)
print("VTAB SQUARE BREVO EMAIL TEST")
print("=" * 60)

print()
print("Test recipient:", TEST_EMAIL)


# ============================================================
# TEST 1: SHORTLISTED EMAIL
# ============================================================

print()
print("Sending shortlisted email...")

result = send_shortlisted_email(
    candidate_name="Vasanth Kumar T",
    recipient_email=TEST_EMAIL,
    job_role="Data Analyst",
    application_id="TEST-VTAB-001"
)

print()
print("SHORTLISTED EMAIL SENT")
print()
print("Brevo response:")
print(result)


# ============================================================
# TEST 2: REJECTION EMAIL
# ============================================================

print()
print("Sending rejection email...")

result = send_rejection_email(
    candidate_name="Test Candidate",
    recipient_email=TEST_EMAIL,
    job_role="Data Analyst",
    application_id="TEST-VTAB-002"
)

print()
print("REJECTION EMAIL SENT")
print()
print("Brevo response:")
print(result)


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 60)
print("BREVO EMAIL TEST COMPLETED")
print("=" * 60)