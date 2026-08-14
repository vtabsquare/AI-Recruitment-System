import os
import json
import base64
import re
import email
import base64 as b64_module
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ============================================================
# GMAIL PERMISSION
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


# ============================================================
# RECRUITMENT CONFIGURATION
# ============================================================

COMPANY_EMAIL = "vasanththiru786573@gmail.com"

RESUME_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx"
}

APPLICATION_KEYWORDS = {
    "application",
    "apply",
    "applying",
    "job",
    "career",
    "resume",
    "cv",
    "vacancy",
    "position",
    "candidate"
}

ROLE_KEYWORDS = {
    "data analyst": "Data Analyst",
    "python developer": "Python Developer",
    "ai engineer": "AI Engineer",
    "machine learning engineer": "Machine Learning Engineer",
    "software developer": "Software Developer",
    "software engineer": "Software Engineer",
    "data scientist": "Data Scientist"
}

DEFAULT_JOB_ROLE = "Data Analyst"

RESUME_DIRECTORY = "incoming_resumes"

PROCESSED_APPLICATION_FILE = (
    "processed_application_emails.json"
)


# ============================================================
# AUTOMATED / NON-CANDIDATE EMAIL DOMAINS
# ============================================================

IGNORED_SENDER_DOMAINS = {
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "brevosend.com",
    "mailin.fr",
    "canva.com",
    "supabase.com",
    "salesforce.com",
    "wipro.com",
}


# ============================================================
# CREATE GMAIL SERVICE
# ============================================================

def get_gmail_service():
    """
    Create and return the authenticated Gmail API service.
    Loads token from GOOGLE_TOKEN_JSON env var (production/Render)
    or from token.json file (local development).
    Returns None gracefully if credentials are unavailable.
    """

    creds = None

    # --- Production: load from environment variable ---
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        try:
            token_data = base64.b64decode(token_env).decode("utf-8")
            creds = Credentials.from_authorized_user_info(
                json.loads(token_data),
                SCOPES
            )
        except Exception as error:
            print("[Gmail] Could not load token from GOOGLE_TOKEN_JSON:", error)
            return None

    # --- Local dev: load from file ---
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    else:
        print("[Gmail] No credentials available (no GOOGLE_TOKEN_JSON env var and no token.json). Gmail features disabled.")
        return None

    # Refresh token if expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token back to file (local dev only)
                if not token_env and os.path.exists("token.json"):
                    with open("token.json", "w", encoding="utf-8") as token:
                        token.write(creds.to_json())
            except Exception as error:
                print("[Gmail] Token refresh failed:", error)
                return None
        else:
            # Cannot open browser on server — fail gracefully
            print("[Gmail] Token invalid and cannot be refreshed. Gmail features disabled.")
            return None

    return build("gmail", "v1", credentials=creds)



# ============================================================
# DECODE GMAIL BODY
# ============================================================

def decode_gmail_body(data):

    if not data:
        return ""

    try:

        padding = "=" * (
            -len(data) % 4
        )

        decoded = base64.urlsafe_b64decode(
            data + padding
        )

        return decoded.decode(
            "utf-8",
            errors="replace"
        )

    except Exception:

        return ""


# ============================================================
# EXTRACT TEXT FROM EMAIL PAYLOAD
# ============================================================

def extract_text_from_payload(payload):

    if not payload:
        return ""

    mime_type = payload.get(
        "mimeType",
        ""
    )

    body = payload.get(
        "body",
        {}
    ) or {}

    data = body.get(
        "data"
    )

    # --------------------------------------------------------
    # TEXT / PLAIN
    # --------------------------------------------------------

    if (
        mime_type == "text/plain"
        and data
    ):

        text = decode_gmail_body(
            data
        )

        if text.strip():
            return text

    # --------------------------------------------------------
    # TEXT / HTML
    # --------------------------------------------------------

    if (
        mime_type == "text/html"
        and data
    ):

        text = decode_gmail_body(
            data
        )

        if text.strip():

            text = re.sub(
                r"<[^>]+>",
                " ",
                text
            )

            text = re.sub(
                r"\s+",
                " ",
                text
            )

            return text.strip()

    # --------------------------------------------------------
    # NESTED MIME PARTS
    # --------------------------------------------------------

    for part in payload.get(
        "parts",
        []
    ):

        text = extract_text_from_payload(
            part
        )

        if text.strip():
            return text

    return ""


