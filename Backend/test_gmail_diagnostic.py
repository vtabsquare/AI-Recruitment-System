from gmail_reader import get_gmail_service


print("=" * 60)
print("GMAIL DIAGNOSTIC")
print("=" * 60)

service = get_gmail_service()

print()
print("Gmail authentication: SUCCESS")
print()
print("Checking recent emails...")
print()


results = (
    service
    .users()
    .messages()
    .list(
        userId="me",
        q="newer_than:7d",
        maxResults=20
    )
    .execute()
)


messages = results.get(
    "messages",
    []
)


if not messages:

    print("No emails found in the last 7 days.")
    raise SystemExit


print(
    f"Found {len(messages)} recent email(s)."
)

print()


for index, message in enumerate(
    messages,
    start=1
):

    msg = (
        service
        .users()
        .messages()
        .get(
            userId="me",
            id=message["id"],
            format="metadata",
            metadataHeaders=[
                "Subject",
                "From",
                "To",
                "Date"
            ]
        )
        .execute()
    )

    headers = (
        msg
        .get("payload", {})
        .get("headers", [])
    )

    subject = ""
    sender = ""
    recipient = ""
    date = ""

    for header in headers:

        name = header.get(
            "name",
            ""
        ).lower()

        value = header.get(
            "value",
            ""
        )

        if name == "subject":
            subject = value

        elif name == "from":
            sender = value

        elif name == "to":
            recipient = value

        elif name == "date":
            date = value

    labels = msg.get(
        "labelIds",
        []
    )

    print("=" * 60)

    print(
        f"EMAIL {index}"
    )

    print("=" * 60)

    print(
        "Subject:",
        subject
    )

    print(
        "From:",
        sender
    )

    print(
        "To:",
        recipient
    )

    print(
        "Date:",
        date
    )

    print(
        "Labels:",
        labels
    )

    print()