from datetime import datetime, timedelta, timezone
import uuid

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_auth import get_google_credentials


# ============================================================
# VTAB SQUARE INTERVIEW SCHEDULER
# COMPANY SLOT BASED SCHEDULING
# ============================================================

IST = timezone(
    timedelta(hours=5, minutes=30)
)

TIMEZONE_NAME = "Asia/Kolkata"

INTERVIEW_DURATION_MINUTES = 30


# ============================================================
# COMPANY INTERVIEW WINDOW
#
# Interviews are allowed only between:
#
# 10:00 AM and 2:00 PM IST
#
# Monday to Friday
# ============================================================

INTERVIEW_START_HOUR = 10
INTERVIEW_END_HOUR = 14


# ============================================================
# COMPANY SLOTS
#
# Explicit 12-hour labels are used here so the configuration
# is easy for humans to understand.
#
# The scheduler converts them internally to 24-hour time.
# ============================================================

COMPANY_SLOTS = {
    "MORNING": [
        "10:00 AM",
        "10:30 AM",
        "11:00 AM",
        "11:30 AM",
    ],

    "AFTERNOON": [
        "12:00 PM",
        "12:30 PM",
        "1:00 PM",
        "1:30 PM",
    ],
}


# ============================================================
# INTERVIEW DAYS
# ============================================================

INTERVIEW_DAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
}


# ============================================================
# CURRENT IST TIME
# ============================================================

def get_current_ist():

    return datetime.now(
        IST
    )


# ============================================================
# NORMALIZE SESSION
# ============================================================

def normalize_session(session):

    if not session:

        raise ValueError(
            "Interview session is required."
        )

    session = (
        str(session)
        .strip()
        .upper()
    )

    aliases = {

        "AM":
            "MORNING",

        "A.M.":
            "MORNING",

        "MORNING":
            "MORNING",

        "MORN":
            "MORNING",

        "PM":
            "AFTERNOON",

        "P.M.":
            "AFTERNOON",

        "AFTERNOON":
            "AFTERNOON",

        "AFTERNOON SESSION":
            "AFTERNOON",

        "NOON":
            "AFTERNOON",
    }

    normalized = aliases.get(
        session
    )

    if normalized is None:

        raise ValueError(
            "Invalid interview session. "
            "Use AM, PM, Morning, or Afternoon."
        )

    return normalized


# ============================================================
# PARSE COMPANY SLOT
# ============================================================

def parse_slot_time(
    interview_date,
    time_string
):

    time_string = (
        time_string
        .strip()
        .upper()
    )

    try:

        parsed = datetime.strptime(
            time_string,
            "%I:%M %p"
        )

    except ValueError as error:

        raise ValueError(
            f"Invalid company slot: "
            f"{time_string}"
        ) from error

    slot_datetime = datetime(
        interview_date.year,
        interview_date.month,
        interview_date.day,
        parsed.hour,
        parsed.minute,
        tzinfo=IST
    )

    return slot_datetime


# ============================================================
# VALIDATE SLOT WINDOW
# ============================================================

def validate_slot_window(
    start_time
):

    end_time = (
        start_time
        + timedelta(
            minutes=INTERVIEW_DURATION_MINUTES
        )
    )

    # Interview must start at or after 10 AM.
    if start_time.hour < INTERVIEW_START_HOUR:

        return False

    # Interview must END by 2 PM.
    if (
        end_time.hour > INTERVIEW_END_HOUR
        or (
            end_time.hour
            == INTERVIEW_END_HOUR
            and end_time.minute > 0
        )
    ):

        return False

    return True


# ============================================================
# DISPLAY COMPANY SLOTS
# ============================================================

def get_company_slots():

    return {
        "MORNING":
            COMPANY_SLOTS[
                "MORNING"
            ].copy(),

        "AFTERNOON":
            COMPANY_SLOTS[
                "AFTERNOON"
            ].copy(),
    }


def print_company_slots():

    print()
    print("=" * 60)

    print(
        "VTAB SQUARE INTERVIEW SLOTS"
    )

    print("=" * 60)

    print()

    print(
        "INTERVIEW WINDOW:"
    )

    print(
        "10:00 AM - 2:00 PM IST"
    )

    print()

    print(
        "MORNING SLOTS:"
    )

    for slot in COMPANY_SLOTS[
        "MORNING"
    ]:

        print(
            f"  {slot}"
        )

    print()

    print(
        "AFTERNOON SLOTS:"
    )

    for slot in COMPANY_SLOTS[
        "AFTERNOON"
    ]:

        print(
            f"  {slot}"
        )

    print()

    print("=" * 60)


# ============================================================
# GET NEXT INTERVIEW DATE
# ============================================================

