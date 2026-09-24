"""
VTAB SQUARE
AI RECRUITMENT EMAIL PIPELINE

New project entry point:

Company Gmail
        ↓
Candidate application email
        ↓
Resume attachment
        ↓
Resume downloaded
        ↓
Existing recruitment system
        ↓
AI screening
        ↓
Candidate/Application
        ↓
Shortlisted / Rejected
        ↓
Candidate email
"""

import json
import traceback
from pathlib import Path


# ============================================================
# GMAIL MODULE
# ============================================================

import gmail_reader


# ============================================================
# BACKWARD COMPATIBILITY
#
# The existing interview/reply pipeline may still expect:
#
#     mark_message_as_processed()
#     is_message_processed()
#
# We add them to the already-loaded gmail_reader module
# BEFORE importing full_recruitment_system.
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent


PROCESSED_MESSAGES_FILE = (
    BASE_DIR
    / "processed_gmail_messages.json"
)

# Supabase import for persistent message ID tracking
from supabase_db import supabase as _supabase



def load_processed_message_ids():
    """
    Load reply-pipeline message IDs from Supabase.
    """
    try:
        response = (
            _supabase
            .table("processed_gmail_messages")
            .select("message_id")
            .eq("pipeline", "reply")
            .execute()
        )
        return {
            row["message_id"]
            for row in (response.data or [])
        }
    except Exception as err:
        print("[Reply] Could not load processed IDs from Supabase:", err)
        return set()


def save_processed_message_ids(message_ids):
    """
    No-op: saves done individually via upsert.
    Kept for backward compatibility.
    """
    pass


def mark_message_as_processed(message_id):
    """
    Record a reply message ID as processed in Supabase.
    """
    if not message_id:
        return
    try:
        _supabase.table("processed_gmail_messages").upsert(
            {
                "message_id": str(message_id),
                "pipeline": "reply",
            },
            on_conflict="message_id,pipeline"
        ).execute()
    except Exception as err:
        print("[Reply] Could not save processed ID to Supabase:", err)


