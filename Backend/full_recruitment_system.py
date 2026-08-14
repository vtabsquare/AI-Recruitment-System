import os
import sys
import time
import traceback
from datetime import datetime

from recruitment_service import process_candidate
from reply_pipeline import process_candidate_replies


# ============================================================
# VTAB SQUARE
# COMPLETE AI RECRUITMENT AUTOMATION
# ============================================================
#
# ONE COMMAND:
#
#     python full_requirement.py
#
# Complete flow:
#
# Resume
#   ↓
# Gemini resume analysis
#   ↓
# AI eligibility evaluation
#   ↓
# Shortlisted / Rejected
#   ↓
# Shortlisted email
#   ↓
# WAIT FOR CANDIDATE REPLY
#   ↓
# Candidate accepts
#   ↓
# AI sends interview availability request
#   ↓
# WAIT FOR CANDIDATE AVAILABILITY
#   ↓
# Candidate chooses exact date + time
#   ↓
# AI validates availability
#   ↓
# Google Calendar
#   ↓
# Google Meet
#   ↓
# Final interview confirmation email
#   ↓
# STOP FOR THIS CANDIDATE
#
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

RESUME_FILE = "resume.pdf"

JOB_ROLE = "Data Analyst"

# How often Gmail should be checked.
#
# 20 seconds is convenient for a live mentor demonstration.
#
POLL_INTERVAL_SECONDS = 20


# ============================================================
# DISPLAY HELPERS
# ============================================================

def banner(title):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)
    print()


def timestamp():

    return datetime.now().strftime(
        "%H:%M:%S"
    )


def log(message):

    print(
        f"[{timestamp()}] {message}"
    )


# ============================================================
# VALIDATE RESUME
# ============================================================

def validate_resume():

    if not os.path.exists(
        RESUME_FILE
    ):

        raise FileNotFoundError(
            f"Resume file was not found:\n"
            f"{os.path.abspath(RESUME_FILE)}"
        )

    if not os.path.isfile(
        RESUME_FILE
    ):

        raise ValueError(
            f"Resume path is not a file:\n"
            f"{os.path.abspath(RESUME_FILE)}"
        )


# ============================================================
# PRINT SCREENING RESULT
# ============================================================

def show_screening_result(
    result
):

    banner(
        "SCREENING RESULT"
    )

    if not result:

        print(
            "Recruitment pipeline returned no result."
        )

        return False

    # --------------------------------------------------------
    # Print result safely
    # --------------------------------------------------------

    print(
        "Recruitment result:"
    )

    print()

    print(
        result
    )

    print()

    # --------------------------------------------------------
    # Determine recruitment decision
    # --------------------------------------------------------

    decision = ""

    if isinstance(
        result,
        dict
    ):

        # Normal recruitment_service result
        decision = str(
            result.get(
                "decision",
                ""
            )
        ).strip().lower()

        # Some versions return nested evaluation data
        if not decision:

            evaluation = result.get(
                "evaluation"
            )

            if isinstance(
                evaluation,
                dict
            ):

                decision = str(
                    evaluation.get(
                        "decision",
                        ""
                    )
                ).strip().lower()

        # Some versions return a notification type
        if not decision:

            decision = str(
                result.get(
                    "type",
                    ""
                )
            ).strip().lower()

    # --------------------------------------------------------
    # Rejected
    # --------------------------------------------------------

    if decision == "rejected":

        print()

        print(
            "Candidate was rejected."
        )

        print(
            "The recruitment process has ended "
            "for this candidate."
        )

        return False

    # --------------------------------------------------------
    # Shortlisted
    # --------------------------------------------------------

    if decision == "shortlisted":

        print()

        print(
            "Candidate was shortlisted."
        )

        print(
            "Shortlisted email has been sent."
        )

        return True

    # --------------------------------------------------------
    # If process_candidate returned another structure,
    # do not incorrectly stop the automation.
    #
    # The actual recruitment service already sends the
    # shortlisted email when its decision is shortlisted.
    #
    # --------------------------------------------------------

    print()

    print(
        "Screening completed."
    )

    print(
        "The reply listener will now monitor Gmail."
    )

    return True


# ============================================================
# PROCESS CANDIDATE REPLIES
# ============================================================

