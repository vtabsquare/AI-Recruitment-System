import json

from google import genai

from config import GEMINI_API_KEY
from supabase_db import supabase


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# DATABASE DECISION MAPPING
# ============================================================
#
# The current Supabase database rejects "selected" in the
# interview_feedback.final_decision column because that column
# uses the existing PostgreSQL enum "ai_decision".
#
# Keep the user-facing interview decision as:
#   selected / rejected / next_round
#
# Store the compatible current database values:
#   selected   -> shortlisted
#   rejected   -> rejected
#   next_round -> needs_review
#
# This fixes the current database error without changing the
# database schema.
# ============================================================

DATABASE_DECISION_MAP = {
    "selected": "shortlisted",
    "rejected": "rejected",
    "next_round": "shortlisted"
}


# ============================================================
# GET INTERVIEW FEEDBACK
# ============================================================

def get_feedback_for_application(application_id):
    if not application_id:
        raise ValueError("Application ID is required.")

    response = (
        supabase
        .table("interview_feedback")
        .select("*")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise ValueError(
            "No interview feedback was found for "
            f"application {application_id}."
        )

    return response.data[0]


# ============================================================
# CLEAN GEMINI JSON
# ============================================================

def clean_json_response(text):
    if not text:
        raise ValueError("Gemini returned an empty response.")

    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print()
        print("Invalid JSON returned by Gemini:")
        print(text)
        raise ValueError(
            "Gemini did not return valid JSON."
        ) from exc


# ============================================================
# VALIDATE AI DECISION
# ============================================================

def validate_decision(decision):
    decision = str(decision or "").strip().lower()

    valid_decisions = {
        "selected",
        "rejected",
        "next_round"
    }

    if decision not in valid_decisions:
        raise ValueError(
            "AI returned an invalid interview decision: "
            f"{decision}"
        )

    return decision


# ============================================================
# AI INTERVIEW EVALUATION
# ============================================================

def evaluate_interview_feedback(application_id):
    feedback = get_feedback_for_application(
        application_id
    )

    technical = feedback.get("technical_skills")
    communication = feedback.get("communication")
    problem_solving = feedback.get("problem_solving")
    overall = feedback.get("overall_performance")

    recommendation = str(
        feedback.get("recommendation", "")
    ).strip().lower()

    comments = str(
        feedback.get("reviewer_comments", "") or ""
    ).strip()

    reviewer_name = str(
        feedback.get("reviewer_name", "Interviewer")
    ).strip()

    # --------------------------------------------------------
    # Validate scores
    # --------------------------------------------------------

    scores = {
        "technical_skills": technical,
        "communication": communication,
        "problem_solving": problem_solving,
        "overall_performance": overall
    }

    for field_name, score in scores.items():
        try:
            numeric_score = int(score)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be a number from 1 to 5."
            )

        if numeric_score < 1 or numeric_score > 5:
            raise ValueError(
                f"{field_name} must be between 1 and 5."
            )

    if not comments:
        raise ValueError(
            "Interviewer comments are required."
        )

    rec_map = {
        "selected": "selected",
        "select": "selected",
        "approve": "selected",
        "approved": "selected",
        "rejected": "rejected",
        "reject": "rejected",
        "next_round": "next_round",
        "next round": "next_round",
    }

    if recommendation not in rec_map:
        raise ValueError(
            "Interviewer recommendation must be "
            "selected, rejected, or next_round."
        )

    recommendation = rec_map[recommendation]

    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are the Interview Evaluation AI for VTAB Square.

Evaluate interviewer-submitted feedback for a candidate who has
completed an interview.

IMPORTANT RULES:

1. Use ONLY the interviewer feedback supplied below.
2. Do not invent interview events, skills, behavior, or facts.
3. Do not evaluate the candidate from their resume.
4. Validate whether the interviewer's recommendation is supported
   by the scores and written comments.
5. Consider all four scores, the recommendation, and comments.
6. If the evidence is contradictory or insufficient for a clear
   final decision, return "next_round".
7. The final decision MUST be exactly one of:
   "selected", "rejected", "next_round".

Scoring:
1 = Poor
2 = Needs Improvement
3 = Satisfactory
4 = Good
5 = Excellent

Interviewer:
{reviewer_name}

Technical Skills:
{technical}/5

Communication:
{communication}/5

Problem Solving:
{problem_solving}/5

Overall Performance:
{overall}/5

Interviewer's Recommendation:
{recommendation}

Interviewer's Comments:
{comments}

Return ONLY valid JSON.

Use exactly this structure:

{{
    "final_decision": "selected",
    "confidence": "high",
    "reason": "",
    "feedback_consistent": true
}}
"""

    print()
    print("Sending interview feedback to Gemini...")

    response = (
        client
        .models
        .generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )
    )

    if not response or not response.text:
        raise ValueError(
            "Gemini returned an empty interview evaluation."
        )

    # --------------------------------------------------------
    # Parse Gemini result
    # --------------------------------------------------------

    result = clean_json_response(
        response.text
    )

    final_decision = validate_decision(
        result.get("final_decision")
    )

    confidence = str(
        result.get("confidence", "medium")
    ).strip().lower()

    if confidence not in {
        "low",
        "medium",
        "high"
    }:
        confidence = "medium"

    reason = str(
        result.get("reason", "")
    ).strip()

    if not reason:
        raise ValueError(
            "Gemini did not provide an evaluation reason."
        )

    feedback_consistent = bool(
        result.get("feedback_consistent", False)
    )

    # --------------------------------------------------------
    # Map to the current database enum
    # --------------------------------------------------------

    database_decision = DATABASE_DECISION_MAP[
        final_decision
    ]

    print()
    print("AI decision:", final_decision)
    print("Database decision:", database_decision)

    # --------------------------------------------------------
    # Save final decision
    # --------------------------------------------------------

    saved = (
        supabase
        .table("interview_feedback")
        .update({
            "final_decision": database_decision
        })
        .eq(
            "id",
            feedback["id"]
        )
        .execute()
    )

    if not saved.data:
        raise Exception(
            "Failed to save the AI interview decision."
        )

    evaluation = {
        "application_id": application_id,
        "feedback_id": feedback["id"],
        "final_decision": final_decision,
        "database_decision": database_decision,
        "confidence": confidence,
        "reason": reason,
        "feedback_consistent": feedback_consistent
    }

    print()
    print("=" * 60)
    print("AI INTERVIEW EVALUATION")
    print("=" * 60)
    print("Application:", application_id)
    print("Interviewer:", reviewer_name)
    print("Final Decision:", final_decision)
    print("Confidence:", confidence)
    print("Feedback Consistent:", feedback_consistent)
    print("Reason:", reason)
    print("=" * 60)

    return evaluation


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("VTAB SQUARE AI INTERVIEW EVALUATION TEST")
    print("=" * 60)

    application_id = input(
        "\nEnter application UUID: "
    ).strip()

    try:
        result = evaluate_interview_feedback(
            application_id
        )

        print()
        print("FINAL RESULT")
        print("=" * 60)
        print(
            json.dumps(
                result,
                indent=4
            )
        )

        print()
        print(
            "AI interview evaluation completed successfully."
        )

    except Exception as error:

        print()
        print("=" * 60)
        print("INTERVIEW EVALUATION ERROR")
        print("=" * 60)

        print(type(error).__name__)
        print(str(error))

        raise