from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from interview_feedback_service import (
    save_interview_feedback
)

from interview_ai_evaluator import (
    evaluate_interview_feedback
)

from interview_decision_email_service import (
    send_final_interview_decision_email
)

from supabase_db import supabase


# ============================================================
# VTAB SQUARE FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="VTAB Square AI Recruitment API",
    version="1.0.0"
)


# ============================================================
# INTERVIEW FEEDBACK REQUEST
# ============================================================

class InterviewFeedbackRequest(BaseModel):

    application_id: str = Field(
        ...,
        min_length=1
    )

    reviewer_name: str = Field(
        ...,
        min_length=1
    )

    technical_skills: int = Field(
        ...,
        ge=1,
        le=5
    )

    communication: int = Field(
        ...,
        ge=1,
        le=5
    )

    problem_solving: int = Field(
        ...,
        ge=1,
        le=5
    )

    overall_performance: int = Field(
        ...,
        ge=1,
        le=5
    )

    recommendation: str = Field(
        ...,
        min_length=1
    )

    reviewer_comments: Optional[str] = ""


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "running",
        "service": "VTAB Square AI Recruitment API"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# GET EXISTING FEEDBACK
# ============================================================

def get_existing_feedback(application_id):
    """
    Get the latest interview feedback for an application.
    """

    response = (
        supabase
        .table("interview_feedback")
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
# SUBMIT INTERVIEW FEEDBACK
# ============================================================

@app.post(
    "/api/interview-feedback"
)
def submit_interview_feedback(
    feedback: InterviewFeedbackRequest
):

    try:

        # ====================================================
        # STEP 1
        # Save interviewer feedback
        # ====================================================

        saved_feedback = (
            save_interview_feedback(

                application_id=
                    feedback.application_id,

                reviewer_name=
                    feedback.reviewer_name,

                technical_skills=
                    feedback.technical_skills,

                communication=
                    feedback.communication,

                problem_solving=
                    feedback.problem_solving,

                overall_performance=
                    feedback.overall_performance,

                recommendation=
                    feedback.recommendation,

                reviewer_comments=
                    feedback.reviewer_comments or ""
            )
        )

        # ====================================================
        # STEP 2
        # AI EVALUATION
        # ====================================================

        print()
        print("=" * 60)
        print("STARTING AI INTERVIEW EVALUATION")
        print("=" * 60)

        ai_result = (
            evaluate_interview_feedback(
                feedback.application_id
            )
        )

        final_decision = (
            ai_result["final_decision"]
        )

        # ====================================================
        # STEP 3
        # SEND FINAL CANDIDATE EMAIL
        # ====================================================

        print()
        print("=" * 60)
        print("PROCESSING FINAL CANDIDATE NOTIFICATION")
        print("=" * 60)

        email_result = (
            send_final_interview_decision_email(

                application_id=
                    feedback.application_id,

                final_decision=
                    final_decision
            )
        )

        # ====================================================
        # STEP 4
        # FINAL RESPONSE TO UI
        # ====================================================

        return {

            "success": True,

            "message":
                "Interview feedback processed successfully.",

            "feedback":
                saved_feedback,

            "ai_evaluation":
                ai_result,

            "email":
                email_result
        }

    # ========================================================
    # VALIDATION ERRORS
    # ========================================================

    except ValueError as error:

        raise HTTPException(

            status_code=400,

            detail=str(error)
        )

    # ========================================================
    # OTHER ERRORS
    # ========================================================

    except Exception as error:

        print()
        print("=" * 60)
        print("INTERVIEW FEEDBACK PROCESS ERROR")
        print("=" * 60)
        print(
            type(error).__name__
        )
        print(
            str(error)
        )

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "app:app",

        host="127.0.0.1",

        port=8000,

        reload=True
    )