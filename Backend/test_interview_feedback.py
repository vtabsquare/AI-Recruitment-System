from interview_feedback_service import (
    save_interview_feedback,
    get_interview_feedback,
    mark_interview_completed
)


# ============================================================
# TEST SETTINGS
# ============================================================

# IMPORTANT:
# Replace this with the REAL application UUID from Supabase
# when testing with a real candidate.

TEST_APPLICATION_ID = "8b91f3cf-31e8-4a3e-8ba9-dade16c25864"


REVIEWER_NAME = "VTAB Square Interview Reviewer"

TECHNICAL_SKILLS = 4
COMMUNICATION = 4
PROBLEM_SOLVING = 5
OVERALL_PERFORMANCE = 4

RECOMMENDATION = "selected"

REVIEWER_COMMENTS = (
    "Candidate demonstrated strong technical knowledge, "
    "good communication, and strong problem-solving ability."
)


# ============================================================
# TEST
# ============================================================

print()
print("=" * 60)
print("VTAB SQUARE INTERVIEW FEEDBACK TEST")
print("=" * 60)


if not TEST_APPLICATION_ID:

    print()
    print(
        "TEST_APPLICATION_ID is empty."
    )

    print()
    print(
        "The feedback service is ready, but we need "
        "the application UUID from Supabase before "
        "saving a real feedback record."
    )

    print()
    print("=" * 60)

else:

    print()
    print(
        "[1/3] Saving reviewer feedback..."
    )

    feedback = save_interview_feedback(

        application_id=
            TEST_APPLICATION_ID,

        reviewer_name=
            REVIEWER_NAME,

        technical_skills=
            TECHNICAL_SKILLS,

        communication=
            COMMUNICATION,

        problem_solving=
            PROBLEM_SOLVING,

        overall_performance=
            OVERALL_PERFORMANCE,

        recommendation=
            RECOMMENDATION,

        reviewer_comments=
            REVIEWER_COMMENTS
    )

    print()
    print(
        "Feedback saved successfully."
    )

    print(
        feedback
    )

    print()
    print(
        "[2/3] Reading saved feedback..."
    )

    saved_feedback = get_interview_feedback(
        TEST_APPLICATION_ID
    )

    print()
    print(
        "Saved feedback:"
    )

    print(
        saved_feedback
    )

    print()
    print(
        "[3/3] Marking interview as completed..."
    )

    application = mark_interview_completed(
        TEST_APPLICATION_ID
    )

    print()
    print(
        "Application status updated:"
    )

    print(
        application
    )

    print()
    print("=" * 60)
    print(
        "INTERVIEW FEEDBACK TEST COMPLETED"
    )
    print("=" * 60)