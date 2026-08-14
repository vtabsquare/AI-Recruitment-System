import json
import re

from google import genai
from config import GEMINI_API_KEY


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# CONCRETE AVAILABILITY DETECTION
# ============================================================

def has_concrete_availability(text):
    """
    Determine whether the candidate's current reply
    contains a concrete interview date/day AND time.

    Examples that are VALID:

        "Tomorrow at 4 PM"
        "Tuesday at 3:30 PM"
        "August 11 at 4 PM"
        "11 August at 4 PM"
        "I am available Monday at 5 PM"

    Examples that are INVALID:

        "I am available"
        "I am free"
        "Anytime works"
        "Whenever is fine"
        "Yes"
        "Yes, I am available at that time"
        "That time works"
    """

    if not text:
        return False

    text = str(text).strip().lower()

    # --------------------------------------------------------
    # TIME DETECTION
    # --------------------------------------------------------

    time_pattern = re.compile(
        r"\b\d{1,2}"
        r"(?::\d{2})?"
        r"\s*(?:am|pm)\b"
        r"|"
        r"\b\d{1,2}:\d{2}\b"
    )

    has_time = bool(
        time_pattern.search(text)
    )

    if not has_time:
        return False

    # --------------------------------------------------------
    # DAY / DATE DETECTION
    # --------------------------------------------------------

    date_words = [

        "today",
        "tomorrow",

        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",

        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december"
    ]

    has_date_word = any(
        word in text
        for word in date_words
    )

    # --------------------------------------------------------
    # NUMERIC DATE
    #
    # 11/08
    # 11-08
    # 11/08/2026
    # --------------------------------------------------------

    numeric_date = bool(
        re.search(
            r"\b\d{1,2}"
            r"(?:st|nd|rd|th)?"
            r"\s*"
            r"(?:/|-)"
            r"\s*\d{1,2}"
            r"(?:\s*(?:/|-)\s*\d{2,4})?"
            r"\b",
            text
        )
    )

    # --------------------------------------------------------
    # DAY + MONTH
    #
    # 11 August
    # 11th August
    # August 11
    # --------------------------------------------------------

    day_month_date = bool(
        re.search(
            r"\b\d{1,2}"
            r"(?:st|nd|rd|th)?"
            r"\s+"
            r"(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december)"
            r"\b",
            text
        )
    )

    month_day_date = bool(
        re.search(
            r"\b"
            r"(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december)"
            r"\s+"
            r"\d{1,2}"
            r"(?:st|nd|rd|th)?"
            r"\b",
            text
        )
    )

    return (
        has_time
        and (
            has_date_word
            or numeric_date
            or day_month_date
            or month_day_date
        )
    )


# ============================================================
# NORMALIZE AVAILABILITY
# ============================================================

def normalize_availability(
    availability
):

    if availability is None:
        return "Not Mentioned"

    availability = str(
        availability
    ).strip()

    if not availability:
        return "Not Mentioned"

    invalid_values = {

        "",
        "none",
        "null",
        "unknown",
        "not mentioned",
        "not provided",
        "not specified",
        "mentioned",
        "available",
        "yes",
        "true"
    }

    if availability.lower() in invalid_values:

        return "Not Mentioned"

    return availability


# ============================================================
# ANALYZE CANDIDATE REPLY
# ============================================================

