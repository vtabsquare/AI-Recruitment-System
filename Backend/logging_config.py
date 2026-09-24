"""
logging_config.py
=================
Centralized, fail-safe structured logging and error monitoring for the AI Recruitment System.

Key Principles:
1. FAIL-SAFE / FAIL-OPEN: Under no circumstance will logging or monitoring failures crash,
   block, or degrade application requests or business workflows.
2. SECRETS HYGIENE: Strictly sanitizes and redacts passwords, tokens, API keys, and authorization
   headers from all structured logs.
3. MINIMAL OVERHEAD: Zero heavy database queries or blocking external network calls during request logging.
4. OPTIONAL SENTRY: Fully optional error monitoring via SENTRY_DSN; runs seamlessly with or without Sentry.
"""

import os
import re
import sys
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Re-use sensitive patterns aligned with audit_service & error sanitization
SENSITIVE_PARAM_NAMES = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "cookie",
    "access_token",
    "refresh_token",
    "key",
}

# Regex to catch tokens or bearer headers in arbitrary string values
TOKEN_REGEX = re.compile(
    r"(Bearer\s+[A-Za-z0-9\-._~+/]+=*)|(eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,})",
    re.IGNORECASE,
)

# Standard Python logger
logger = logging.getLogger("recruitment_monitoring")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

_SENTRY_INITIALIZED = False


def sanitize_query_string(url_path: str) -> str:
    """
    Sanitizes URL query strings by masking sensitive parameters like tokens or keys.
    Preserves endpoint routing paths intact.
    """
    try:
        parsed = urlparse(url_path)
        if not parsed.query:
            return url_path

        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_params = []
        for key, val in query_params:
            key_lower = key.lower().replace("-", "_").strip()
            if any(sensitive in key_lower for sensitive in SENSITIVE_PARAM_NAMES):
                sanitized_params.append((key, "[REDACTED]"))
            elif TOKEN_REGEX.search(val):
                sanitized_params.append((key, "[REDACTED_TOKEN]"))
            else:
                sanitized_params.append((key, val))

        sanitized_query = urlencode(sanitized_params, safe="[]")
        return urlunparse(parsed._replace(query=sanitized_query))
    except Exception:
        return url_path.split("?")[0] if "?" in url_path else url_path


def format_structured_log(
    level: str,
    event: str,
    fields: Dict[str, Any],
) -> str:
    """
    Formats key-value structured log line:
    timestamp=... level=... event=... field1=value1 field2=value2
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        f"timestamp={now_iso}",
        f"level={level.upper()}",
        f"event={event}",
    ]

    for k, v in fields.items():
        if v is None:
            continue
        v_str = str(v).replace("\n", " ").replace("\r", "")
        # Redact raw tokens or credentials if accidentally present in string field
        if TOKEN_REGEX.search(v_str):
            v_str = TOKEN_REGEX.sub("[REDACTED_TOKEN]", v_str)
        # Quote values containing spaces
        if " " in v_str or "=" in v_str:
            parts.append(f'{k}="{v_str}"')
        else:
            parts.append(f"{k}={v_str}")

    return " ".join(parts)


def log_structured(level: str, event: str, **fields: Any) -> None:
    """
    Safely writes a structured log line to stdout.
    GUARANTEE: Never raises an exception under any circumstance (fail-safe).
    """
    try:
        msg = format_structured_log(level=level, event=event, fields=fields)
        lvl_upper = level.upper()
        if lvl_upper == "ERROR":
            logger.error(msg)
        elif lvl_upper == "WARNING" or lvl_upper == "WARN":
            logger.warning(msg)
        elif lvl_upper == "DEBUG":
            logger.debug(msg)
        else:
            logger.info(msg)
    except Exception as log_err:
        try:
            print(f"[LOGGING_FALLBACK] event={event} level={level} error={log_err}")
        except Exception:
            pass


def log_request_summary(
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
    client_ip: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Emits a structured log summary upon HTTP request completion.
    """
    sanitized_route = sanitize_query_string(route)
    level = "INFO"
    if status_code >= 500:
        level = "ERROR"
    elif status_code >= 400:
        level = "WARNING"

    fields: Dict[str, Any] = {
        "method": method,
        "route": sanitized_route,
        "status": status_code,
        "duration_ms": duration_ms,
    }
    if correlation_id:
        fields["correlation_id"] = correlation_id
    if client_ip and client_ip not in ("127.0.0.1", "::1", "localhost"):
        fields["client_ip"] = client_ip

    log_structured(level=level, event="request_completed", **fields)


