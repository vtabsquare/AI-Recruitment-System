from reply_analyzer import analyze_reply


# ============================================================
# TEST CANDIDATE REPLY
# ============================================================

candidate_reply = """
Yes, I am interested in the data analyst position.
I am available tomorrow after 4 pm.
"""


print("=" * 60)
print("VTAB SQUARE REPLY ANALYZER TEST")
print("=" * 60)

print()
print("CANDIDATE REPLY:")
print(candidate_reply)

print()
print("Sending reply to Gemini...")

result = analyze_reply(
    candidate_reply
)

print()
print("=" * 60)
print("AI REPLY ANALYSIS")
print("=" * 60)

print(result)

print()
print("=" * 60)
print("VALIDATION")
print("=" * 60)


# ============================================================
# EXPECTED VALUES
# ============================================================

expected_interest = "Interested"

expected_emotion = "Positive"

expected_availability = "Tomorrow after 4 pm"

expected_action = "Schedule Interview"


passed = True


# ============================================================
# INTEREST
# ============================================================

if result["interest"] == expected_interest:

    print("Interest: PASSED")

else:

    print("Interest: FAILED")

    print(
        "Expected:",
        expected_interest
    )

    print(
        "Actual:",
        result["interest"]
    )

    passed = False


# ============================================================
# EMOTION
# ============================================================

if result["emotion"] == expected_emotion:

    print("Emotion: PASSED")

else:

    print("Emotion: FAILED")

    print(
        "Expected:",
        expected_emotion
    )

    print(
        "Actual:",
        result["emotion"]
    )

    passed = False


# ============================================================
# AVAILABILITY
# ============================================================

if (
    result["availability"].strip().lower()
    == expected_availability.strip().lower()
):

    print("Availability: PASSED")

else:

    print("Availability: FAILED")

    print(
        "Expected:",
        expected_availability
    )

    print(
        "Actual:",
        result["availability"]
    )

    passed = False


# ============================================================
# NEXT ACTION
# ============================================================

if result["next_action"] == expected_action:

    print("Next Action: PASSED")

else:

    print("Next Action: FAILED")

    print(
        "Expected:",
        expected_action
    )

    print(
        "Actual:",
        result["next_action"]
    )

    passed = False


# ============================================================
# FINAL RESULT
# ============================================================

print()

if passed:

    print("=" * 60)
    print("REPLY ANALYZER TEST: PASSED")
    print("=" * 60)

else:

    print("=" * 60)
    print("REPLY ANALYZER TEST: FAILED")
    print("=" * 60)

    raise SystemExit(1)