#!/usr/bin/env python3
"""
scripts/backup_db.py
====================
Standalone Operational Backup CLI for VTAB Square AI Recruitment System.

Features:
- Independent execution: Does NOT import Backend/app.py and never runs during app startup.
- Exports structured data from all 14 Supabase relational tables.
- Generates metadata manifest with execution timestamp, record counts, file sizes, and SHA-256 checksums.
- Includes candidate document storage references manifest.
- Provides --verify and --dry-run modes for safe disaster recovery drills.
- Zero plaintext secrets printed to console or logs.

Usage:
    python scripts/backup_db.py
    python scripts/backup_db.py --output-dir /var/backups/recruitment --verify
    python scripts/backup_db.py --tables candidates,applications,documents
    python scripts/backup_db.py --dry-run
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure Backend directory is on sys.path for config access if run from repository root
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "Backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# All 14 active database tables in the AI Recruitment System
DEFAULT_TABLES = [
    "job_roles",
    "job_role_skills",
    "candidates",
    "applications",
    "staff_users",
    "ai_evaluations",
    "interviews",
    "interview_feedback",
    "document_requests",
    "document_requirements",
    "documents",
    "revoked_tokens",
    "audit_logs",
    "resumes",
]


def mask_secret(value: str) -> str:
    """Masks sensitive strings so credentials are never logged."""
    if not value:
        return "[NOT SET]"
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:3]}...{value[-3:]}"


def calculate_sha256(filepath: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_db_client():
    """
    Initializes a Supabase client using environment variables or Backend/config.py.
    Fails safely if credentials are not configured.
    """
    try:
        from supabase import create_client
    except ImportError:
        print("[ERROR] Required package 'supabase' is not installed. Install via: pip install supabase")
        sys.exit(1)

    # Prefer environment variables, fallback to config module
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        try:
            import config
            url = url or getattr(config, "SUPABASE_URL", "")
            key = key or getattr(config, "SUPABASE_KEY", "")
        except Exception:
            pass

    if not url or not key:
        print("[ERROR] Supabase credentials missing. Ensure SUPABASE_URL and SUPABASE_KEY are set.")
        sys.exit(1)

    return create_client(url, key)


def export_table(client, table_name: str, batch_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Paginates through a table and exports all records.
    Returns list of record dictionaries.
    """
    records: List[Dict[str, Any]] = []
    offset = 0

    while True:
        try:
            response = (
                client.table(table_name)
                .select("*")
                .range(offset, offset + batch_size - 1)
                .execute()
            )
            data = response.data or []
            records.extend(data)
            if len(data) < batch_size:
                break
            offset += batch_size
        except Exception as err:
            # Check if table does not exist or empty
            err_msg = str(err).lower()
            if "relation" in err_msg and "does not exist" in err_msg:
                print(f"  [WARN] Table '{table_name}' does not exist on target database (skipped).")
                return []
            raise RuntimeError(f"Failed exporting table '{table_name}': {err}")

    return records


def verify_backup_directory(target_dir: Path) -> Tuple[bool, List[str]]:
    """
    Verifies that a generated backup directory is valid and intact.
    Checks file existence, JSON validity, and SHA-256 checksums against metadata.json.
    """
    errors: List[str] = []
    metadata_file = target_dir / "metadata.json"

    if not metadata_file.exists():
        return False, ["metadata.json is missing from backup directory."]

    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as err:
        return False, [f"Failed to parse metadata.json: {err}"]

    table_entries = metadata.get("tables", {})
    if not table_entries:
        return False, ["metadata.json contains no table records."]

    for table_name, info in table_entries.items():
        filename = info.get("file")
        if not filename:
            errors.append(f"Table '{table_name}' metadata missing file reference.")
            continue

        file_path = target_dir / filename
        if not file_path.exists():
            errors.append(f"Backup file '{filename}' for table '{table_name}' does not exist.")
            continue

        if file_path.stat().st_size == 0:
            errors.append(f"Backup file '{filename}' is empty (0 bytes).")
            continue

        # Verify JSON parsing
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                errors.append(f"File '{filename}' does not contain a JSON list.")
            elif len(data) != info.get("record_count", -1):
                errors.append(
                    f"Record count mismatch in '{filename}': metadata={info.get('record_count')}, file={len(data)}"
                )
        except Exception as parse_err:
            errors.append(f"File '{filename}' contains invalid JSON: {parse_err}")

        # Verify SHA-256 checksum
        computed_sha = calculate_sha256(file_path)
        expected_sha = info.get("sha256")
        if expected_sha and computed_sha != expected_sha:
            errors.append(f"Checksum mismatch for '{filename}': expected {expected_sha}, got {computed_sha}")

    return len(errors) == 0, errors


