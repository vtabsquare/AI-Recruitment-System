import os
import json
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ============================================================
# GOOGLE OAUTH SCOPES
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CREDENTIALS_FILE = os.path.join(
    BASE_DIR,
    "credentials.json"
)

TOKEN_FILE = os.path.join(
    BASE_DIR,
    "token.json"
)


# ============================================================
# REQUIRED SCOPES
# ============================================================

REQUIRED_SCOPES = set(
    SCOPES
)


# ============================================================
# DEBUG
# ============================================================

print(
    "LOADED FILE:",
    os.path.abspath(__file__)
)

print(
    "SCOPES:",
    repr(SCOPES)
)


# ============================================================
# LOAD EXISTING TOKEN
# ============================================================

def load_existing_credentials():
    """
    Load OAuth token from env var (Render/production) or file (local dev).
    GOOGLE_TOKEN_JSON env var should contain the base64-encoded contents of token.json.
    """

    # --- Production: load from environment variable ---
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        try:
            token_data = base64.b64decode(token_env).decode("utf-8")
            return Credentials.from_authorized_user_info(
                json.loads(token_data),
                SCOPES
            )
        except Exception as error:
            print("Could not load token from GOOGLE_TOKEN_JSON env var:", error)
            return None

    # --- Local dev: load from file ---
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    except Exception as error:
        print("Could not load existing token from file:", error)
        return None


# ============================================================
# DELETE TOKEN
# ============================================================

def delete_token():

    if os.path.exists(
        TOKEN_FILE
    ):

        try:

            os.remove(
                TOKEN_FILE
            )

            print()
            print(
                "Old token.json deleted."
            )

        except Exception as error:

            raise RuntimeError(
                "Could not delete token.json: "
                f"{error}"
            )


# ============================================================
# SAVE TOKEN
# ============================================================

def save_credentials(
    credentials
):

    with open(
        TOKEN_FILE,
        "w",
        encoding="utf-8"
    ) as token:

        token.write(
            credentials.to_json()
        )


# ============================================================
# CHECK REQUIRED SCOPES
# ============================================================

def has_required_scopes(
    credentials
):

    if not credentials:
        return False

    granted_scopes = set(
        credentials.scopes or []
    )

    return REQUIRED_SCOPES.issubset(
        granted_scopes
    )


# ============================================================
# DISPLAY SCOPES
# ============================================================

def display_scopes(
    title,
    scopes
):

    print()
    print(title)

    if not scopes:

        print(
            "  NONE"
        )

        return

    for scope in sorted(
        scopes
    ):

        print(
            "  -",
            scope
        )


# ============================================================
# TEST ACTUAL CALENDAR ACCESS
# ============================================================

def verify_calendar_access(
    credentials
):

    print()
    print(
        "Testing actual Google Calendar API access..."
    )

    try:

        service = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False
        )

        # ----------------------------------------------------
        # This is a REAL API permission test.
        #
        # If this succeeds, the access token actually has
        # Calendar permission.
        # ----------------------------------------------------

        calendar = (
            service
            .calendars()
            .get(
                calendarId="primary"
            )
            .execute()
        )

        calendar_name = calendar.get(
            "summary",
            "Primary Calendar"
        )

        print()
        print(
            "CALENDAR ACCESS VERIFIED."
        )

        print(
            "Calendar:",
            calendar_name
        )

        return True

    except HttpError as error:

        print()
        print(
            "CALENDAR ACCESS FAILED."
        )

        print(
            error
        )

        return False

    except Exception as error:

        print()
        print(
            "CALENDAR ACCESS TEST FAILED."
        )

        print(
            error
        )

        return False


# ============================================================
# AUTHORIZE GOOGLE
# ============================================================

def authorize_google():

    if not os.path.exists(
        CREDENTIALS_FILE
    ):

        raise FileNotFoundError(
            "credentials.json was not found at:\n"
            f"{CREDENTIALS_FILE}"
        )

    print()
    print("=" * 60)
    print("NEW GOOGLE AUTHORIZATION")
    print("=" * 60)

    print()
    print(
        "The browser will open for Google authorization."
    )

    print()
    print(
        "Required permissions:"
    )

    print(
        "  - Gmail read access"
    )

    print(
        "  - Google Calendar access"
    )

    print()

    flow = (
        InstalledAppFlow
        .from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES
        )
    )

    credentials = (
        flow.run_local_server(
            port=0
        )
    )

    # ========================================================
    # CHECK GRANTED SCOPES
    # ========================================================

    granted_scopes = set(
        credentials.scopes or []
    )

    display_scopes(
        "Newly granted scopes:",
        granted_scopes
    )

    missing_scopes = (
        REQUIRED_SCOPES
        - granted_scopes
    )

    if missing_scopes:

        raise RuntimeError(
            "Google authorization completed, "
            "but required scopes are missing:\n"
            + "\n".join(
                f"- {scope}"
                for scope in sorted(
                    missing_scopes
                )
            )
        )

    # ========================================================
    # SAVE
    # ========================================================

    save_credentials(
        credentials
    )

    print()
    print(
        "New Google token saved."
    )

    # ========================================================
    # VERIFY REAL CALENDAR ACCESS
    # ========================================================

    if not verify_calendar_access(
        credentials
    ):

        delete_token()

        raise RuntimeError(
            "Google authorization completed, "
            "but the authorized token could not "
            "access Google Calendar."
        )

    return credentials