def log_external_service_failure(
    service: str,
    error: Exception,
    status_code: Optional[int] = None,
    endpoint: Optional[str] = None,
) -> None:
    """
    Records a safe structured event when an external dependency (Supabase, Brevo, Gemini, Google) fails.
    Strips raw secrets and stack traces from the log line.
    """
    try:
        err_msg = str(error)
        if TOKEN_REGEX.search(err_msg):
            err_msg = TOKEN_REGEX.sub("[REDACTED_TOKEN]", err_msg)

        # Truncate overly long error messages
        if len(err_msg) > 200:
            err_msg = err_msg[:197] + "..."

        fields: Dict[str, Any] = {
            "service": service,
            "error_type": type(error).__name__,
            "message": err_msg,
        }
        if status_code is not None:
            fields["status"] = status_code
        if endpoint:
            fields["endpoint"] = endpoint

        log_structured(level="ERROR", event="external_service_failure", **fields)
    except Exception:
        pass


def init_monitoring() -> bool:
    """
    Optionally initializes Sentry error monitoring if SENTRY_DSN is configured.
    GUARANTEE:
    - Never raises an exception.
    - If Sentry is not configured or sentry-sdk is not installed, gracefully returns False.
    - Application starts normally in all scenarios.
    """
    global _SENTRY_INITIALIZED
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        def safe_before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Strip authorization tokens, cookies, and secret keys before sending to Sentry."""
            try:
                # Strip request headers
                req = event.get("request", {})
                headers = req.get("headers", {})
                if headers:
                    for sensitive_header in ("authorization", "cookie", "x-api-key", "proxy-authorization"):
                        if sensitive_header in headers:
                            headers[sensitive_header] = "[REDACTED]"

                # Strip query strings with sensitive parameters
                query_string = req.get("query_string")
                if query_string:
                    req["query_string"] = sanitize_query_string(f"?{query_string}").lstrip("?")

                # Scrub candidate resumes or documents in extra data
                extra = event.get("extra", {})
                for k in list(extra.keys()):
                    if any(s in k.lower() for s in SENSITIVE_PARAM_NAMES):
                        extra[k] = "[REDACTED]"
            except Exception:
                pass
            return event

        environment = os.getenv("ENVIRONMENT", "production" if os.getenv("RENDER") else "development")
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            before_send=safe_before_send,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
        )
        _SENTRY_INITIALIZED = True
        log_structured("INFO", "monitoring_initialized", service="sentry", environment=environment)
        return True

    except ImportError:
        log_structured(
            "INFO",
            "monitoring_notice",
            detail="SENTRY_DSN provided but sentry-sdk is not installed; running with stdout logging only.",
        )
        return False
    except Exception as exc:
        log_structured(
            "WARNING",
            "monitoring_init_failed",
            error=str(exc),
            detail="Monitoring initialization failed safely; continuing without Sentry.",
        )
        return False


def capture_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Safely captures an unexpected exception to Sentry if initialized.
    GUARANTEE: Never raises an exception (fail-safe).
    """
    if not _SENTRY_INITIALIZED:
        return

    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            if context:
                for k, v in context.items():
                    if not any(s in k.lower() for s in SENSITIVE_PARAM_NAMES):
                        scope.set_extra(k, str(v)[:250])
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass
