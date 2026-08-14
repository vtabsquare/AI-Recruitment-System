from supabase_db import get_job_roles, get_job_role


print("ACTIVE JOB ROLES")
print("================")

roles = get_job_roles()

for role in roles:
    print(
        role["role_name"],
        "| CGPA:",
        role["minimum_cgpa"],
        "| Required Skills:",
        role["required_skill_count"]
    )


print("\nDATA ANALYST REQUIREMENTS")
print("=========================")

data_analyst = get_job_role("Data Analyst")

print(data_analyst)