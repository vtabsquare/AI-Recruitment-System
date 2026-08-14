from datetime import datetime, timezone

from supabase_db import supabase


# ============================================================
# CURRENT UTC TIMESTAMP
# ============================================================

def get_current_utc():
    """
    Return the current UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# VALIDATE SCORE
# ============================================================

def validate_score(
    score,
    field_name
):
    """
    Validate an interview score from 1 to 5.
    """

    try:

        score = int(score)

    except (TypeError, ValueError):

        raise ValueError(
            f"{field_name} must be a number from 1 to 5."
        )

    if score < 1 or score > 5:

        raise ValueError(
            f"{field_name} must be between 1 and 5."
        )

    return score


# ============================================================
# VALIDATE RECOMMENDATION
# ============================================================

def validate_recommendation(
    recommendation
):
    """
    Validate the reviewer's recommendation.
    """

    if not recommendation:

        raise ValueError(
            "Reviewer recommendation is required."
        )

    recommendation = (
        str(recommendation)
        .strip()
        .lower()
    )

    rec_map = {
        "approve": "selected",
        "approved": "selected",
        "select": "selected",
        "selected": "selected",
        "reject": "rejected",
        "rejected": "rejected",
        "next_round": "next_round",
        "next round": "next_round",
    }

    if recommendation not in rec_map:
        raise ValueError(
            "Recommendation must be one of: "
            "selected, rejected, next_round."
        )

    return rec_map[recommendation]


# ============================================================
# GET INTERVIEW FOR APPLICATION
# ============================================================

def get_interview_by_application(
    application_id
):
    """
    Find the interview record belonging to an application.
    """

    if not application_id:

        raise ValueError(
            "Application ID is required."
        )

    response = (
        supabase
        .table("interviews")
        .select("*")
        .eq(
            "application_id",
            application_id
        )
        .order(
            "created_at",
            desc=True
        )
        .limit(1)
        .execute()
    )

    if not response.data:

        return None

    return response.data[0]


# ============================================================
# SAVE INTERVIEW FEEDBACK
# ============================================================

def save_interview_feedback(
    application_id,
    reviewer_name,
    technical_skills,
    communication,
    problem_solving,
    overall_performance,
    recommendation,
    reviewer_comments=""
):
    """
    Save reviewer feedback against the actual interview
    belonging to the application.
    """

    if not application_id:

        raise ValueError(
            "Application ID is required."
        )

    if not reviewer_name:

        raise ValueError(
            "Reviewer name is required."
        )

    # --------------------------------------------------------
    # Find interview
    # --------------------------------------------------------

    interview = get_interview_by_application(
        application_id
    )

    if not interview:

        raise ValueError(
            "No interview record was found for "
            f"application {application_id}."
        )

    interview_id = interview["id"]

    # --------------------------------------------------------
    # Validate scores
    # --------------------------------------------------------

    technical_skills = validate_score(
        technical_skills,
        "Technical skills"
    )

    communication = validate_score(
        communication,
        "Communication"
    )

    problem_solving = validate_score(
        problem_solving,
        "Problem solving"
    )

    overall_performance = validate_score(
        overall_performance,
        "Overall performance"
    )

    # --------------------------------------------------------
    # Validate recommendation
    # --------------------------------------------------------

    recommendation = validate_recommendation(
        recommendation
    )

    # --------------------------------------------------------
    # Prepare feedback
    # --------------------------------------------------------

    feedback_data = {

        "interview_id":
            interview_id,

        "application_id":
            application_id,

        "reviewer_name":
            str(
                reviewer_name
            ).strip(),

        "technical_skills":
            technical_skills,

        "communication":
            communication,

        "problem_solving":
            problem_solving,

        "overall_performance":
            overall_performance,

        "recommendation":
            recommendation,

        "reviewer_comments":
            str(
                reviewer_comments or ""
            ).strip(),

        "updated_at":
            get_current_utc()

    }

    # --------------------------------------------------------
    # Save feedback
    # --------------------------------------------------------

    response = (
        supabase
        .table("interview_feedback")
        .upsert(
            feedback_data,
            on_conflict="interview_id"
        )
        .execute()
    )

    if not response.data:

        raise Exception(
            "Failed to save interview feedback."
        )

    return response.data[0]


# ============================================================
# GET INTERVIEW FEEDBACK
# ============================================================

def get_interview_feedback(
    application_id
):
    """
    Retrieve feedback using the application ID.
    """

    if not application_id:

        raise ValueError(
            "Application ID is required."
        )

    response = (
        supabase
        .table("interview_feedback")
        .select("*")
        .eq(
            "application_id",
            application_id
        )
        .limit(1)
        .execute()
    )

    if not response.data:

        return None

    return response.data[0]


# ============================================================
# MARK INTERVIEW COMPLETED
# ============================================================

def mark_interview_completed(
    application_id
):
    """
    Mark the interview as completed and update the
    application status.
    """

    if not application_id:

        raise ValueError(
            "Application ID is required."
        )

    # --------------------------------------------------------
    # Update interview record
    # --------------------------------------------------------

    interview = get_interview_by_application(
        application_id
    )

    if not interview:

        raise ValueError(
            "No interview record was found for "
            f"application {application_id}."
        )

    interview_response = (
        supabase
        .table("interviews")
        .update({

            "status":
                "completed",

            "completed_at":
                get_current_utc()

        })
        .eq(
            "id",
            interview["id"]
        )
        .execute()
    )

    if not interview_response.data:

        raise Exception(
            "Failed to mark interview as completed."
        )

    # --------------------------------------------------------
    # Update application
    # --------------------------------------------------------

    application_response = (
        supabase
        .table("applications")
        .update({

            "status":
                "interview_completed"

        })
        .eq(
            "id",
            application_id
        )
        .execute()
    )

    if not application_response.data:

        raise Exception(
            "Failed to mark application as "
            "interview_completed."
        )

    return application_response.data[0]