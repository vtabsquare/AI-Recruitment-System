from application_service import create_candidate, create_application
from supabase_db import get_job_role


print("Getting Data Analyst role...")

role = get_job_role("Data Analyst")

print("\nRole:")
print(role)


print("\nCreating test candidate...")

candidate = create_candidate(
    "Test Candidate",
    "testcandidate@example.com",
    "9999999999"
)

print("\nCandidate:")
print(candidate)


print("\nCreating application...")

application = create_application(
    candidate["id"],
    role["id"]
)

print("\nApplication:")
print(application)