# ============================================================
# GET GOOGLE CREDENTIALS
# ============================================================

def get_google_credentials():

    print()
    print("=" * 60)
    print("GOOGLE AUTHENTICATION")
    print("=" * 60)

    print()
    print(
        "Required Google scopes:"
    )

    for scope in SCOPES:

        print(
            "  -",
            scope
        )

    # ========================================================
    # CHECK CLIENT CREDENTIALS
    # ========================================================

    if not os.path.exists(
        CREDENTIALS_FILE
    ):

        raise FileNotFoundError(
            "credentials.json was not found at:\n"
            f"{CREDENTIALS_FILE}"
        )

    # ========================================================
    # LOAD TOKEN
    # ========================================================

    credentials = (
        load_existing_credentials()
    )

    if credentials:

        existing_scopes = set(
            credentials.scopes or []
        )

        display_scopes(
            "Scopes stored in existing token:",
            existing_scopes
        )

        # ----------------------------------------------------
        # Detect malformed scopes
        # ----------------------------------------------------

        malformed = any(
            scope.startswith("[")
            or "](" in scope
            or "](http" in scope
            for scope in existing_scopes
        )

        if malformed:

            print()
            print(
                "Malformed OAuth scopes detected."
            )

            delete_token()

            credentials = None

        # ----------------------------------------------------
        # Detect missing scopes
        # ----------------------------------------------------

        elif not has_required_scopes(
            credentials
        ):

            print()
            print(
                "Required scopes are missing."
            )

            missing = (
                REQUIRED_SCOPES
                - existing_scopes
            )

            for scope in sorted(
                missing
            ):

                print(
                    "  -",
                    scope
                )

            delete_token()

            credentials = None

    # ========================================================
    # EXISTING TOKEN
    # ========================================================

    if credentials:

        # ----------------------------------------------------
        # ALWAYS REFRESH IF POSSIBLE
        #
        # This is important because the existing access token
        # may be valid but still be an older token.
        # ----------------------------------------------------

        if credentials.refresh_token:

            try:

                print()
                print(
                    "Refreshing Google access token..."
                )

                credentials.refresh(
                    Request()
                )

                save_credentials(
                    credentials
                )

                print(
                    "Access token refreshed."
                )

            except Exception as error:

                print()
                print(
                    "Existing token refresh failed."
                )

                print(
                    "Reason:",
                    error
                )

                delete_token()

                credentials = None

        # ----------------------------------------------------
        # Check validity
        # ----------------------------------------------------

        if (
            credentials
            and not credentials.valid
        ):

            print()
            print(
                "Existing Google credentials are invalid."
            )

            delete_token()

            credentials = None

    # ========================================================
    # VERIFY REAL CALENDAR ACCESS
    # ========================================================

    if (
        credentials
        and has_required_scopes(
            credentials
        )
    ):

        print()
        print(
            "Testing current access token "
            "against Google Calendar..."
        )

        calendar_access = (
            verify_calendar_access(
                credentials
            )
        )

        if calendar_access:

            print()
            print(
                "Using existing Google credentials."
            )

            print(
                "Token file:",
                TOKEN_FILE
            )

            display_scopes(
                "Granted scopes:",
                set(
                    credentials.scopes or []
                )
            )

            print()
            print(
                "Google credentials are valid."
            )

            return credentials

        # ----------------------------------------------------
        # Token metadata says Calendar exists,
        # but the actual API rejects it.
        # ----------------------------------------------------

        print()
        print(
            "The existing token claims to have "
            "Calendar access, but Google Calendar "
            "rejected the actual access token."
        )

        print()
        print(
            "Deleting the stale token and "
            "starting a fresh OAuth authorization..."
        )

        delete_token()

        credentials = None

    # ========================================================
    # NEW AUTHORIZATION
    # ========================================================

    credentials = authorize_google()

    print()
    print("=" * 60)
    print("GOOGLE AUTHENTICATION SUCCESS")
    print("=" * 60)

    print()
    print(
        "VALID:",
        credentials.valid
    )

    display_scopes(
        "Verified scopes:",
        set(
            credentials.scopes or []
        )
    )

    print()
    print(
        "TOKEN FILE:",
        TOKEN_FILE
    )

    return credentials


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    credentials = (
        get_google_credentials()
    )

    print()
    print("=" * 60)
    print("GOOGLE AUTHENTICATION TEST PASSED")
    print("=" * 60)

    print()
    print(
        "VALID:",
        credentials.valid
    )

    print()
    print(
        "SCOPES:"
    )

    for scope in sorted(
        credentials.scopes or []
    ):

        print(
            "-",
            scope
        )

    print()
    print(
        "CALENDAR API:"
    )

    print(
        "ACCESS VERIFIED"
    )

    print()
    print(
        "TOKEN FILE:"
    )

    print(
        TOKEN_FILE
    )

    print()
    print(
        "=" * 60
    )