def get_next_interview_date(
    start_date=None
):

    if start_date is None:

        start_date = (
            get_current_ist()
            .date()
        )

    for day_offset in range(
        0,
        14
    ):

        candidate_date = (
            start_date
            + timedelta(
                days=day_offset
            )
        )

        if (
            candidate_date.weekday()
            in INTERVIEW_DAYS.values()
        ):

            return candidate_date

    raise RuntimeError(
        "No interview day found."
    )


# ============================================================
# GOOGLE CALENDAR SERVICE
# ============================================================

def get_calendar_service():

    credentials = (
        get_google_credentials()
    )

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )


# ============================================================
# CHECK CALENDAR AVAILABILITY
# ============================================================

def is_slot_available(
    service,
    start_time,
    end_time
):

    try:

        response = (
            service
            .freebusy()
            .query(
                body={

                    "timeMin":
                        start_time.isoformat(),

                    "timeMax":
                        end_time.isoformat(),

                    "timeZone":
                        TIMEZONE_NAME,

                    "items": [
                        {
                            "id":
                                "primary"
                        }
                    ]
                }
            )
            .execute()
        )

        calendars = (
            response.get(
                "calendars",
                {}
            )
        )

        primary = (
            calendars.get(
                "primary",
                {}
            )
        )

        busy_periods = (
            primary.get(
                "busy",
                []
            )
        )

        return (
            len(
                busy_periods
            )
            == 0
        )

    except HttpError as error:

        print()
        print("=" * 60)

        print(
            "GOOGLE CALENDAR AVAILABILITY ERROR"
        )

        print("=" * 60)

        print(error)

        raise


# ============================================================
# FIND AVAILABLE COMPANY SLOT
# ============================================================

def find_available_slot(
    session,
    service=None,
    start_date=None
):

    session = normalize_session(
        session
    )

    if service is None:

        service = (
            get_calendar_service()
        )

    now = (
        get_current_ist()
    )

    if start_date is None:

        start_date = (
            now.date()
        )

    # --------------------------------------------------------
    # Search next 14 days
    # --------------------------------------------------------

    for day_offset in range(
        0,
        14
    ):

        interview_date = (
            start_date
            + timedelta(
                days=day_offset
            )
        )

        # Monday-Friday only
        if (
            interview_date.weekday()
            not in INTERVIEW_DAYS.values()
        ):

            continue

        # ----------------------------------------------------
        # Check company's slots for selected session
        # ----------------------------------------------------

        for time_string in COMPANY_SLOTS[
            session
        ]:

            start_time = parse_slot_time(
                interview_date,
                time_string
            )

            end_time = (
                start_time
                + timedelta(
                    minutes=
                    INTERVIEW_DURATION_MINUTES
                )
            )

            # ------------------------------------------------
            # Enforce 10 AM - 2 PM rule
            # ------------------------------------------------

            if not validate_slot_window(
                start_time
            ):

                continue

            # ------------------------------------------------
            # Don't schedule in the past
            # ------------------------------------------------

            if start_time <= now:

                continue

            # ------------------------------------------------
            # Check Google Calendar
            # ------------------------------------------------

            if is_slot_available(
                service,
                start_time,
                end_time
            ):

                return {

                    "session":
                        session,

                    "date":
                        interview_date,

                    "time":
                        time_string,

                    "start_time":
                        start_time,

                    "end_time":
                        end_time,

                    "duration_minutes":
                        INTERVIEW_DURATION_MINUTES,

                    "timezone":
                        TIMEZONE_NAME
                }

    return None


# ============================================================
# FIND ALTERNATIVE SESSION
# ============================================================

def get_alternative_session(
    session
):

    if session == "MORNING":

        return "AFTERNOON"

    return "MORNING"


# ============================================================
# CREATE INTERVIEW PROPOSAL
# ============================================================

def create_interview_proposal(
    session,
    candidate_name="Candidate",
    start_date=None
):

    session = normalize_session(
        session
    )

    service = (
        get_calendar_service()
    )

    slot = find_available_slot(
        session=session,
        service=service,
        start_date=start_date
    )

    # --------------------------------------------------------
    # Requested session unavailable
    # --------------------------------------------------------

    if slot is None:

        alternative_session = (
            get_alternative_session(
                session
            )
        )

        alternative_slot = (
            find_available_slot(
                session=
                    alternative_session,

                service=
                    service,

                start_date=
                    start_date
            )
        )

        if alternative_slot:

            return {

                "success":
                    False,

                "session_full":
                    True,

                "requested_session":
                    session,

                "alternative_session":
                    alternative_session,

                "alternative_slot":
                    alternative_slot,

                "message":
                    (
                        f"All {session.lower()} "
                        "slots are currently full. "
                        f"An {alternative_session.lower()} "
                        "slot is available."
                    )
            }

        return {

            "success":
                False,

            "session_full":
                True,

            "requested_session":
                session,

            "alternative_session":
                None,

            "alternative_slot":
                None,

            "message":
                (
                    "No interview slots are "
                    "currently available."
                )
        }

    # --------------------------------------------------------
    # Slot found
    # --------------------------------------------------------

    return {

        "success":
            True,

        "session_full":
            False,

        "candidate_name":
            candidate_name,

        "session":
            session,

        "start_time":
            slot[
                "start_time"
            ],

        "end_time":
            slot[
                "end_time"
            ],

        "duration_minutes":
            INTERVIEW_DURATION_MINUTES,

        "timezone":
            TIMEZONE_NAME
    }