# ============================================================
# GET EMAIL HEADER
# ============================================================

def get_header(
    headers,
    name
):

    target = name.lower()

    for header in headers:

        if (
            header.get(
                "name",
                ""
            ).lower()
            == target
        ):

            return header.get(
                "value",
                ""
            )

    return ""


# ============================================================
# EXTRACT EMAIL ADDRESS
# ============================================================

def extract_email_address(
    sender
):

    if not sender:
        return ""

    match = re.search(
        r"<([^<>@\s]+@[^<>@\s]+)>",
        sender
    )

    if match:

        return (
            match.group(1)
            .lower()
            .strip()
        )

    match = re.search(
        r"[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}",
        sender
    )

    if match:

        return (
            match.group(0)
            .lower()
            .strip()
        )

    return ""


# ============================================================
# EXTRACT CANDIDATE NAME
# ============================================================

def extract_candidate_name(
    sender
):

    if not sender:
        return "Candidate"

    sender = str(sender).strip()

    match = re.match(
        r'["\']?(.+?)["\']?\s*<[^<>]+>',
        sender
    )

    if match:

        name = (
            match.group(1)
            .strip()
            .strip("\"'")
        )

        if name:
            return name

    email = extract_email_address(
        sender
    )

    if email:

        username = email.split(
            "@",
            1
        )[0]

        username = re.sub(
            r"[._-]+",
            " ",
            username
        )

        return username.title()

    return "Candidate"


# ============================================================
# CHECK AUTOMATED SENDER
# ============================================================

def is_ignored_sender(
    sender_email
):

    if not sender_email:
        return True

    sender_email = (
        sender_email
        .lower()
        .strip()
    )

    # Never treat the company's own email as a candidate.
    if sender_email == COMPANY_EMAIL.lower():
        return True

    if "@" not in sender_email:
        return True

    domain = sender_email.rsplit(
        "@",
        1
    )[1]

    if domain in IGNORED_SENDER_DOMAINS:
        return True

    if domain.endswith(
        ".brevosend.com"
    ):
        return True

    return False


# ============================================================
# CHECK WHETHER EMAIL IS SENT TO COMPANY
# ============================================================

def is_sent_to_company(
    recipient
):

    if not recipient:
        return False

    recipient_lower = (
        recipient
        .lower()
        .strip()
    )

    return (
        COMPANY_EMAIL.lower()
        in recipient_lower
    )


# ============================================================
# DOWNLOAD GMAIL ATTACHMENT
# ============================================================

def download_gmail_attachment(
    service,
    message_id,
    attachment_id,
    filename,
    output_directory=RESUME_DIRECTORY
):

    output_dir = Path(
        output_directory
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    attachment = (
        service
        .users()
        .messages()
        .attachments()
        .get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        )
        .execute()
    )

    data = attachment.get(
        "data"
    )

    if not data:

        raise ValueError(
            f"No attachment data found "
            f"for '{filename}'."
        )

    padding = "=" * (
        -len(data) % 4
    )

    file_data = base64.urlsafe_b64decode(
        data + padding
    )

    safe_filename = Path(
        filename
    ).name

    output_path = (
        output_dir
        / safe_filename
    )

    # Prevent overwriting.
    if output_path.exists():

        stem = output_path.stem
        suffix = output_path.suffix

        output_path = (
            output_dir
            / (
                f"{stem}_"
                f"{message_id[:8]}"
                f"{suffix}"
            )
        )

    with open(
        output_path,
        "wb"
    ) as file:

        file.write(
            file_data
        )

    return str(
        output_path
    )


# ============================================================
# FIND RESUME ATTACHMENTS
# ============================================================

def find_resume_attachments(
    service,
    message_id,
    payload,
    output_directory=RESUME_DIRECTORY
):

    resumes = []

    if not payload:
        return resumes

    filename = (
        payload.get(
            "filename",
            ""
        )
        or ""
    ).strip()

    body = (
        payload.get(
            "body",
            {}
        )
        or {}
    )

    attachment_id = body.get(
        "attachmentId"
    )

    if (
        filename
        and attachment_id
    ):

        extension = (
            Path(filename)
            .suffix
            .lower()
        )

        if extension in RESUME_EXTENSIONS:

            path = download_gmail_attachment(
                service=service,
                message_id=message_id,
                attachment_id=attachment_id,
                filename=filename,
                output_directory=output_directory
            )

            resumes.append(
                path
            )

    for part in payload.get(
        "parts",
        []
    ):

        resumes.extend(
            find_resume_attachments(
                service=service,
                message_id=message_id,
                payload=part,
                output_directory=output_directory
            )
        )

    return resumes


