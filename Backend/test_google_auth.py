from google_auth import get_google_credentials


print()
print("=" * 60)
print("VTAB SQUARE GOOGLE AUTHENTICATION TEST")
print("=" * 60)

print()
print("Requesting Gmail + Google Calendar permissions...")

credentials = get_google_credentials()

print()
print("=" * 60)
print("GOOGLE AUTHENTICATION SUCCESS")
print("=" * 60)

print()
print("Token is valid.")

print()
print("Granted scopes:")

for scope in credentials.scopes or []:

    print(
        f"- {scope}"
    )

print()
print("=" * 60)