def analyze_reply(
    email_body,
    current_stage="unknown"
):
    """
    Analyze the candidate's latest reply.

    IMPORTANT:

    Gemini decides the candidate's intent and next action.

    The actual candidate email is used as the scheduling
    availability source.

    This prevents Gemini from returning values such as:

        "Mentioned"

    and accidentally sending that value to the
    interview scheduler.
    """

    if not email_body:

        raise ValueError(
            "Candidate reply is empty."
        )

    email_body = str(
        email_body
    ).strip()

    current_stage = str(
        current_stage or "unknown"
    ).strip().lower()

    # ========================================================
    # GEMINI PROMPT
    # ========================================================

    prompt = f"""
You are the AI recruitment assistant for VTAB Square.

Analyze ONLY the candidate's latest email reply.

CURRENT APPLICATION STAGE:
{current_stage}

============================================================
VTAB SQUARE RECRUITMENT WORKFLOW
============================================================

Stage 1:

shortlisted
    ↓
Candidate accepts the opportunity
    ↓
interview_pending
    ↓
Candidate provides interview availability
    ↓
Schedule Interview
    ↓
interview_scheduled

============================================================
INTEREST
============================================================

Return exactly one:

Interested
Not Interested
Unsure

Examples of Interested:

"Yes"
"Yes, I am interested"
"I would like to proceed"
"I want to continue"
"I accept"
"I am interested in the position"

Examples of Not Interested:

"No"
"I am not interested"
"I don't want to proceed"
"I decline"

============================================================
AVAILABILITY
============================================================

A valid interview availability MUST contain
a concrete date/day AND a concrete time.

VALID:

"Tomorrow at 4 PM"
"Tuesday at 3:30 PM"
"Monday at 5 PM"
"August 11 at 4 PM"
"11 August at 4 PM"
"I am available on Friday at 2 PM"

INVALID:

"I am available"
"I am free"
"Anytime works"
"Whenever is fine"
"Yes"
"Yes, I am available at that time"
"That time works"
"That is fine"
"I can do it"

NEVER infer a date or time from previous emails.

Only use information explicitly present in
the CURRENT candidate reply.

============================================================
NEXT ACTION
============================================================

If CURRENT APPLICATION STAGE is:

shortlisted

and candidate is Interested:

    next_action = "Request Availability"

Even if the candidate includes a time in this first
acceptance email, DO NOT schedule the interview yet.

The workflow requires:

1. Candidate accepts
2. System asks for availability
3. Candidate provides availability
4. System schedules interview

If candidate is Not Interested:

    next_action = "Close Application"

If candidate is Unsure:

    next_action = "Send Follow-up"


If CURRENT APPLICATION STAGE is:

interview_pending

and the candidate provides a concrete date AND time:

    next_action = "Schedule Interview"

If the candidate does NOT provide a concrete date AND time:

    next_action = "Wait"

IMPORTANT:

Do NOT repeatedly request availability.

Do NOT schedule an interview from an ambiguous reply.

============================================================
AVAILABILITY OUTPUT
============================================================

If the candidate provides a concrete date/time,
return the actual availability phrase from the
candidate's current reply.

Do NOT return labels such as:

"Mentioned"
"Available"
"Yes"
"Confirmed"

If no concrete date/time exists:

"Not Mentioned"

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

No markdown.
No code fences.
No explanation outside JSON.

Use exactly:

{{
    "interest": "Interested",
    "emotion": "Positive",
    "availability": "Not Mentioned",
    "next_action": "Wait",
    "reason": "Candidate did not provide a concrete interview date and time."
}}

============================================================
CANDIDATE REPLY
============================================================

{email_body}
"""

    # ========================================================
    # CALL GEMINI
    # ========================================================

    response = client.models.generate_content(

        model="gemini-3.5-flash-lite",

        contents=prompt
    )

    text = response.text.strip()

    # ========================================================
    # REMOVE MARKDOWN FENCES
    # ========================================================

    if text.startswith(
        "```json"
    ):

        text = text[7:]

    elif text.startswith(
        "```"
    ):

        text = text[3:]

    if text.endswith(
        "```"
    ):

        text = text[:-3]

    text = text.strip()

    # ========================================================
    # PARSE JSON
    # ========================================================

    try:

        result = json.loads(
            text
        )

    except json.JSONDecodeError as error:

        print()
        print(
            "INVALID GEMINI RESPONSE:"
        )

        print(text)

        raise ValueError(
            "Gemini returned invalid JSON."
        ) from error

    # ========================================================
    # REQUIRED FIELDS
    # ========================================================

    required_fields = [

        "interest",

        "emotion",

        "availability",

        "next_action",

        "reason"
    ]

    for field in required_fields:

        if field not in result:

            raise ValueError(
                f"Gemini response is missing "
                f"required field: {field}"
            )

    # ========================================================
    # NORMALIZE VALUES
    # ========================================================

    result["interest"] = str(
        result["interest"]
    ).strip()

    result["emotion"] = str(
        result["emotion"]
    ).strip()

    result["availability"] = normalize_availability(
        result["availability"]
    )

    result["next_action"] = str(
        result["next_action"]
    ).strip()

    result["reason"] = str(
        result["reason"]
    ).strip()

    # ========================================================
    # VALID VALUES
    # ========================================================

    valid_interest = {

        "Interested",

        "Not Interested",

        "Unsure"
    }

    valid_emotions = {

        "Positive",

        "Neutral",

        "Negative"
    }

    valid_actions = {

        "Request Availability",

        "Schedule Interview",

        "Send Follow-up",

        "Close Application",

        "Wait"
    }

    if result["interest"] not in valid_interest:

        result["interest"] = "Unsure"

    if result["emotion"] not in valid_emotions:

        result["emotion"] = "Neutral"

    if result["next_action"] not in valid_actions:

        result["next_action"] = "Wait"

    # ========================================================
    # HARD DETERMINISTIC AVAILABILITY CHECK
    # ========================================================

    concrete = has_concrete_availability(
        email_body
    )

    # ========================================================
    # INTERVIEW_PENDING
    # ========================================================

    if current_stage == "interview_pending":

        # ----------------------------------------------------
        # CONCRETE DATE + TIME
        # ----------------------------------------------------

        if concrete:

            # IMPORTANT:
            #
            # NEVER use Gemini's availability field here.
            #
            # Use the actual candidate reply.
            #
            # This fixes:
            #
            # "availability": "Mentioned"
            #
            # causing:
            #
            # parse_availability("Mentioned")
            #
            # The scheduler now receives the actual text.

            result["availability"] = (
                email_body.strip()
            )

            result["next_action"] = (
                "Schedule Interview"
            )

            result["reason"] = (
                "Candidate provided a concrete "
                "interview date and time."
            )

        # ----------------------------------------------------
        # NO CONCRETE DATE/TIME
        # ----------------------------------------------------

        else:

            result["availability"] = (
                "Not Mentioned"
            )

            result["next_action"] = (
                "Wait"
            )

            result["reason"] = (
                "Candidate did not provide a concrete "
                "interview date and time."
            )

    # ========================================================
    # SHORTLISTED
    # ========================================================

    elif current_stage == "shortlisted":

        # ----------------------------------------------------
        # ACCEPTED
        # ----------------------------------------------------

        if result["interest"] == "Interested":

            result["availability"] = (
                "Not Mentioned"
            )

            result["next_action"] = (
                "Request Availability"
            )

            result["reason"] = (
                "Candidate confirmed interest and should "
                "now provide interview availability."
            )

        # ----------------------------------------------------
        # REJECTED
        # ----------------------------------------------------

        elif result["interest"] == "Not Interested":

            result["next_action"] = (
                "Close Application"
            )

            result["reason"] = (
                "Candidate declined to proceed "
                "with the opportunity."
            )

        # ----------------------------------------------------
        # UNSURE
        # ----------------------------------------------------

        else:

            result["next_action"] = (
                "Send Follow-up"
            )

            result["reason"] = (
                "Candidate did not clearly confirm "
                "or decline the opportunity."
            )

    # ========================================================
    # UNKNOWN STAGE
    # ========================================================

    else:

        # ----------------------------------------------------
        # Never schedule from an unknown stage.
        # ----------------------------------------------------

        if not concrete:

            result["availability"] = (
                "Not Mentioned"
            )

            result["next_action"] = (
                "Wait"
            )

        else:

            result["availability"] = (
                email_body.strip()
            )

            result["next_action"] = (
                "Schedule Interview"
            )

    # ========================================================
    # FINAL SAFETY CHECK
    # ========================================================

    if (
        result["next_action"]
        == "Schedule Interview"
        and not concrete
    ):

        result["availability"] = (
            "Not Mentioned"
        )

        result["next_action"] = (
            "Wait"
        )

        result["reason"] = (
            "Interview scheduling was blocked because "
            "the candidate did not provide a concrete "
            "date and time."
        )

    return result