import re

from reply_cleaner import clean_reply
from gmail_reader import read_candidate_replies
from reply_analyzer import analyze_reply

emails = read_candidate_replies()

if not emails:
    print("No candidate replies found.")

else:

    latest = emails[0]

    cleaned_reply = clean_reply(latest["body"])

    print("Candidate Reply:")
    print(cleaned_reply)
    print()

    print("EMAIL SUBJECT:")
    print(latest["subject"])
    print()

    # Extract Application ID
    match = re.search(r"VTAB-\d{4}-\d{4}", latest["subject"])

    if match:
        application_id = match.group()
    else:
        application_id = "Unknown"

    # Extract only the email address
    email_match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        latest["from"]
    )

    if email_match:
        candidate_email = email_match.group()
    else:
        candidate_email = "Unknown"

    result = analyze_reply(cleaned_reply)

    result["application_id"] = application_id
    result["candidate_email"] = candidate_email

    print("AI Result:")
    print(result)