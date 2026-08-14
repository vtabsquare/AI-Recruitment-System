from pathlib import Path
import shutil
import re

APP = Path(__file__).resolve().parent / "app.py"

if not APP.exists():
    raise SystemExit(f"ERROR: {APP} was not found.")

text = APP.read_text(encoding="utf-8")

backup = APP.with_name("app.py.backup_before_status_fix")
shutil.copy2(APP, backup)

# Fix manager decision -> real application_status enum.
text = text.replace('"approve": "manager_approved"', '"approve": "interview_pending"')
text = text.replace('"approved": "manager_approved"', '"approved": "interview_pending"')
text = text.replace('"next_round": "next_round"', '"next_round": "interview_pending"')
text = text.replace('"next round": "next_round"', '"next round": "interview_pending"')

# Fix interview AI decision -> real application_status enum.
text = re.sub(
    r'new_application_status\s*=\s*"manager_approved"',
    'new_application_status = "documents_pending"',
    text
)
text = re.sub(
    r'new_application_status\s*=\s*"approved"',
    'new_application_status = "documents_pending"',
    text
)
text = re.sub(
    r'new_application_status\s*=\s*"selected"',
    'new_application_status = "documents_pending"',
    text
)
text = re.sub(
    r'new_application_status\s*=\s*"next_round"',
    'new_application_status = "interview_pending"',
    text
)

# Fix HR queue if the old invalid status set is still present.
text = re.sub(
    r'hr_statuses\s*=\s*\{"approved",\s*"selected",\s*"manager_approved"\}',
    'hr_statuses = {"documents_pending", "documents_verifying", "onboarding"}',
    text
)

APP.write_text(text, encoding="utf-8")

print("STATUS FIX APPLIED SUCCESSFULLY")
print(f"Updated: {APP}")
print(f"Backup:  {backup}")
print()
print("Expected interview result:")
print('New status: documents_pending')
print()
print("Now restart FastAPI with:")
print("python -m uvicorn app:app --reload --port 8000")