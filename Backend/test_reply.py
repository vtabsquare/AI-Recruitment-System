from gmail_reader import read_candidate_replies

emails = read_candidate_replies()

if not emails:
    print("No candidate replies found.")

else:

    for email in emails:

        print("=" * 60)

        print("FROM:")
        print(email["from"])

        print()

        print("SUBJECT:")
        print(email["subject"])

        print()

        print("THREAD ID:")
        print(email["thread_id"])

        print()

        print("MESSAGE ID:")
        print(email["message_id"])

        print()

        print("BODY:")
        print(email["body"])