# ============================================================
# CHECK WHETHER EMAIL LOOKS LIKE APPLICATION
# ============================================================

def is_candidate_application_email(
    subject,
    body,
    resume_paths
):

    if not resume_paths:
        return False

    text = (
        f"{subject} {body}"
        .lower()
    )

    # --------------------------------------------------------
    # Application wording
    # --------------------------------------------------------

    for keyword in APPLICATION_KEYWORDS:

        if keyword in text:
            return True

    # --------------------------------------------------------
    # Resume filename fallback
    # --------------------------------------------------------

    for resume_path in resume_paths:

        filename = (
            Path(resume_path)
            .name
            .lower()
        )

        if (
            "resume" in filename
            or "cv" in filename
        ):

            return True

    return False


# ============================================================
# DETECT JOB ROLE
# ============================================================

def detect_job_role(
    subject,
    body,
    default_role=DEFAULT_JOB_ROLE
):

    text = (
        f"{subject} {body}"
        .lower()
    )

    for keyword, role in ROLE_KEYWORDS.items():

        if keyword in text:
            return role

    return default_role


# ============================================================
# LOAD PROCESSED APPLICATION EMAIL IDS
# ============================================================

def load_processed_application_ids():

    path = Path(
        PROCESSED_APPLICATION_FILE
    )

    if not path.exists():
        return set()

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            list
        ):

            return set()

        return set(
            str(item)
            for item in data
        )

    except Exception:

        return set()


# ============================================================
# SAVE PROCESSED APPLICATION EMAIL IDS
# ============================================================

def save_processed_application_ids(
    processed_ids
):

    with open(
        PROCESSED_APPLICATION_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            sorted(processed_ids),
            file,
            indent=2
        )


# ============================================================
# MARK APPLICATION EMAIL PROCESSED
# ============================================================

def mark_application_email_processed(
    message_id
):

    processed_ids = (
        load_processed_application_ids()
    )

    processed_ids.add(
        message_id
    )

    save_processed_application_ids(
        processed_ids
    )


# ============================================================
# GET FULL GMAIL MESSAGE
# ============================================================

def get_full_gmail_message(
    service,
    message_id
):

    return (
        service
        .users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full"
        )
        .execute()
    )


# ============================================================
# READ NEW CANDIDATE APPLICATIONS
# ============================================================

