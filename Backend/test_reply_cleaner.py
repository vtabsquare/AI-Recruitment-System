from reply_cleaner import clean_reply


test_email = """
Yes, I am interested in the data analyst position. I am available tomorrow after 4 pm.

On Sat, 8 Aug 2026, 4:46 pm VTAB Square Recruitment
<vasanththiru786573@11837687.brevosend.com> wrote:

> Application Shortlisted
> Dear VASANTH KUMAR T,
> We are pleased to inform you that your application for Data Analyst at VTAB Square has been shortlisted.
> Our recruitment team will contact you with the next steps regarding the interview process.
> Application ID: VTAB-2026-7523
> Regards,
> VTAB Square Recruitment Team
"""


print("=" * 60)
print("VTAB SQUARE REPLY CLEANER TEST")
print("=" * 60)

print()
print("ORIGINAL EMAIL:")
print(test_email)

cleaned = clean_reply(test_email)

print()
print("=" * 60)
print("CLEANED REPLY")
print("=" * 60)

print(cleaned)

print()
print("=" * 60)

expected = (
    "Yes, I am interested in the data analyst position. "
    "I am available tomorrow after 4 pm."
)

if cleaned == expected:

    print("REPLY CLEANER: PASSED")

else:

    print("REPLY CLEANER: FAILED")

    print()
    print("Expected:")
    print(repr(expected))

    print()
    print("Actual:")
    print(repr(cleaned))