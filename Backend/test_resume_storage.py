from resume_reader import extract_resume_text
from ai_analyzer import analyze_resume
from resume_service import save_resume, save_resume_analysis


# ============================================================
# TEST APPLICATION
# ============================================================

APPLICATION_ID = "b5499d4e-e988-43e3-81d7-c3b571be5958"


# ============================================================
# 1. EXTRACT RESUME
# ============================================================

print("Reading resume...")

resume_text = extract_resume_text("resume.pdf")

print("Resume extracted successfully.")


# ============================================================
# 2. SAVE RESUME
# ============================================================

print("\nSaving resume to Supabase...")

resume_record = save_resume(
    application_id=APPLICATION_ID,
    file_name="resume.pdf",
    extracted_text=resume_text
)

print("\nRESUME RECORD:")
print(resume_record)


# ============================================================
# 3. ANALYZE RESUME WITH GEMINI
# ============================================================

print("\nAnalyzing resume with Gemini...")

analysis = analyze_resume(resume_text)

print("\nGEMINI ANALYSIS:")
print(analysis)


# ============================================================
# 4. SAVE GEMINI ANALYSIS
# ============================================================

print("\nSaving resume analysis to Supabase...")

analysis_record = save_resume_analysis(
    application_id=APPLICATION_ID,
    analysis=analysis
)

print("\nRESUME ANALYSIS RECORD:")
print(analysis_record)


# ============================================================
# COMPLETE
# ============================================================

print("\n========================================")
print("RESUME STORAGE TEST COMPLETED")
print("========================================")