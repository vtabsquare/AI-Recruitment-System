import time

from gmail_reader import read_candidate_replies
from reply_analyzer import analyze_reply


print("🤖 VTAB AI Recruitment Agent Started...\n")

processed_messages = set()


while True:

    emails = read_candidate_replies()

    if emails:

        for email in emails:

            if email["message_id"] in processed_messages:
                continue

            print("=" * 60)
            print("New Candidate Reply Found\n")

            print(email["body"])
            print()

            result = analyze_reply(email["body"])

            print("AI Decision:")
            print(result)

            processed_messages.add(email["message_id"])

    else:

        print("No new replies...")

    print("\nChecking again in 30 seconds...\n")

    time.sleep(30)