from recruitment_service import process_candidate
from reply_pipeline import process_candidate_replies


print()
print("=" * 70)
print("VTAB SQUARE COMPLETE INTERVIEW AUTOMATION DEMO")
print("=" * 70)

print()
print("FLOW:")
print("1. Resume is analyzed")
print("2. Candidate is evaluated")
print("3. Shortlist / greeting email is sent")
print("4. System waits for candidate reply")
print("5. Candidate reply is analyzed by Gemini")
print("6. Interview is scheduled")
print("7. Google Meet is generated")
print("8. Interview confirmation email is sent")
print()

print("=" * 70)


# ============================================================
# STAGE 1 - RESUME SCREENING
# ============================================================

print()
print("[STAGE 1] STARTING AI RECRUITMENT SCREENING")
print("=" * 70)

result = process_candidate(
    "resume.pdf",
    "Data Analyst"
)


# ============================================================
# CHECK STAGE 1 RESULT
# ============================================================

evaluation = result.get(
    "ai_evaluation",
    {}
)

decision = str(
    evaluation.get(
        "decision",
        ""
    )
).strip().lower()


print()
print("=" * 70)
print("STAGE 1 COMPLETED")
print("=" * 70)

print()
print("Candidate:")
print(
    result.get(
        "candidate",
        {}
    ).get(
        "candidate_name",
        "Unknown"
    )
)

print()
print("Email:")
print(
    result.get(
        "candidate",
        {}
    ).get(
        "email",
        "Unknown"
    )
)

print()
print("AI Decision:")
print(decision)


# ============================================================
# STOP IF REJECTED
# ============================================================

if decision != "shortlisted":

    print()
    print("=" * 70)
    print("PIPELINE STOPPED")
    print("=" * 70)

    print()
    print(
        "Candidate was not shortlisted."
    )

    print(
        "No interview will be scheduled."
    )

    print()
    print("=" * 70)

    raise SystemExit(0)


# ============================================================
# SHORTLIST EMAIL HAS BEEN SENT
# ============================================================

print()
print("=" * 70)
print("SHORTLIST EMAIL SENT")
print("=" * 70)

print()
print(
    "The candidate has received the greeting /"
    " shortlist email."
)

print()
print(
    "Now open the candidate Gmail account."
)

print()
print(
    "Reply to the email as the candidate."
)

print()
print(
    "Example reply:"
)

print(
    "Yes, I am interested in the data analyst "
    "position. I am available tomorrow after 4 pm."
)

print()
print("=" * 70)


# ============================================================
# WAIT FOR CANDIDATE REPLY
# ============================================================

input(
    "\nPress ENTER only AFTER the candidate has replied..."
)


# ============================================================
# STAGE 2 - CANDIDATE REPLY PIPELINE
# ============================================================

print()
print("=" * 70)
print("STAGE 2 - PROCESSING CANDIDATE REPLY")
print("=" * 70)

results = process_candidate_replies()


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("=" * 70)
print("FINAL INTERVIEW AUTOMATION RESULT")
print("=" * 70)

print()

if not results:

    print(
        "No candidate replies were processed."
    )

else:

    for index, result in enumerate(
        results,
        start=1
    ):

        print()
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
                "Unknown"
            )
        )

        print(
            "Email:",
            result.get(
                "candidate_email",
                "Unknown"
            )
        )

        analysis = result.get(
            "analysis",
            {}
        )

        print()
        print(
            "Interest:",
            analysis.get(
                "interest",
                ""
            )
        )

        print(
            "Emotion:",
            analysis.get(
                "emotion",
                ""
            )
        )

        print(
            "Availability:",
            analysis.get(
                "availability",
                ""
            )
        )

        print(
            "Next Action:",
            analysis.get(
                "next_action",
                ""
            )
        )

        interview = result.get(
            "interview"
        )

        if interview:

            calendar = interview.get(
                "calendar",
                {}
            )

            print()
            print(
                "Google Calendar:",
                calendar.get(
                    "event_link",
                    ""
                )
            )

            print(
                "Google Meet:",
                calendar.get(
                    "meet_link",
                    ""
                )
            )

            interview_record = interview.get(
                "interview_record"
            )

            if interview_record:

                print()
                print(
                    "Interview ID:",
                    interview_record.get(
                        "id",
                        ""
                    )
                )

                print(
                    "Interview Status:",
                    interview_record.get(
                        "status",
                        ""
                    )
                )

        confirmation = result.get(
            "confirmation_email"
        )

        if confirmation:

            print()
            print(
                "Interview Confirmation Sent To:",
                confirmation.get(
                    "recipient",
                    ""
                )
            )

            print(
                "Message ID:",
                confirmation.get(
                    "message_id",
                    ""
                )
            )


print()
print("=" * 70)
print("COMPLETE INTERVIEW AUTOMATION DEMO FINISHED")
print("=" * 70)