def run_backup(
    output_dir: Path,
    tables: List[str],
    dry_run: bool = False,
    verify: bool = True,
    client: Optional[Any] = None,
) -> int:
    """
    Main backup execution logic.
    Returns 0 on success, 1 on failure.
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")

    print("================================================================")
    print("VTAB SQUARE AI RECRUITMENT SYSTEM - DATABASE BACKUP")
    print("================================================================")
    print(f"Timestamp (UTC): {start_time.isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXPORT'}")
    print(f"Tables ({len(tables)}): {', '.join(tables)}")

    # Initialize client if not injected (for testing)
    if client is None:
        client = get_db_client()

    url = os.getenv("SUPABASE_URL", "")
    print(f"Target Database: {url if url else '[CONFIGURED CLIENT]'}")

    if dry_run:
        print("\n[DRY RUN] Validating table connectivity...")
        all_ok = True
        for table in tables:
            try:
                res = client.table(table).select("*").limit(1).execute()
                count = len(res.data or [])
                print(f"  [OK] Table '{table}' accessible (sample count: {count}).")
            except Exception as err:
                print(f"  [FAIL] Table '{table}' check error: {err}")
                all_ok = False
        print("\n[DRY RUN] Dry run complete. " + ("All tables verified." if all_ok else "Some tables had warnings."))
        return 0 if all_ok else 1

    # Create destination directory
    backup_folder_name = f"backup_{timestamp_str}"
    target_dir = output_dir / backup_folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Destination: {target_dir.resolve()}")

    metadata: Dict[str, Any] = {
        "backup_name": backup_folder_name,
        "created_at": start_time.isoformat(),
        "system": "VTAB Square AI Recruitment System",
        "tables": {},
        "storage_manifest": {
            "bucket": "candidate-documents",
            "referenced_files_count": 0,
            "file": "storage_manifest.json"
        },
        "total_records": 0,
    }

    storage_paths: List[str] = []
    total_records = 0

    print("\n--- Exporting Tables ---")
    for table in tables:
        print(f"  Exporting '{table}'...", end="", flush=True)
        try:
            records = export_table(client, table)
            file_name = f"{table}.json"
            file_path = target_dir / file_name

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)

            file_size = file_path.stat().st_size
            sha256 = calculate_sha256(file_path)
            count = len(records)
            total_records += count

            metadata["tables"][table] = {
                "file": file_name,
                "record_count": count,
                "size_bytes": file_size,
                "sha256": sha256,
            }

            # Collect storage references from documents table
            if table == "documents":
                for doc in records:
                    sp = doc.get("storage_path")
                    if sp and sp not in storage_paths:
                        storage_paths.append(sp)

            print(f" Done ({count} records, {file_size} bytes)")
        except Exception as err:
            print(f" FAILED: {err}")
            return 1

    # Write storage manifest
    manifest_path = target_dir / "storage_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "bucket": "candidate-documents",
            "extracted_at": start_time.isoformat(),
            "count": len(storage_paths),
            "storage_paths": storage_paths
        }, f, indent=2)

    metadata["storage_manifest"]["referenced_files_count"] = len(storage_paths)
    metadata["total_records"] = total_records

    # Write metadata.json
    metadata_path = target_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n--- Backup Summary ---")
    print(f"Total Tables Exported: {len(metadata['tables'])}")
    print(f"Total Records Exported: {total_records}")
    print(f"Storage Documents Referenced: {len(storage_paths)}")
    print(f"Metadata Manifest: {metadata_path.name}")

    if verify:
        print("\n--- Verification ---")
        is_valid, errors = verify_backup_directory(target_dir)
        if is_valid:
            print("  [PASS] Backup verification passed: All files present, non-empty, and checksums match.")
        else:
            print("  [FAIL] Backup verification failed:")
            for err in errors:
                print(f"    - {err}")
            return 1

    end_time = datetime.datetime.now(datetime.timezone.utc)
    elapsed = (end_time - start_time).total_seconds()
    print(f"\n[SUCCESS] Backup completed successfully in {elapsed:.2f}s.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="VTAB Square AI Recruitment System - Standalone Database Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/backup_db.py
  python scripts/backup_db.py --output-dir /var/backups/recruitment --verify
  python scripts/backup_db.py --dry-run
  python scripts/backup_db.py --tables candidates,applications,documents
        """
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "backups" / "db",
        help="Directory where the timestamped backup folder will be created (default: ./backups/db)"
    )
    parser.add_argument(
        "--tables",
        type=str,
        default="",
        help="Comma-separated list of tables to export (default: all 14 application tables)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify JSON integrity and SHA-256 checksums after writing (default: True)"
    )
    parser.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Skip post-backup verification"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test connectivity and table access without writing any files"
    )

    args = parser.parse_args()

    if args.tables:
        table_list = [t.strip() for t in args.tables.split(",") if t.strip()]
    else:
        table_list = DEFAULT_TABLES

    exit_code = run_backup(
        output_dir=args.output_dir,
        tables=table_list,
        dry_run=args.dry_run,
        verify=args.verify,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