# ============================================================
# CREATE GOOGLE CALENDAR EVENT + GOOGLE MEET
# ============================================================

def create_google_calendar_event(
    proposal,
    candidate_email=None,
    test_event=False,
    application_id=None
):

    if not proposal:

        raise ValueError(
            "Interview proposal is required."
        )

    if not proposal.get(
        "success",
        True
    ):

        raise ValueError(
            proposal.get(
                "message",
                "Interview proposal unavailable."
            )
        )

    credentials = (
        get_google_credentials()
    )

    service = build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False
    )

    candidate_name = (
        proposal.get(
            "candidate_name",
            "Candidate"
        )
    )

    start_time = proposal[
        "start_time"
    ]

    end_time = proposal[
        "end_time"
    ]

    # ========================================================
    # EVENT DETAILS
    # ========================================================

    if test_event:

        summary = (
            "VTAB TEST INTERVIEW - "
            f"{candidate_name}"
        )

        description = (
            "VTAB Square test interview."
        )

    else:

        summary = (
            "VTAB Square Interview - "
            f"{candidate_name}"
        )

        description = (
            "Interview scheduled by the "
            "VTAB Square AI Recruitment System.\n\n"
            f"Session: "
            f"{proposal.get('session', '')}\n"
            f"Date: "
            f"{start_time.strftime('%d %B %Y')}\n"
            f"Time: "
            f"{start_time.strftime('%I:%M %p')}\n"
            f"Timezone: "
            f"{TIMEZONE_NAME}\n"
        )

        if application_id:

            description += (
                f"Application ID: "
                f"{application_id}\n"
            )

    # ========================================================
    # EVENT
    # ========================================================

    event = {

        "summary":
            summary,

        "description":
            description,

        "start": {

            "dateTime":
                start_time.isoformat(),

            "timeZone":
                TIMEZONE_NAME
        },

        "end": {

            "dateTime":
                end_time.isoformat(),

            "timeZone":
                TIMEZONE_NAME
        },

        "conferenceData": {

            "createRequest": {

                "requestId":
                    str(uuid.uuid4()),

                "conferenceSolutionKey": {

                    "type":
                        "hangoutsMeet"
                }
            }
        }
    }

    # ========================================================
    # CANDIDATE ATTENDEE
    # ========================================================

    if (
        not test_event
        and candidate_email
    ):

        event[
            "attendees"
        ] = [

            {
                "email":
                    candidate_email
            }

        ]

    # ========================================================
    # CREATE EVENT
    # ========================================================

    try:

        created_event = (
            service
            .events()
            .insert(

                calendarId=
                    "primary",

                body=
                    event,

                conferenceDataVersion=
                    1,

                sendUpdates=(
                    "none"
                    if test_event
                    else "all"
                )
            )
            .execute()
        )

    except HttpError as error:

        print()
        print("=" * 60)

        print(
            "GOOGLE CALENDAR EVENT ERROR"
        )

        print("=" * 60)

        print(error)

        raise

    # ========================================================
    # GET GOOGLE MEET LINK
    # ========================================================

    meet_link = ""

    conference_data = (
        created_event.get(
            "conferenceData",
            {}
        )
    )

    for entry_point in (
        conference_data.get(
            "entryPoints",
            []
        )
    ):

        if (
            entry_point.get(
                "entryPointType"
            )
            == "video"
        ):

            meet_link = (
                entry_point.get(
                    "uri",
                    ""
                )
            )

            break

    if not meet_link:

        raise RuntimeError(
            "Google Meet link was not created."
        )

    return {

        "event_id":
            created_event.get(
                "id",
                ""
            ),

        "event_link":
            created_event.get(
                "htmlLink",
                ""
            ),

        "meet_link":
            meet_link,

        "candidate_name":
            candidate_name,

        "candidate_email":
            candidate_email or "",

        "application_id":
            application_id,

        "session":
            proposal.get(
                "session",
                ""
            ),

        "start_time":
            start_time,

        "end_time":
            end_time,

        "timezone":
            TIMEZONE_NAME,

        "test_event":
            test_event
    }


# ============================================================
# COMPLETE CANDIDATE SCHEDULING
# ============================================================

