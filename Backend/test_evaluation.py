from supabase_db import get_job_role
from evaluation_service import evaluate_candidate


# --------------------------------------------------------
# Get role requirements from Supabase
# --------------------------------------------------------

role = get_job_role("Data Analyst")

print("ROLE:")
print(role)


# --------------------------------------------------------
# Fake resume analysis
# --------------------------------------------------------

resume_analysis = {
    "cgpa": "7.4",

    "skills": [
        "Python",
        "SQL",
        "Excel",
        "Power BI"
    ]
}


# --------------------------------------------------------
# Evaluate candidate
# --------------------------------------------------------

result = evaluate_candidate(
    "b5499d4e-e988-43e3-81d7-c3b571be5958",
    resume_analysis,
    role
)


print("\nAI EVALUATION:")
print(result)