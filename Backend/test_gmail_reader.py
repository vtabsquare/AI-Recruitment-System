from gmail_reader import read_candidate_replies


print("=" * 60)
print("VTAB SQUARE GMAIL REPLY TEST")
print("=" * 60)

print()
print("Reading unread recruitment emails...")
print()

replies = read_candidate_replies()


if not replies:

    print("NO RECRUITMENT REPLIES FOUND.")

else:

    print(
        f"FOUND {len(replies)} REPLY/REPLIES"
    )

    print()

    for index, reply in enumerate(
        replies,
        start=1
    ):

        print("=" * 60)

        print(
            f"REPLY {index}"
        )

        print("=" * 60)

        print(
            "Message ID:",
            reply["message_id"]
        )

        print(
            "Thread ID:",
            reply["thread_id"]
        )

        print(
            "From:",
            reply["from"]
        )

        print(
            "To:",
            reply["to"]
        )

        print(
            "Subject:",
            reply["subject"]
        )

        print(
            "Date:",
            reply["date"]
        )

        print()

        print(
            "BODY:"
        )

        print(
            reply["body"]
        )

        print()