def is_message_processed(message_id):
    """
    Check whether a reply message has already been processed.
    """
    if not message_id:
        return False
    try:
        response = (
            _supabase
            .table("processed_gmail_messages")
            .select("message_id")
            .eq("message_id", str(message_id))
            .eq("pipeline", "reply")
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as err:
        print("[Reply] Could not check processed ID in Supabase:", err)
        return False



# ============================================================
# INSTALL COMPATIBILITY FUNCTIONS
# ============================================================

if not hasattr(
    gmail_reader,
    "load_processed_message_ids"
):

    gmail_reader.load_processed_message_ids = (
        load_processed_message_ids
    )


if not hasattr(
    gmail_reader,
    "save_processed_message_ids"
):

    gmail_reader.save_processed_message_ids = (
        save_processed_message_ids
    )


if not hasattr(
    gmail_reader,
    "mark_message_as_processed"
):

    gmail_reader.mark_message_as_processed = (
        mark_message_as_processed
    )


if not hasattr(
    gmail_reader,
    "is_message_processed"
):

    gmail_reader.is_message_processed = (
        is_message_processed
    )


# ============================================================
# EXISTING RECRUITMENT SYSTEM
#
# IMPORTANT:
# This import comes AFTER the compatibility functions above.
#
# EMAIL FALLBACK FIX:
#
# The Gmail application already contains the candidate's real
# email address. Some resumes do not contain an email address.
# The old ai_analyzer.py rejected those resumes before Gemini
# analysis could continue.
#
# To preserve the existing project flow, we patch only the
# recruitment entry path here:
#
#   Resume email exists
#       -> existing ai_analyzer behavior is used
#
#   Resume email missing
#       -> Gemini still analyzes the resume
#       -> Gmail application email is used as the candidate email
#
# No database flow, AI evaluation flow, email flow, or reply
# pipeline flow is changed.
# ============================================================

import re
import ai_analyzer


_CURRENT_CANDIDATE_EMAIL = ""


def _extract_resume_email_fallback(text):
    """
    Extract an email from resume text when possible.

    This is intentionally conservative. The Gmail application
    email remains the authoritative fallback.
    """

    if not text:
        return ""

    match = re.search(
        r"[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}",
        str(text)
    )

    if not match:
        return ""

    return match.group(0).strip().lower()


def _analyze_resume_using_gemini_with_email_fallback(
    resume_text,
    candidate_email=None,
    *args,
    **kwargs
):
    """
    Compatibility wrapper around the existing Gemini analyzer.

    If the resume already contains an email, the original
    ai_analyzer.analyze_resume() function is used unchanged.

    If the resume has no email, Gemini still performs the same
    resume analysis and the Gmail application email is injected
    as the authoritative candidate email.
    """

    global _CURRENT_CANDIDATE_EMAIL

    if not resume_text:
        raise ValueError("Resume text is empty.")

    target_email = str(
        candidate_email or _CURRENT_CANDIDATE_EMAIL or ""
    ).strip().lower()

    resume_email = _extract_resume_email_fallback(
        resume_text
    ) or target_email

    # --------------------------------------------------------
    # NORMAL PATH
    #
    # Preserve the existing analyzer completely when the
    # resume already contains an email or an email was provided.
    # --------------------------------------------------------

    if resume_email:
        result = _ORIGINAL_ANALYZE_RESUME(
            resume_text,
            candidate_email=target_email or None,
            *args,
            **kwargs
        )

        # If the application was received via Gmail, the sender's email address
        # is the authoritative address where the candidate expects notifications and replies.
        if target_email:
            result["email"] = target_email

        return result

    # --------------------------------------------------------
    # FALLBACK PATH
    #
    # The resume has no email. Continue Gemini analysis instead
    # of failing. The Gmail sender/application email becomes
    # the authoritative candidate email.
    # --------------------------------------------------------

    candidate_email = target_email

    if not candidate_email:
        raise ValueError(
            "Candidate email was not available from the "
            "Gmail application."
        )

    prompt = f"""
You are an expert AI Recruitment Assistant for VTAB Square.

Analyze the uploaded resume.

Extract:

1. Candidate Name
2. Email Address, if present in the resume
3. Phone Number
4. Degree
5. CGPA
6. Technical Skills
7. Projects / Experience
8. Education
9. Strengths
10. Weaknesses

IMPORTANT:

Return ONLY valid JSON.

Do NOT use markdown.

Do NOT wrap JSON in a code block.

Do NOT make a recruitment decision.

Do NOT return:
- decision
- reason

Use exactly this structure:

{{
    "candidate_name": "",
    "email": "",
    "phone_number": "",
    "degree": "",
    "cgpa": null,
    "skills": [],
    "experience": [],
    "education": [],
    "strengths": [],
    "weaknesses": []
}}

If the resume does not contain an email address, leave
"email" as an empty string.

Resume:

{resume_text}
"""

    response = ai_analyzer.client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    if not response or not response.text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    text = response.text.strip()

    # --------------------------------------------------------
    # Remove accidental Markdown fences
    # --------------------------------------------------------

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    # --------------------------------------------------------
    # Parse Gemini JSON
    # --------------------------------------------------------

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        print(
            "Invalid JSON returned by Gemini:"
        )
        print(text)

        raise ValueError(
            "Gemini did not return valid JSON."
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "Gemini returned an invalid resume analysis structure."
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # The Gmail application email is authoritative when the
    # resume itself does not contain an email.
    # --------------------------------------------------------

    result["email"] = candidate_email

    print(
        "Resume did not contain an email."
    )

    print(
        "Using Gmail application email:",
        repr(candidate_email)
    )

    return result


# Keep a reference to the original implementation.
_ORIGINAL_ANALYZE_RESUME = (
    ai_analyzer.analyze_resume
)


# Replace the imported analyzer before full_recruitment_system
# imports recruitment_service. recruitment_service therefore
# receives the compatibility-safe analyzer without requiring
# changes to the existing recruitment flow.
ai_analyzer.analyze_resume = (
    _analyze_resume_using_gemini_with_email_fallback
)


from full_recruitment_system import (
    process_candidate
)


# ============================================================
# NEW GMAIL APPLICATION FUNCTIONS
# ============================================================

read_new_candidate_applications = (
    gmail_reader.read_new_candidate_applications
)


mark_application_email_processed = (
    gmail_reader.mark_application_email_processed
)


unmark_application_email_processed = (
    gmail_reader.unmark_application_email_processed
)


# ============================================================
# DEFAULT ROLE
# ============================================================

DEFAULT_JOB_ROLE = (
    "Data Analyst"
)


# ============================================================
# PROCESS ONE APPLICATION
# ============================================================

def process_application(
    application
):
    """
    Process one candidate application received
    through the company recruitment Gmail.
    """

    message_id = application.get(
        "message_id"
    )

    candidate_name = application.get(
        "candidate_name",
        "Candidate"
    )

    candidate_email = application.get(
        "candidate_email",
        ""
    )

    subject = application.get(
        "subject",
        ""
    )

    job_role = application.get(
        "job_role",
        DEFAULT_JOB_ROLE
    )

    resume_paths = application.get(
        "resume_paths",
        []
    )

    # --------------------------------------------------------
    # DISPLAY APPLICATION
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "NEW CANDIDATE APPLICATION"
    )

    print("=" * 60)

    print(
        "Candidate:",
        candidate_name
    )

    print(
        "Email:",
        candidate_email
    )

    print(
        "Subject:",
        subject
    )

    print(
        "Job role:",
        job_role
    )

    print(
        "Resume:",
        resume_paths
    )

    print("=" * 60)

    # --------------------------------------------------------
    # VALIDATE RESUME
    # --------------------------------------------------------

    if not resume_paths:

        raise ValueError(
            "No resume attachment was found "
            "in the candidate application."
        )

    results = []

    # --------------------------------------------------------
    # PROCESS RESUME
    # --------------------------------------------------------

    for resume_path in resume_paths:

        print()
        print(
            "-" * 60
        )

        print(
            "STARTING AI RECRUITMENT PIPELINE"
        )

        print(
            "-" * 60
        )

        print(
            "Resume:",
            resume_path
        )

        print(
            "Job role:",
            job_role
        )

        print()

        # ----------------------------------------------------
        # MARK APPLICATION EMAIL AS PROCESSED
        #
        # Do this BEFORE processing to prevent duplicate
        # runs if the 20-second poll interval triggers
        # while Gemini is still analyzing this resume.
        # ----------------------------------------------------

        if message_id:
            mark_application_email_processed(message_id)

        # ----------------------------------------------------
        # Existing recruitment system
        #
        # Store the Gmail application email before entering
        # the existing recruitment system. This allows the
        # compatibility analyzer above to use it only when
        # the resume itself has no email address.
        # ----------------------------------------------------

        global _CURRENT_CANDIDATE_EMAIL

        _CURRENT_CANDIDATE_EMAIL = str(
            candidate_email or ""
        ).strip().lower()

        try:
            result = process_candidate(
                resume_path,
                job_role,
                candidate_email=candidate_email,
                candidate_name=candidate_name
            )
        except Exception as e:
            print(f"Error processing candidate: {e}")
            result = {"error": str(e)}

        # Clear the temporary application context immediately
        # after the candidate has been processed.
        _CURRENT_CANDIDATE_EMAIL = ""

        if message_id and result.get("error"):
            try:
                unmark_application_email_processed(message_id)
            except Exception:
                pass

        results.append(
            result
        )

        print()
        print(
            "AI recruitment pipeline completed successfully."
        )

        print(
            "Result:",
            result
        )

        results.append(
            result
        )

        print()
        print(
            "AI recruitment pipeline completed."
        )

        print(
            "Result:",
            result
        )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)

    print(
        "VTAB SQUARE AI RECRUITMENT EMAIL PIPELINE"
    )

    print("=" * 60)

    print()
    print(
        "Connecting to company recruitment Gmail..."
    )

    print()

    # ========================================================
    # READ NEW APPLICATIONS
    # ========================================================

    try:

        applications = (
            read_new_candidate_applications(
                default_role=DEFAULT_JOB_ROLE
            )
        )

    except Exception as error:

        print()
        print("=" * 60)

        print(
            "GMAIL MONITOR ERROR"
        )

        print("=" * 60)

        print(
            "Error type:",
            type(error).__name__
        )

        print(
            "Error:",
            str(error)
        )

        print()

        traceback.print_exc()

        return

    # ========================================================
    # NO APPLICATIONS
    # ========================================================

    if not applications:

        print(
            "No new candidate applications found."
        )

        print()
        print(
            "Gmail check completed."
        )

        print("=" * 60)

        return

    # ========================================================
    # APPLICATIONS FOUND
    # ========================================================

    print(
        f"Found {len(applications)} "
        f"new candidate application(s)."
    )

    successful = 0
    failed = 0

    # ========================================================
    # PROCESS APPLICATIONS
    # ========================================================

    for index, application in enumerate(
        applications,
        start=1
    ):

        print()
        print()
        print(
            "#" * 60
        )

        print(
            f"PROCESSING APPLICATION {index}"
        )

        print(
            "#" * 60
        )

        try:

            process_application(
                application
            )

            successful += 1

            print()
            print(
                "APPLICATION PROCESSED SUCCESSFULLY"
            )

        except Exception as error:

            failed += 1

            print()
            print("=" * 60)

            print(
                "APPLICATION PROCESSING FAILED"
            )

            print("=" * 60)

            print(
                "Candidate:",
                application.get(
                    "candidate_name",
                    "Unknown"
                )
            )

            print(
                "Email:",
                application.get(
                    "candidate_email",
                    "Unknown"
                )
            )

            print(
                "Subject:",
                application.get(
                    "subject",
                    "Unknown"
                )
            )

            print(
                "Error type:",
                type(error).__name__
            )

            print(
                "Error:",
                str(error)
            )

            print()

            traceback.print_exc()

            print()

            print(
                "The application email was NOT "
                "marked as processed."
            )

            print(
                "It can be retried after the "
                "error is fixed."
            )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print()
    print("=" * 60)

    print(
        "RECRUITMENT EMAIL PIPELINE SUMMARY"
    )

    print("=" * 60)

    print(
        "Applications found:",
        len(applications)
    )

    print(
        "Successfully processed:",
        successful
    )

    print(
        "Failed:",
        failed
    )

    print("=" * 60)

    print()
    print(
        "Gmail recruitment check completed."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()