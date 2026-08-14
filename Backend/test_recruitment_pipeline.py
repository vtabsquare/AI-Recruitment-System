from recruitment_service import process_candidate


print("\nStarting complete recruitment pipeline...\n")


result = process_candidate(
    "resume.pdf",
    "Data Analyst"
)


print("\n")
print("=" * 60)
print("FINAL RESULT")
print("=" * 60)

print(result)