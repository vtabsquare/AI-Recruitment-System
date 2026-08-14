from resume_reader import extract_resume_text
from ai_analyzer import analyze_resume
from email_sender import send_email

resume_text = extract_resume_text("resume.pdf")

print("Resume Loaded Successfully\n")

result = analyze_resume(resume_text)

print(result)

candidate_name = result["candidate_name"]
candidate_email = result["email"]
decision = result["decision"]

print(f"\nDecision : {decision}")

send_email(
    candidate_name,
    candidate_email,
    decision
)