def check_candidate_replies():

    """
    Run the existing candidate-reply pipeline once.

    The existing reply_pipeline handles:

        Gmail reply
            ↓
        Reply cleaning
            ↓
        Gemini analysis
            ↓
        Candidate/application lookup
            ↓
        Acceptance / availability handling
            ↓
        Interview scheduling
            ↓
        Google Calendar
            ↓
        Google Meet
            ↓
        Supabase
            ↓
        Final Brevo confirmation email
    """

    try:

        results = (
            process_candidate_replies()
        )

        return results

    except Exception as error:

        print()
        print("=" * 70)
        print(
            "REPLY PIPELINE ERROR"
        )
        print("=" * 70)

        print()
        print(
            type(error).__name__
        )

        print(
            str(error)
        )

        print()

        traceback.print_exc()

        return None


# ============================================================
# CHECK WHETHER INTERVIEW IS COMPLETE
# ============================================================

def interview_completed(
    results
):

    """
    Stop the one-command automation immediately after the
    final interview Meet link has been generated/sent.
    """

    if not results:

        return False

    def contains_final_interview_result(value):

        # Dictionary result
        if isinstance(
            value,
            dict
        ):

            if value.get(
                "confirmation_email"
            ):

                return True

            meet_link = value.get(
                "meet_link"
            )

            if (
                isinstance(
                    meet_link,
                    str
                )
                and "meet.google.com" in meet_link
            ):

                return True

            for nested_value in value.values():

                if contains_final_interview_result(
                    nested_value
                ):

                    return True

            return False

        # List / tuple result
        if isinstance(
            value,
            (list, tuple)
        ):

            for item in value:

                if contains_final_interview_result(
                    item
                ):

                    return True

            return False

        # String fallback
        if isinstance(
            value,
            str
        ):

            return (
                "meet.google.com" in value
            )

        return False

    return contains_final_interview_result(
        results
    )


# ============================================================
# DISPLAY FINAL INTERVIEW RESULT
# ============================================================

def display_final_result(
    results
):

    banner(
        "FINAL INTERVIEW AUTOMATION RESULT"
    )

    if not results:

        print(
            "No final interview result was returned."
        )

        return

    if isinstance(
        results,
        dict
    ):

        results = [
            results
        ]

    if not isinstance(
        results,
        list
    ):

        print(
            results
        )

        return

    for index, result in enumerate(
        results,
        start=1
    ):

        if not isinstance(
            result,
            dict
        ):

            print(
                result
            )

            continue

        print(
            f"RESULT {index}"
        )

        print(
            "-" * 70
        )

        print(
            "Candidate:",
            result.get(
                "candidate_name",
                "Not available"
            )
        )

        print(
            "Email:",
            result.get(
                "candidate_email",
                "Not available"
            )
        )

        analysis = result.get(
            "analysis"
        )

        if isinstance(
            analysis,
            dict
        ):

            print(
                "Interest:",
                analysis.get(
                    "interest",
                    "Not available"
                )
            )

            print(
                "Availability:",
                analysis.get(
                    "availability",
                    "Not available"
                )
            )

            print(
                "Next Action:",
                analysis.get(
                    "next_action",
                    "Not available"
                )
            )

        interview = result.get(
            "interview"
        )

        if isinstance(
            interview,
            dict
        ):

            proposal = interview.get(
                "proposal"
            )

            if isinstance(
                proposal,
                dict
            ):

                start_time = proposal.get(
                    "start_time"
                )

                end_time = proposal.get(
                    "end_time"
                )

                if start_time:

                    print()

                    print(
                        "Interview:",
                        start_time.strftime(
                            "%A, %d %B %Y at %I:%M %p"
                        )
                    )

                if end_time:

                    print(
                        "Ends:",
                        end_time.strftime(
                            "%I:%M %p"
                        )
                    )

            calendar_result = (
                interview.get(
                    "calendar"
                )
            )

            if isinstance(
                calendar_result,
                dict
            ):

                print()

                print(
                    "Google Calendar:",
                    calendar_result.get(
                        "event_link",
                        "Not available"
                    )
                )

                print(
                    "Google Meet:",
                    calendar_result.get(
                        "meet_link",
                        "Not available"
                    )
                )

        confirmation = result.get(
            "confirmation_email"
        )

        if isinstance(
            confirmation,
            dict
        ):

            print()

            print(
                "Confirmation email:",
                confirmation.get(
                    "recipient",
                    "Not available"
                )
            )

            print(
                "Brevo Message ID:",
                confirmation.get(
                    "message_id",
                    "Not available"
                )
            )

        print()


# ============================================================
# MAIN AUTOMATION
# ============================================================

