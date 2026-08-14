from ai_analyzer import clean_email

print("EMAIL CLEANER TEST")
print("=" * 50)

email = "[vasanth@gmail.com](mailto:vasanth@gmail.com)"

result = clean_email(email)

print("INPUT:")
print(email)

print("\nOUTPUT:")
print(result)

print("\nEXPECTED:")
print("vasanth@gmail.com")

print("\nRESULT:")

if result == "vasanth@gmail.com":
    print("PASS")
else:
    print("FAIL")