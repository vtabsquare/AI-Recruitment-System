from resume_reader import extract_resume_text
from ai_analyzer import analyze_resume
from supabase_db import get_job_role
from evaluation_service import evaluate_candidate


print("Reading resume...")

resume_text = extract_resume_text("resume.pdf")

print("Resume loaded successfully.")


print("\nAnalyzing resume with Gemini...")

resume_analysis = analyze_resume(resume_text)

print("\nRESUME ANALYSIS:")
print(resume_analysis)


print("\nGetting Data Analyst requirements...")

role = get_job_role("Data Analyst")

print(role)


print("\nEvaluating candidate...")

result = evaluate_candidate(
    "b5499d4e-e988-43e3-81d7-c3b571be5958",
    resume_analysis,
    role
)


print("\nFINAL AI EVALUATION:")
print(result)