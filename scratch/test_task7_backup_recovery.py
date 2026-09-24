"""
Task 7: Backup & Recovery Test Suite
-------------------------------------
Comprehensive validation of:
1. docs/BACKUP_AND_RECOVERY.md completeness, scenarios, steps, and secrets hygiene.
2. scripts/backup_db.py standalone operational execution, verification, and dry-run.
3. Backup integrity validation (SHA-256, JSON structure, storage coupling).
4. Zero runtime impact on Backend/app.py and Frontend/src/App.jsx.
"""

import sys
import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "Backend"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

passed_count = 0
failed_count = 0


def check(name: str, condition: bool, details: str = ""):
    global passed_count, failed_count
    if condition:
        print(f"  [PASS] {name}")
        passed_count += 1
    else:
        print(f"  [FAIL] {name} - {details}")
        failed_count += 1


print("================================================================")
print("TASK 7: BACKUP & DISASTER RECOVERY TEST SUITE")
print("================================================================")

# ==============================================================================
# SECTION 1: DISASTER RECOVERY DOCUMENTATION (docs/BACKUP_AND_RECOVERY.md)
# ==============================================================================
print("\n=== Section 1: Disaster Recovery Documentation Tests ===")

doc_path = DOCS_DIR / "BACKUP_AND_RECOVERY.md"
check("Documentation file exists at docs/BACKUP_AND_RECOVERY.md", doc_path.exists())

doc_text = ""
if doc_path.exists():
    with open(doc_path, "r", encoding="utf-8") as f:
        doc_text = f.read()

check("Documentation is non-empty (> 1000 characters)", len(doc_text) > 1000)

# Check 10-step recovery procedure
for step_num in range(1, 11):
    step_pattern = f"Step {step_num}"
    check(f"Documentation covers recovery Step {step_num}", step_pattern in doc_text)

# Check 5 disaster scenarios
for scenario_letter in ["A", "B", "C", "D", "E"]:
    scenario_pattern = f"Scenario {scenario_letter}"
    check(f"Documentation covers Disaster Scenario {scenario_letter}", scenario_pattern in doc_text)

# Check explicit RPO / RTO designations
check("RPO explicitly marked 'To be defined by system owner'", "RPO" in doc_text and "To be defined by system owner" in doc_text)
check("RTO explicitly marked 'To be defined by system owner'", "RTO" in doc_text and "To be defined by system owner" in doc_text)

# Check retention policy designation
check("Retention policy marked 'To be decided by the deployment/operations owner'", "To be decided by the deployment/operations owner" in doc_text)

# Check database scope distinguishes schema vs data vs complete
check("Documentation explains Schema backup", "schema" in doc_text.lower() and "--schema-only" in doc_text)
check("Documentation explains Data backup", "data" in doc_text.lower() and ("--data-only" in doc_text or "data backup" in doc_text.lower()))
check("Documentation explains Complete backup", "complete" in doc_text.lower() and ("pg_dump" in doc_text or "full" in doc_text.lower()))

# Check candidate document storage coupling
check("Documentation explains candidate-documents bucket", "candidate-documents" in doc_text)
check("Documentation details storage_path coupling with documents table", "storage_path" in doc_text and "documents" in doc_text)
check("Documentation emphasizes database and storage must be restored together", "restored together" in doc_text.lower() or "backed up and restored together" in doc_text.lower())

# Check secrets hygiene placeholders
check("Documentation uses '<restore from secure secret store>' placeholders", "<restore from secure secret store>" in doc_text)
check("Documentation warns against committing plaintext secrets", "zero plaintext secrets" in doc_text.lower() or "never commit real secrets" in doc_text.lower())


# ==============================================================================
# SECTION 2: STANDALONE BACKUP CLI SCRIPT (scripts/backup_db.py)
# ==============================================================================
print("\n=== Section 2: Standalone Backup CLI Script Tests ===")

script_path = SCRIPTS_DIR / "backup_db.py"
check("Backup script exists at scripts/backup_db.py", script_path.exists())

import backup_db

# Check independence from app.py
with open(script_path, "r", encoding="utf-8") as f:
    script_source = f.read()

check("backup_db.py does NOT import app.py", "from app import" not in script_source and "import app" not in script_source)
check("backup_db.py defines all 14 active database tables", len(backup_db.DEFAULT_TABLES) == 14)

# Test mask_secret helper
check("mask_secret handles empty string safely", backup_db.mask_secret("") == "[NOT SET]")
check("mask_secret masks short strings safely", backup_db.mask_secret("secret") == "[REDACTED]")
check("mask_secret masks long tokens safely", backup_db.mask_secret("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9") == "eyJ...CJ9")

# Test calculate_sha256 helper
with tempfile.NamedTemporaryFile("w", delete=False) as tf:
    tf.write("test_content_for_sha256")
    temp_file_path = Path(tf.name)

try:
    computed_hash = backup_db.calculate_sha256(temp_file_path)
    # sha256 of "test_content_for_sha256"
    check("calculate_sha256 computes valid 64-char hex digest", len(computed_hash) == 64 and all(c in "0123456789abcdef" for c in computed_hash))
finally:
    if temp_file_path.exists():
        temp_file_path.unlink()

