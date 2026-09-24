"""
audit_service.py
================
Centralized, non-blocking audit logging service for VTAB Square Recruitment System.

Key Principles:
1. NON-BLOCKING & FAIL-SAFE: Under no circumstances will audit logging raise an exception,
   block execution, or cause a business transaction to fail or roll back.
2. SECRETS HYGIENE: Strictly sanitizes and redacts passwords, tokens, API keys, and credentials
   before persisting to the audit log.
3. SCHEMA INTEGRITY: Conforms exactly to the existing Supabase `audit_logs` table schema:
   - action (str)
   - staff_user_id (str / None)
   - table_name (str / None)
   - record_id (str / None)
   - new_data (dict / None)
"""

import logging
import re
from typing import Any, Dict, Optional
from supabase_db import supabase

logger = logging.getLogger("audit_service")

# Substrings that identify sensitive fields requiring redaction
SENSITIVE_KEY_PATTERNS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "credential",
    "cookie",
    "access_token",
    "refresh_token",
    "private_key",
    "service_role",
)

# Pattern to detect JWT or Bearer headers in string values
JWT_OR_BEARER_PATTERN = re.compile(
    r"(Bearer\s+[A-Za-z0-9\-._~+/]+=*)|(eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,})",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key matches any sensitive pattern."""
    key_lower = str(key).lower().replace("-", "_").strip()
    return any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS)


def sanitize_audit_data(data: Any, max_depth: int = 5) -> Any:
    """
    Recursively redacts sensitive values such as passwords, tokens, and API keys.
    Preserves all non-sensitive business data for operational traceability.
    """
    if max_depth <= 0:
        return "[TRUNCATED_DEPTH]"

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if is_sensitive_key(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_data(v, max_depth=max_depth - 1)
        return sanitized

    elif isinstance(data, (list, tuple, set)):
        return [sanitize_audit_data(item, max_depth=max_depth - 1) for item in data]

    elif isinstance(data, str):
        # Redact raw tokens or Bearer headers embedded in strings
        if JWT_OR_BEARER_PATTERN.search(data):
            return JWT_OR_BEARER_PATTERN.sub("[REDACTED_TOKEN]", data)
        return data

    return data


def log_audit_event(
    action: str,
    staff_user_id: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[str] = None,
    new_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Safely records an audit event to the `audit_logs` table.

    GUARANTEE:
    - Never raises an exception under any circumstance.
    - Never blocks, halts, or rolls back caller business operations.
    - Never exposes sensitive secrets or credentials.
    - If database or network error occurs, logs a warning and gracefully returns False.

    Returns:
        True if the audit event was successfully persisted, False otherwise.
    """
    try:
        if not action or not str(action).strip():
            logger.warning("[AUDIT WARNING] Attempted to log an audit event with an empty action.")
            return False

        safe_new_data = sanitize_audit_data(new_data) if new_data is not None else None

        payload = {
            "action": str(action).strip(),
            "staff_user_id": str(staff_user_id).strip() if staff_user_id else None,
            "table_name": str(table_name).strip() if table_name else None,
            "record_id": str(record_id).strip() if record_id else None,
            "new_data": safe_new_data,
        }

        # Insert into existing audit_logs table
        supabase.table("audit_logs").insert(payload).execute()
        return True

    except Exception as audit_err:
        # Isolated failure logging: console output only, no secondary audit call (prevents recursion)
        print(f"[AUDIT WARNING] Failed to record audit event '{action}': {audit_err}")
        logger.warning("Failed to record audit event '%s': %s", action, audit_err)
        return False
