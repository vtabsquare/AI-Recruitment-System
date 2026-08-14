from gmail_reader import read_candidate_replies
from reply_cleaner import clean_reply

emails = read_candidate_replies()

body = emails[0]["body"]

cleaned = clean_reply(body)

print(repr(cleaned))