def read_new_candidate_applications(
    default_role=DEFAULT_JOB_ROLE
):

    service = get_gmail_service()

    processed_ids = (
        load_processed_application_ids()
    )

    print()
    print("=" * 60)
    print("VTAB SQUARE AI RECRUITMENT GMAIL MONITOR")
    print("=" * 60)

    print()
    print(
        "Checking company recruitment Gmail..."
    )

    print(
        "Company mailbox:",
        COMPANY_EMAIL
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Search ONLY incoming mail:
    # - sent to company recruitment mailbox
    # - has an attachment
    # - newer than 7 days
    # - not sent by company
    #
    # This prevents the reader from scanning normal inbox mail.
    # --------------------------------------------------------

    query = (
        f"in:inbox "
        f"to:{COMPANY_EMAIL} "
        "newer_than:7d "
        "has:attachment "
        f"-from:{COMPANY_EMAIL}"
    )

    print()
    print(
        "Gmail application filter:"
    )

    print(
        query
    )

    results = (
        service
        .users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=50
        )
        .execute()
    )

    messages = results.get(
        "messages",
        []
    )

    print()
    print(
        "Incoming attachment emails found:",
        len(messages)
    )

    if not messages:

        print()
        print(
            "No new candidate applications found."
        )

        return []

    applications = []

    # ========================================================
    # PROCESS EACH MESSAGE
    # ========================================================

    for message in messages:

        message_id = message.get(
            "id"
        )

        if not message_id:
            continue

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        if message_id in processed_ids:
            continue

        try:

            msg = get_full_gmail_message(
                service,
                message_id
            )

        except Exception as error:

            print(
                "Could not read Gmail message:",
                error
            )

            continue

        payload = msg.get(
            "payload",
            {}
        )

        headers = payload.get(
            "headers",
            []
        )

        subject = get_header(
            headers,
            "Subject"
        )

        sender = get_header(
            headers,
            "From"
        )

        recipient = get_header(
            headers,
            "To"
        )

        date = get_header(
            headers,
            "Date"
        )

        thread_id = msg.get(
            "threadId",
            ""
        )

        # ----------------------------------------------------
        # SENDER
        # ----------------------------------------------------

        candidate_email = (
            extract_email_address(
                sender
            )
        )

        # ----------------------------------------------------
        # IGNORE AUTOMATED SERVICES
        # ----------------------------------------------------

        if is_ignored_sender(
            candidate_email
        ):
            continue

        # ----------------------------------------------------
        # MUST BE SENT TO COMPANY
        # ----------------------------------------------------

        if not is_sent_to_company(
            recipient
        ):
            continue

        # ----------------------------------------------------
        # CANDIDATE NAME
        # ----------------------------------------------------

        candidate_name = (
            extract_candidate_name(
                sender
            )
        )

        # ----------------------------------------------------
        # EMAIL BODY
        # ----------------------------------------------------

        body = (
            extract_text_from_payload(
                payload
            )
        )

        # ----------------------------------------------------
        # RESUME ATTACHMENTS
        # ----------------------------------------------------

        try:

            resume_paths = (
                find_resume_attachments(
                    service=service,
                    message_id=message_id,
                    payload=payload
                )
            )

        except Exception as error:

            print(
                "Could not download resume:",
                error
            )

            continue

        # No supported resume = not a candidate application.
        if not resume_paths:
            continue

        # ----------------------------------------------------
        # CONFIRM APPLICATION
        # ----------------------------------------------------

        if not is_candidate_application_email(
            subject=subject,
            body=body,
            resume_paths=resume_paths
        ):

            continue

        # ----------------------------------------------------
        # DETECT JOB ROLE
        # ----------------------------------------------------

        role = detect_job_role(
            subject=subject,
            body=body,
            default_role=default_role
        )

        # ----------------------------------------------------
        # CANDIDATE APPLICATION DETECTED
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("NEW CANDIDATE APPLICATION DETECTED")
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
            role
        )

        print(
            "Resume:",
            resume_paths
        )

        print(
            "Status:",
            "READY FOR AI VALIDATION"
        )

        # ----------------------------------------------------
        # APPLICATION OBJECT
        # ----------------------------------------------------

        application = {

            "message_id":
                message_id,

            "thread_id":
                thread_id,

            "candidate_email":
                candidate_email,

            "candidate_name":
                candidate_name,

            "sender":
                sender,

            "recipient":
                recipient,

            "subject":
                subject,

            "date":
                date,

            "body":
                body,

            "job_role":
                role,

            "resume_paths":
                resume_paths
        }

        applications.append(
            application
        )

    # ========================================================
    # RESULT
    # ========================================================

    print()
    print("=" * 60)

    if applications:

        print(
            f"Found {len(applications)} "
            "candidate application(s)."
        )

    else:

        print(
            "No new candidate applications found."
        )

    print("=" * 60)

    return applications


# ============================================================
# TEST GMAIL CONNECTION
# ============================================================

def test_gmail_connection():

    service = get_gmail_service()

    profile = (
        service
        .users()
        .getProfile(
            userId="me"
        )
        .execute()
    )

    return profile.get(
        "emailAddress",
        ""
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("VTAB SQUARE GMAIL READER")
    print("=" * 60)

    try:

        email_address = (
            test_gmail_connection()
        )

        print()
        print(
            "Gmail authentication: SUCCESS"
        )

        print(
            "Connected account:",
            email_address
        )

        print()

        applications = (
            read_new_candidate_applications()
        )

        if applications:

            for index, application in enumerate(
                applications,
                start=1
            ):

                print()
                print(
                    "-" * 60
                )

                print(
                    f"APPLICATION {index}"
                )

                print(
                    "-" * 60
                )

                print(
                    "Candidate:",
                    application[
                        "candidate_name"
                    ]
                )

                print(
                    "Email:",
                    application[
                        "candidate_email"
                    ]
                )

                print(
                    "Job role:",
                    application[
                        "job_role"
                    ]
                )

                print(
                    "Resume:",
                    application[
                        "resume_paths"
                    ]
                )

        else:

            print()
            print(
                "No candidate applications "
                "are waiting for processing."
            )

    except Exception as error:

        print()
        print(
            "GMAIL READER FAILED"
        )

        print(
            type(error).__name__
        )

        print(
            str(error)
        )

        raise