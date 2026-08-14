from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


# ============================================================
# SUPABASE CLIENT
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def get_supabase():
    """
    Returns the Supabase client.
    """
    return supabase


# ============================================================
# JOB ROLE FUNCTIONS
# ============================================================

def get_job_roles():
    """
    Fetch all active job roles from Supabase.
    """

    response = (
        supabase
        .table("job_roles")
        .select(
            "id, role_name, minimum_cgpa, required_skill_count"
        )
        .eq("is_active", True)
        .execute()
    )

    return response.data


def get_job_role(role_name):
    """
    Fetch one active job role and its required skills.
    """

    role_response = (
        supabase
        .table("job_roles")
        .select(
            "id, role_name, minimum_cgpa, "
            "required_skill_count, minimum_skill_matches"
        )
        .eq("role_name", role_name)
        .eq("is_active", True)
        .single()
        .execute()
    )

    role = role_response.data

    if not role:
        return None

    skills_response = (
        supabase
        .table("job_role_skills")
        .select(
            "skill_name, is_required"
        )
        .eq("job_role_id", role["id"])
        .execute()
    )

    role["required_skills"] = [
        skill["skill_name"]
        for skill in skills_response.data
        if skill["is_required"]
    ]

    return role


# ============================================================
# CANDIDATE FUNCTIONS
# ============================================================

def create_candidate(
    candidate_name,
    email,
    phone_number=None
):
    """
    Create a new candidate in Supabase.

    The candidates.email column has a UNIQUE constraint,
    so duplicate email addresses are rejected by the database.
    """

    candidate_data = {
        "candidate_name": candidate_name,
        "email": email,
        "phone_number": phone_number
    }

    response = (
        supabase
        .table("candidates")
        .insert(candidate_data)
        .execute()
    )

    if not response.data:
        raise Exception(
            "Failed to create candidate."
        )

    return response.data[0]


def get_candidate_by_email(email):
    """
    Find an existing candidate using their email address.
    """

    response = (
        supabase
        .table("candidates")
        .select(
            "id, candidate_name, email, phone_number, "
            "created_at, updated_at"
        )
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def update_candidate(
    candidate_id,
    candidate_name,
    email,
    phone_number=None
):
    """
    Update an existing candidate.
    """

    candidate_data = {
        "candidate_name": candidate_name,
        "email": email,
        "phone_number": phone_number
    }

    response = (
        supabase
        .table("candidates")
        .update(candidate_data)
        .eq("id", candidate_id)
        .execute()
    )

    if not response.data:
        raise Exception(
            "Failed to update candidate."
        )

    return response.data[0]


# ============================================================
# APPLICATION FUNCTIONS
# ============================================================

def create_application(
    candidate_id,
    job_role_id
):
    """
    Create a new application for a candidate.

    Generates a VTAB application ID and starts the
    application in the 'processing' state.
    """

    import uuid
    from id_generator import generate_application_id

    application_data = {
        "application_id": generate_application_id(),
        "candidate_id": candidate_id,
        "job_role_id": job_role_id,
        "status": "processing"
    }

    response = (
        supabase
        .table("applications")
        .insert(application_data)
        .execute()
    )

    if not response.data:
        raise Exception(
            "Failed to create application."
        )

    return response.data[0]


def get_application(application_id):
    """
    Fetch an application by its database UUID.
    """

    response = (
        supabase
        .table("applications")
        .select("*")
        .eq("id", application_id)
        .single()
        .execute()
    )

    return response.data


def update_application_status(
    application_id,
    status
):
    """
    Update the status of an application.
    """

    valid_statuses = {
        "processing",
        "shortlisted",
        "rejected",
        "interview_pending",
        "interview_scheduled",
        "interview_completed",
        "documents_pending",
        "documents_verifying",
        "onboarding",
        "onboarded",
        "closed"
    }

    if status not in valid_statuses:
        raise ValueError(
            f"Invalid application status: {status}"
        )

    response = (
        supabase
        .table("applications")
        .update({
            "status": status
        })
        .eq("id", application_id)
        .execute()
    )

    if not response.data:
        raise Exception(
            f"Failed to update application status "
            f"to '{status}'."
        )

    return response.data[0]