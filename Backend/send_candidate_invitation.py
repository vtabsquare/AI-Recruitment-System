import sys
from email_service import send_shortlisted_email

CANDIDATE_NAME = "Mohamed Yasin"
RECIPIENT_EMAIL = "massyaseen824@gmail.com"
JOB_ROLE = "Data Analyst"
APPLICATION_ID = "VTAB-2026-7324"

print(f"Sending shortlisted email to {RECIPIENT_EMAIL}...")
try:
    response = send_shortlisted_email(
        candidate_name=CANDIDATE_NAME,
        recipient_email=RECIPIENT_EMAIL,
        job_role=JOB_ROLE,
        application_id=APPLICATION_ID
    )
    print("SUCCESS! Shortlisted email sent successfully.")
    print("Brevo response:", response)
except Exception as e:
    print("Failed to send email:")
    print(e)