def main():

    banner(
        "VTAB SQUARE"
    )

    print(
        "COMPLETE AI RECRUITMENT AUTOMATION"
    )

    print()

    print(
        "ONE-COMMAND MODE"
    )

    print()

    print(
        "Resume"
    )

    print(
        "  ↓"
    )

    print(
        "AI Screening"
    )

    print(
        "  ↓"
    )

    print(
        "Shortlisted Email"
    )

    print(
        "  ↓"
    )

    print(
        "WAIT FOR CANDIDATE"
    )

    print(
        "  ↓"
    )

    print(
        "Candidate Acceptance"
    )

    print(
        "  ↓"
    )

    print(
        "Availability Request"
    )

    print(
        "  ↓"
    )

    print(
        "WAIT FOR CANDIDATE"
    )

    print(
        "  ↓"
    )

    print(
        "Candidate Preferred Date + Exact Time"
    )

    print(
        "  ↓"
    )

    print(
        "Calendar + Google Meet"
    )

    print(
        "  ↓"
    )

    print(
        "Final Interview Email"
    )

    print()

    print(
        "The program will remain running "
        "while waiting for candidate replies."
    )

    print()

    # ========================================================
    # VALIDATE RESUME
    # ========================================================

    validate_resume()

    log(
        f"Resume: {os.path.abspath(RESUME_FILE)}"
    )

    log(
        f"Role: {JOB_ROLE}"
    )

    # ========================================================
    # START RECRUITMENT PIPELINE
    # ========================================================

    banner(
        "STARTING RECRUITMENT PIPELINE"
    )

    try:

        recruitment_result = (
            process_candidate(
                RESUME_FILE,
                JOB_ROLE
            )
        )

    except Exception as error:

        banner(
            "RECRUITMENT PIPELINE FAILED"
        )

        print(
            type(error).__name__
        )

        print(
            str(error)
        )

        print()

        traceback.print_exc()

        sys.exit(1)

    # ========================================================
    # SCREENING RESULT
    # ========================================================

    shortlisted = (
        show_screening_result(
            recruitment_result
        )
    )

    if not shortlisted:

        banner(
            "AUTOMATION FINISHED"
        )

        print(
            "No interview automation is required."
        )

        return

    # ========================================================
    # START REPLY LISTENER
    # ========================================================

    banner(
        "CANDIDATE REPLY LISTENER ACTIVE"
    )

    print(
        "Waiting for candidate replies..."
    )

    print()

    print(
        "The candidate can now reply to the "
        "shortlisted email."
    )

    print()

    print(
        "Expected sequence:"
    )

    print(
        "1. Candidate accepts"
    )

    print(
        "2. AI sends availability request"
    )

    print(
        "3. Candidate provides preferred date + exact time"
    )

    print(
        "4. AI validates the requested time"
    )

    print(
        "5. Calendar + Google Meet are created"
    )

    print(
        "6. Final confirmation email is sent"
    )

    print()

    print(
        "Allowed interview windows:"
    )

    print(
        "  10:00 AM - 2:00 PM"
    )

    print(
        "  3:00 PM - 5:00 PM"
    )

    print()

    print(
        "The candidate chooses the exact time."
    )

    print(
        "The AI does NOT choose a time."
    )

    print()

    # ========================================================
    # CONTINUOUS MONITORING
    # ========================================================

    while True:

        print()

        log(
            "Checking Gmail for candidate replies..."
        )

        results = (
            check_candidate_replies()
        )

        # ----------------------------------------------------
        # FINAL INTERVIEW COMPLETED
        # ----------------------------------------------------

        if interview_completed(
            results
        ):

            display_final_result(
                results
            )

            banner(
                "COMPLETE RECRUITMENT FLOW FINISHED"
            )

            print(
                "Candidate interview has been scheduled."
            )

            print(
                "Google Meet link has been generated."
            )

            print(
                "Final interview confirmation has been sent."
            )

            print()

            print(
                "The automation has reached its final stage."
            )

            print(
                "STOPPING."
            )

            return

        # ----------------------------------------------------
        # Continue waiting
        # ----------------------------------------------------

        log(
            "No completed interview yet."
        )

        print(
            f"Next Gmail check in "
            f"{POLL_INTERVAL_SECONDS} seconds..."
        )

        try:

            time.sleep(
                POLL_INTERVAL_SECONDS
            )

        except KeyboardInterrupt:

            print()

            banner(
                "AUTOMATION STOPPED"
            )

            print(
                "Stopped by user."
            )

            return


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        banner(
            "AUTOMATION STOPPED"
        )

        print(
            "Stopped by user."
        )

    except Exception as error:

        print()

        banner(
            "UNEXPECTED ERROR"
        )

        print(
            type(error).__name__
        )

        print(
            str(error)
        )

        print()

        traceback.print_exc()