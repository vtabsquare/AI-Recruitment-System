from supabase_db import supabase


def create_candidate(name, email, phone=None):
    """
    Create a candidate in Supabase.
    If the email already exists, return the existing candidate.
    """

    existing = (
        supabase
        .table("candidates")
        .select("*")
        .eq("email", email)
        .execute()
    )

    if existing.data:
        return existing.data[0]

    response = (
        supabase
        .table("candidates")
        .insert({
            "candidate_name": name,
            "email": email,
            "phone_number": phone
        })
        .execute()
    )

    return response.data[0]


def create_application(candidate_id, job_role_id):
    """
    Create an application for a candidate and job role.
    """

    response = (
        supabase
        .table("applications")
        .insert({
            "candidate_id": candidate_id,
            "job_role_id": job_role_id
        })
        .execute()
    )

    return response.data[0]