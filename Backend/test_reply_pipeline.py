from reply_pipeline import process_candidate_replies


print()
print("=" * 60)
print("VTAB SQUARE REAL INTERVIEW AUTOMATION TEST")
print("=" * 60)

print()
print("Starting candidate reply processing...")
print()

try:

    results = process_candidate_replies()

except Exception as error:

    print()
    print("=" * 60)
    print("PIPELINE ERROR")
    print("=" * 60)

    print()
    print(type(error).__name__)
    print(error)

    raise


print()
print("=" * 60)
print("FINAL PIPELINE RESULT")
print("=" * 60)

print()

# ============================================================
# NO RESULT
# ============================================================

if not results:

    print(
        "No candidate replies were processed."
    )

# ============================================================
# DICTIONARY RESULT
# ============================================================

elif isinstance(
    results,
    dict
):

    print(
        "Pipeline completed."
    )

    print()

    for key, value in results.items():

        print(
            f"{key}: {value}"
        )

# ============================================================
# LIST RESULT
# ============================================================

elif isinstance(
    results,
    list
):

    for index, result in enumerate(
        results,
        start=1
    ):

        print(
            f"RESULT {index}"
        )

        print(
            "-" * 60
        )

        # ----------------------------------------------------
        # Normal dictionary result
        # ----------------------------------------------------

        if isinstance(
            result,
            dict
        ):

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
                    "Emotion:",
                    analysis.get(
                        "emotion",
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

            if interview:

                print()

                if isinstance(
                    interview,
                    dict
                ):

                    calendar = interview.get(
                        "calendar"
                    )

                    if isinstance(
                        calendar,
                        dict
                    ):

                        print(
                            "Calendar Event:",
                            calendar.get(
                                "summary",
                                "Not available"
                            )
                        )

                        print(
                            "Google Meet:",
                            calendar.get(
                                "meet_link",
                                "Not available"
                            )
                        )

            confirmation = result.get(
                "confirmation_email"
            )

            if confirmation:

                print()

                if isinstance(
                    confirmation,
                    dict
                ):

                    print(
                        "Confirmation Email:",
                        confirmation.get(
                            "recipient",
                            "Not available"
                        )
                    )

                    print(
                        "Message ID:",
                        confirmation.get(
                            "message_id",
                            "Not available"
                        )
                    )

            print()

        # ----------------------------------------------------
        # String result
        # ----------------------------------------------------

        else:

            print(
                "Pipeline returned:"
            )

            print(
                result
            )

        print()

# ============================================================
# STRING RESULT
# ============================================================

elif isinstance(
    results,
    str
):

    print(
        results
    )

# ============================================================
# UNKNOWN RESULT
# ============================================================

else:

    print(
        "Pipeline returned an unexpected result type:"
    )

    print(
        type(results).__name__
    )

    print()

    print(
        results
    )


print("=" * 60)
print("END")
print("=" * 60)