# Test CLI --help execution
help_result = subprocess.run(
    [sys.executable, str(script_path), "--help"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
check("backup_db.py --help returns exit code 0", help_result.returncode == 0)
check("backup_db.py --help output contains usage instructions", "usage: backup_db.py" in help_result.stdout)


# ==============================================================================
# SECTION 3: BACKUP EXECUTION, INTEGRITY & VERIFICATION DRILL
# ==============================================================================
print("\n=== Section 3: Backup Execution & Verification Drill ===")

temp_backup_dir = Path(tempfile.mkdtemp(prefix="test_backup_"))

try:
    # Create mock Supabase client returning sample data
    mock_supabase = MagicMock()

    def mock_table_handler(table_name):
        mock_query = MagicMock()
        sample_records = [
            {"id": f"{table_name}_1", "name": f"Item 1 in {table_name}", "created_at": "2026-09-23T12:00:00Z"},
            {"id": f"{table_name}_2", "name": f"Item 2 in {table_name}", "created_at": "2026-09-23T12:05:00Z"}
        ]
        if table_name == "documents":
            sample_records[0]["storage_path"] = "app_001/resume_abc.pdf"
            sample_records[1]["storage_path"] = "app_002/degree_xyz.pdf"

        mock_query.select.return_value.range.return_value.execute.return_value = MagicMock(data=sample_records)
        mock_query.select.return_value.limit.return_value.execute.return_value = MagicMock(data=sample_records)
        return mock_query

    mock_supabase.table.side_effect = mock_table_handler

    # Test Dry-Run Mode
    dry_run_code = backup_db.run_backup(
        output_dir=temp_backup_dir,
        tables=["candidates", "applications"],
        dry_run=True,
        client=mock_supabase
    )
    check("Dry-run execution returns exit code 0", dry_run_code == 0)
    created_folders = list(temp_backup_dir.glob("backup_*"))
    check("Dry-run does NOT write backup folders to disk", len(created_folders) == 0)

    # Test Live Export Mode with post-backup verification
    live_exit_code = backup_db.run_backup(
        output_dir=temp_backup_dir,
        tables=backup_db.DEFAULT_TABLES,
        dry_run=False,
        verify=True,
        client=mock_supabase
    )
    check("Live backup execution returns exit code 0", live_exit_code == 0)

    created_folders = list(temp_backup_dir.glob("backup_*"))
    check("Live backup created exactly one timestamped directory", len(created_folders) == 1)

    backup_folder = created_folders[0] if created_folders else None

    if backup_folder:
        metadata_file = backup_folder / "metadata.json"
        check("metadata.json was created", metadata_file.exists())

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        check("metadata.json contains created_at timestamp", "created_at" in metadata)
        check("metadata.json contains all 14 tables in summary", len(metadata.get("tables", {})) == 14)
        check("metadata.json total_records matches expected count", metadata.get("total_records") == 28)

        # Check storage manifest
        storage_manifest_file = backup_folder / "storage_manifest.json"
        check("storage_manifest.json was created", storage_manifest_file.exists())
        with open(storage_manifest_file, "r", encoding="utf-8") as f:
            storage_manifest = json.load(f)

        check("storage_manifest references candidate-documents bucket", storage_manifest.get("bucket") == "candidate-documents")
        check("storage_manifest extracted 2 document storage paths", len(storage_manifest.get("storage_paths", [])) == 2)
        check("storage_manifest contains app_001/resume_abc.pdf", "app_001/resume_abc.pdf" in storage_manifest.get("storage_paths", []))

        # Check that individual table files exist and are non-empty
        all_tables_valid = True
        for t in backup_db.DEFAULT_TABLES:
            t_file = backup_folder / f"{t}.json"
            if not t_file.exists() or t_file.stat().st_size == 0:
                all_tables_valid = False
        check("All 14 table JSON files exist and are non-empty", all_tables_valid)

        # Test verification helper on the valid directory
        is_valid, errors = backup_db.verify_backup_directory(backup_folder)
        check("verify_backup_directory confirms backup is 100% valid", is_valid and len(errors) == 0)

        # Test verification catches tampered file
        tampered_file = backup_folder / "candidates.json"
        with open(tampered_file, "a", encoding="utf-8") as f:
            f.write("\n// corrupted")
        is_valid_after_tampering, errors_after = backup_db.verify_backup_directory(backup_folder)
        check("verify_backup_directory catches corrupted / tampered file", not is_valid_after_tampering and len(errors_after) > 0)

finally:
    if temp_backup_dir.exists():
        shutil.rmtree(temp_backup_dir, ignore_errors=True)


# ==============================================================================
# SECTION 4: RUNTIME APPLICATION ISOLATION & SAFETY VERIFICATION
# ==============================================================================
print("\n=== Section 4: Runtime Application Isolation & Safety ===")

# Verify Backend/app.py was not modified for Task 7
with open(BACKEND_DIR / "app.py", "r", encoding="utf-8") as f:
    app_source = f.read()

check("Backend/app.py does NOT import backup_db", "backup_db" not in app_source)
check("Backend/app.py does NOT execute backup on startup", "run_backup" not in app_source)
check("Backend/app.py has zero backup endpoints added", "/api/backup" not in app_source)

# Verify Frontend/src/App.jsx was not modified for Task 7
frontend_app_path = REPO_ROOT / "Frontend" / "src" / "App.jsx"
with open(frontend_app_path, "r", encoding="utf-8") as f:
    frontend_source = f.read()

check("Frontend/src/App.jsx does NOT contain backup UI or endpoints", "backup" not in frontend_source.lower())


# ==============================================================================
# FINAL RESULTS
# ==============================================================================
print("\n================================================================")
print(f"Task 7 Test Results: {passed_count}/{passed_count + failed_count} Passed ({failed_count} Failed)")
print("================================================================")

if failed_count > 0:
    sys.exit(1)
