from ai_analyzer import extract_plain_email


tests = [
    (
        "[vasanth@gmail.com](mailto:vasanth@gmail.com)",
        "vasanth@gmail.com",
    ),
    (
        "[vasanth@gmail.com](mailto\\:vasanth@gmail.com)",
        "vasanth@gmail.com",
    ),
    (
        "[vasanththiru786573@gmail.com](mailto\\:vasanththiru786573@gmail.com)",
        "vasanththiru786573@gmail.com",
    ),
    (
        "Email: vasanth@gmail.com",
        "vasanth@gmail.com",
    ),
]


print("EMAIL EXTRACTION TEST")
print("=====================")

all_passed = True

for number, (value, expected) in enumerate(tests, 1):
    result = extract_plain_email(value)
    passed = result == expected

    print()
    print(f"TEST {number}")
    print("Input    :", repr(value))
    print("Output   :", repr(result))
    print("Expected :", repr(expected))
    print("PASS     :", passed)

    if not passed:
        all_passed = False

print()

if all_passed:
    print("ALL EMAIL TESTS PASSED")
else:
    print("EMAIL TEST FAILED")
    raise SystemExit(1)