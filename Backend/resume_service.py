from datetime import datetime, timezone

from supabase_db import supabase


# ============================================================
# CURRENT UTC TIMESTAMP
# ============================================================

def get_current_utc():
    """
    Return the current UTC timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# RESUME SERVICE
# ============================================================

def save_resume(
    application_id,
    file_name,
    extracted_text,
    storage_path=None
):
    """
    Save or update the resume record for an application.

    The resumes table does not currently have a unique
    constraint on application_id, so we manually check
    whether a record already exists.
    """

    resume_data = {
        "application_id": application_id,
        "file_name": file_name,
        "storage_path": storage_path,
        "extracted_text": extracted_text
    }

    # --------------------------------------------------------
    # Check whether a resume already exists
    # --------------------------------------------------------

    existing_response = (
        supabase
        .table("resumes")
        .select("id")
        .eq("application_id", application_id)
        .limit(1)
        .execute()
    )

    existing_records = existing_response.data or []

    # --------------------------------------------------------
    # Update existing resume
    # --------------------------------------------------------

    if existing_records:

        resume_id = existing_records[0]["id"]

        response = (
            supabase
            .table("resumes")
            .update(resume_data)
            .eq("id", resume_id)
            .execute()
        )

    # --------------------------------------------------------
    # Create new resume
    # --------------------------------------------------------

    else:

        response = (
            supabase
            .table("resumes")
            .insert(resume_data)
            .execute()
        )

    if not response.data:
        raise Exception("Failed to save resume.")

    return response.data[0]


# ============================================================
# RESUME ANALYSIS
# ============================================================

def save_resume_analysis(application_id, analysis):
    """
    Save or update Gemini's structured resume analysis.
    """

    analysis_data = {
        "application_id": application_id,
        "degree": analysis.get("degree"),
        "cgpa": analysis.get("cgpa"),
        "skills": analysis.get("skills", []),
        "experience": analysis.get("experience", []),
        "education": analysis.get("education", []),
        "strengths": analysis.get("strengths", []),
        "weaknesses": analysis.get("weaknesses", []),
        "raw_analysis": analysis,
        "analyzed_at": get_current_utc()
    }

    response = (
        supabase
        .table("resume_analysis")
        .upsert(
            analysis_data,
            on_conflict="application_id"
        )
        .execute()
    )

    if not response.data:
        raise Exception("Failed to save resume analysis.")

    return response.data[0]