def schedule_candidate_from_session(
    session,
    candidate_name,
    candidate_email,
    application_id=None,
    start_date=None
):

    print()
    print("=" * 60)

    print(
        "VTAB SQUARE AI INTERVIEW SCHEDULER"
    )

    print("=" * 60)

    print()

    print(
        "Candidate:",
        candidate_name
    )

    print(
        "Email:",
        candidate_email
    )

    print(
        "Requested session:",
        session
    )

    # --------------------------------------------------------
    # Find slot
    # --------------------------------------------------------

    proposal = (
        create_interview_proposal(
            session=
                session,

            candidate_name=
                candidate_name,

            start_date=
                start_date
        )
    )

    # --------------------------------------------------------
    # No slot
    # --------------------------------------------------------

    if not proposal.get(
        "success"
    ):

        print()
        print(
            proposal.get(
                "message",
                "No slot available."
            )
        )

        return proposal

    # --------------------------------------------------------
    # Slot found
    # --------------------------------------------------------

    print()
    print(
        "AVAILABLE SLOT FOUND"
    )

    print(
        "Session:",
        proposal[
            "session"
        ]
    )

    print(
        "Date:",
        proposal[
            "start_time"
        ].strftime(
            "%A, %d %B %Y"
        )
    )

    print(
        "Time:",
        proposal[
            "start_time"
        ].strftime(
            "%I:%M %p"
        )
    )

    # --------------------------------------------------------
    # Calendar + Meet
    # --------------------------------------------------------

    calendar_result = (
        create_google_calendar_event(

            proposal=
                proposal,

            candidate_email=
                candidate_email,

            test_event=
                False,

            application_id=
                application_id
        )
    )

    print()
    print(
        "GOOGLE MEET CREATED"
    )

    print(
        calendar_result[
            "meet_link"
        ]
    )

    return {

        "success":
            True,

        "candidate_name":
            candidate_name,

        "candidate_email":
            candidate_email,

        "application_id":
            application_id,

        "session":
            proposal[
                "session"
            ],

        "start_time":
            proposal[
                "start_time"
            ],

        "end_time":
            proposal[
                "end_time"
            ],

        "meet_link":
            calendar_result[
                "meet_link"
            ],

        "event_id":
            calendar_result[
                "event_id"
            ],

        "event_link":
            calendar_result[
                "event_link"
            ],

        "timezone":
            TIMEZONE_NAME
    }


# ============================================================
# PRINT PROPOSAL
# ============================================================

def print_interview_proposal(
    proposal
):

    if not proposal:

        return

    print()
    print("=" * 60)

    print(
        "INTERVIEW PROPOSAL"
    )

    print("=" * 60)

    if not proposal.get(
        "success"
    ):

        print(
            "Status: NO SLOT AVAILABLE"
        )

        print(
            "Requested session:",
            proposal.get(
                "requested_session"
            )
        )

        print(
            "Message:",
            proposal.get(
                "message"
            )
        )

        if proposal.get(
            "alternative_session"
        ):

            alternative_slot = (
                proposal.get(
                    "alternative_slot"
                )
            )

            print(
                "Alternative session:",
                proposal[
                    "alternative_session"
                ]
            )

            if alternative_slot:

                print(
                    "Alternative time:",
                    alternative_slot[
                        "start_time"
                    ].strftime(
                        "%A, %d %B %Y at %I:%M %p"
                    )
                )

        return

    print(
        "Candidate:",
        proposal.get(
            "candidate_name",
            "Candidate"
        )
    )

    print(
        "Session:",
        proposal[
            "session"
        ]
    )

    print(
        "Date:",
        proposal[
            "start_time"
        ].strftime(
            "%A, %d %B %Y"
        )
    )

    print(
        "Start:",
        proposal[
            "start_time"
        ].strftime(
            "%I:%M %p"
        )
    )

    print(
        "End:",
        proposal[
            "end_time"
        ].strftime(
            "%I:%M %p"
        )
    )

    print(
        "Duration:",
        proposal[
            "duration_minutes"
        ],
        "minutes"
    )

    print(
        "Timezone:",
        proposal[
            "timezone"
        ]
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)

    print(
        "VTAB SQUARE INTERVIEW SCHEDULER TEST"
    )

    print("=" * 60)

    print_company_slots()

    print()
    print(
        "Testing MORNING availability..."
    )

    morning_proposal = (
        create_interview_proposal(
            session="MORNING",
            candidate_name=
                "Test Candidate"
        )
    )

    print_interview_proposal(
        morning_proposal
    )

    print()
    print(
        "Testing AFTERNOON availability..."
    )

    afternoon_proposal = (
        create_interview_proposal(
            session="AFTERNOON",
            candidate_name=
                "Test Candidate"
        )
    )

    print_interview_proposal(
        afternoon_proposal
    )