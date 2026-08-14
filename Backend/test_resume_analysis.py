from resume_reader import extract_resume_text
from ai_analyzer import analyze_resume


print("Reading resume...")

resume_text = extract_resume_text("resume.pdf")

print("Resume loaded successfully.")
print()
print("Sending resume to Gemini...")
print()

result = analyze_resume(resume_text)

print()
print("# AI RESUME ANALYSIS")
print("====================")
print(result)

print()
print("# FINAL EMAIL")
print("====================")
print(result["email"])
print()
print("Email representation:", repr(result["email"]))