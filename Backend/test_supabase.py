from supabase_db import supabase


print("Connecting to Supabase...")

response = (
    supabase
    .table("job_roles")
    .select("id, role_name, minimum_cgpa, required_skill_count")
    .execute()
)


print("\nJob Roles:")
print(response.data)