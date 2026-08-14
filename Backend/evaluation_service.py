from datetime import datetime, timezone

from supabase_db import supabase


# ============================================================
# SKILL NORMALIZATION
# ============================================================

SKILL_ALIASES = {
    "microsoft excel": "excel",
    "excel": "excel",

    "statistical analysis": "statistics",
    "statistics": "statistics",

    "power bi": "power bi",
    "python": "python",
    "sql": "sql",
}


def normalize_skill(skill):
    """
    Normalize a skill name before comparison.
    """

    if not isinstance(skill, str):
        return ""

    skill = skill.strip().lower()

    return SKILL_ALIASES.get(skill, skill)


# ============================================================
# CURRENT UTC TIMESTAMP
# ============================================================

def get_current_utc():
    """
    Return the current UTC timestamp.
    """

    return datetime.now(timezone.utc).isoformat()


# ============================================================
# CANDIDATE EVALUATION
# ============================================================

def evaluate_candidate(application_id, resume_analysis, job_role):
    """
    Evaluate a candidate using the recruitment rules
    stored in Supabase.
    """

    # --------------------------------------------------------
    # 1. Get CGPA
    # --------------------------------------------------------

    cgpa = resume_analysis.get("cgpa")

    minimum_cgpa = float(job_role["minimum_cgpa"])

    if cgpa is None:
        cgpa_eligible = False
    else:
        cgpa_eligible = float(cgpa) >= minimum_cgpa

    # --------------------------------------------------------
    # 2. Get candidate skills
    # --------------------------------------------------------

    candidate_skills = resume_analysis.get("skills", [])

    candidate_skills_normalized = {
        normalize_skill(skill)
        for skill in candidate_skills
        if isinstance(skill, str)
    }

    # --------------------------------------------------------
    # 3. Get required skills
    # --------------------------------------------------------

    required_skills = job_role.get("required_skills", [])

    matched_skills = []
    missing_skills = []

    for skill in required_skills:

        if normalize_skill(skill) in candidate_skills_normalized:
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)

    # --------------------------------------------------------
    # 4. Check minimum skill requirement
    # --------------------------------------------------------

    minimum_skill_matches = int(
        job_role["minimum_skill_matches"]
    )

    skills_eligible = (
        len(matched_skills) >= minimum_skill_matches
    )

    # --------------------------------------------------------
    # 5. Final decision
    # --------------------------------------------------------

    overall_eligible = (
        cgpa_eligible
        and skills_eligible
    )

    if overall_eligible:
        decision = "shortlisted"
    else:
        decision = "rejected"

    # --------------------------------------------------------
    # 6. Generate reason
    # --------------------------------------------------------

    if overall_eligible:

        reason = (
            f"Candidate meets the minimum CGPA requirement "
            f"and matched {len(matched_skills)} of "
            f"{len(required_skills)} required skills."
        )

    else:

        reasons = []

        if not cgpa_eligible:

            if cgpa is None:
                reasons.append(
                    "CGPA was not available in the resume."
                )
            else:
                reasons.append(
                    f"CGPA {cgpa} is below the minimum "
                    f"requirement of {minimum_cgpa}."
                )

        if not skills_eligible:

            reasons.append(
                f"Candidate matched {len(matched_skills)} "
                f"of {len(required_skills)} required skills; "
                f"at least {minimum_skill_matches} are required."
            )

        reason = " ".join(reasons)

    # --------------------------------------------------------
    # 7. Save evaluation to Supabase
    # --------------------------------------------------------

    evaluation_data = {
        "application_id": application_id,
        "decision": decision,
        "reason": reason,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "cgpa_eligible": cgpa_eligible,
        "skills_eligible": skills_eligible,
        "overall_eligible": overall_eligible,
        "evaluated_at": get_current_utc()
    }

    response = (
        supabase
        .table("ai_evaluations")
        .upsert(
            evaluation_data,
            on_conflict="application_id"
        )
        .execute()
    )

    if not response.data:
        raise Exception("Failed to save AI evaluation.")

    return response.data[0]