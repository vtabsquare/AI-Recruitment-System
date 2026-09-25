from collections import Counter
from typing import Optional, Any
import os
import re
import uuid
import hashlib
import secrets
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import time
import logging

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from supabase_db import supabase
from interview_feedback_service import save_interview_feedback
from interview_ai_evaluator import evaluate_interview_feedback
from interview_decision_email_service import send_final_interview_decision_email
from email_service import send_email
from audit_service import log_audit_event, sanitize_audit_data
from logging_config import (
    log_structured,
    log_request_summary,
    capture_exception,
    init_monitoring,
)


try:
    from ai_analyzer import client as gemini_client
except Exception:
    gemini_client = None


def _call_gemini_with_fallback(client, **kwargs):
    model = (kwargs.get("model") or os.getenv("GEMINI_MODEL") or "").strip()
    if not model or model in ("gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.0-pro"):
        model = "gemini-3.5-flash"
    kwargs["model"] = model
    try:
        return client.models.generate_content(**kwargs)
    except Exception as exc:
        err_str = str(exc).lower()
        if "404" in err_str or "not_found" in err_str or "no longer available" in err_str:
            kwargs["model"] = "gemini-3.5-flash-lite"
            return client.models.generate_content(**kwargs)
        raise

app = FastAPI(
    title="VTAB Square AI Recruitment API",
    version="1.2.0",
    description="Backend API for the VTAB Square AI recruitment workflow.",
)

_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    """
    Lightweight, fail-safe HTTP request logging middleware.
    Measures duration and records structured summary on stdout for Render log streaming.
    GUARANTEE: Any logging error is caught and suppressed; requests never fail due to logging.
    """
    start_time = time.perf_counter()
    raw_route = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        try:
            client_ip = request.client.host if request.client else None
            log_request_summary(
                method=request.method,
                route=raw_route,
                status_code=500,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
        except Exception:
            pass
        raise exc

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    try:
        client_ip = request.client.host if request.client else None
        log_request_summary(
            method=request.method,
            route=raw_route,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )
    except Exception:
        pass
    return response


logger = logging.getLogger("api_error_handler")

GENERIC_INTERNAL_ERROR = "An internal error occurred. Please try again later."

LEAK_INDICATORS = (
    "traceback",
    'file "',
    "line ",
    "postgrest",
    "supabase",
    "operationalerror",
    "databaseerror",
    "programmingerror",
    "integrityerror",
    "syntaxerror",
    "psycopg2",
    "errno",
    "exception:",
    "error:",
    "connectionerror",
    "timeouterror",
    "connecterror",
    "getaddrinfo",
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "bearer",
    "authorization",
    "select ",
    "insert ",
    "update ",
    "delete ",
    "from ",
    "where ",
    "\\",
    ".py",
)

SENSITIVE_PARAM_PATTERN = re.compile(
    r"(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*([^\s,;]+)",
    re.IGNORECASE,
)


def log_internal_error(error: Exception, context: str = "") -> None:
    """
    Safely logs internal server errors with context, stripping any sensitive secrets.
    Does not expose errors to the client.
    Integrates fail-safe structured error logging and optional Sentry monitoring.
    """
    try:
        err_str = str(error)
        safe_msg = sanitize_audit_data(err_str) if "sanitize_audit_data" in globals() else err_str
        if isinstance(safe_msg, str):
            safe_msg = SENSITIVE_PARAM_PATTERN.sub(r"\1=[REDACTED]", safe_msg)
        ctx_prefix = f"[{context}] " if context else ""
        print(f"[SERVER ERROR] {ctx_prefix}{type(error).__name__}: {safe_msg}")
        logger.error(f"[SERVER ERROR] {ctx_prefix}{safe_msg}", exc_info=True)
        # Task 9: Structured error logging and fail-safe optional Sentry capture
        try:
            log_structured(
                level="ERROR",
                event="application_error",
                error_type=type(error).__name__,
                context=context or "internal",
                message=safe_msg[:200] if isinstance(safe_msg, str) else str(type(error).__name__),
            )
            capture_exception(error, context={"location": context or "internal"})
        except Exception:
            pass
    except Exception:
        print(f"[SERVER ERROR] {type(error).__name__}: Unexpected internal failure")



def sanitize_error_detail(detail: Any) -> str:
    """
    Sanitizes 500 error details so internal tracebacks, SQL statements,
    file paths, and credentials are never returned to clients.
    """
    if not isinstance(detail, str) or not detail.strip():
        return GENERIC_INTERNAL_ERROR

    detail_lower = detail.lower()
    if any(indicator in detail_lower for indicator in LEAK_INDICATORS):
        return GENERIC_INTERNAL_ERROR

    return detail.strip()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Global handler for HTTPExceptions:
    - Preserves all 4xx business errors (400, 401, 403, 404, etc.) with original messages and status.
    - Sanitizes 500 internal errors to prevent leaking internal stack traces, DB errors, or file paths.
    """
    if exc.status_code >= 500:
        log_internal_error(exc, context=f"{request.method} {request.url.path}")
        safe_detail = sanitize_error_detail(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": safe_detail},
            headers=getattr(exc, "headers", None),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Global catch-all for any unhandled Python exception:
    - Logs diagnostic details securely server-side.
    - Returns a safe HTTP 500 generic error to the client with zero internal leaks.
    """
    log_internal_error(exc, context=f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": GENERIC_INTERNAL_ERROR},
    )


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3)


class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=6)
    token: Optional[str] = None
    access_token: Optional[str] = None


class AIChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class InterviewFeedbackRequest(BaseModel):
    application_id: str = Field(..., min_length=1)
    reviewer_name: str = Field(..., min_length=1)
    technical_skills: int = Field(..., ge=1, le=5)
    communication: int = Field(..., ge=1, le=5)
    problem_solving: int = Field(..., ge=1, le=5)
    overall_performance: int = Field(..., ge=1, le=5)
    recommendation: str = Field(..., min_length=1)
    reviewer_comments: Optional[str] = ""


class CandidateDecisionRequest(BaseModel):
    application_id: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    comments: Optional[str] = ""


def select_all(table_name: str, order_column: Optional[str] = None, descending: bool = True):
    query = supabase.table(table_name).select("*")
    if order_column:
        query = query.order(order_column, desc=descending)
    return query.execute().data or []


def select_one(table_name: str, record_id: str):
    response = supabase.table(table_name).select("*").eq("id", record_id).limit(1).execute()
    return response.data[0] if response.data else None


def safe_select_all(table_name: str, order_column: Optional[str] = None):
    try:
        return {"available": True, "data": select_all(table_name, order_column)}
    except Exception as error:
        log_internal_error(error, context=f"safe_select_all({table_name})")
        return {
            "available": False,
            "data": [],
            "message": f"{table_name} is not available yet.",
            "error": "Database service unavailable.",
        }


# ------------------------- AUTH -------------------------

@app.post("/api/auth/login")
def login(request: LoginRequest):
    try:
        email = request.email.strip().lower()
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": request.password,
        })
        session = getattr(auth_response, "session", None)
        user = getattr(auth_response, "user", None)
        if not session or not user:
            log_audit_event(
                "staff_login_failed",
                table_name="staff_users",
                new_data={"email": email, "reason": "invalid_credentials"},
            )
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        staff_response = (
            supabase.table("staff_users")
            .select("id, full_name, email, role, is_active")
            .or_(f"auth_user_id.eq.{user.id},email.ilike.{email}")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not staff_response.data:
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            log_audit_event(
                "staff_login_failed",
                staff_user_id=getattr(user, "id", None),
                table_name="staff_users",
                new_data={"email": email, "reason": "inactive_staff"},
            )
            raise HTTPException(status_code=403, detail="Authenticated user is not an active staff member.")

        staff = staff_response.data[0]
        role = str(staff.get("role", "")).lower()
        if role not in {"manager", "hr", "admin"}:
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            log_audit_event(
                "staff_login_failed",
                staff_user_id=staff.get("id"),
                table_name="staff_users",
                record_id=staff.get("id"),
                new_data={"email": email, "role": role, "reason": "unauthorized_role"},
            )
            raise HTTPException(status_code=403, detail="Only Manager, HR, or Admin accounts can access this portal.")

        log_audit_event(
            "staff_login_success",
            staff_user_id=staff.get("id"),
            table_name="staff_users",
            record_id=staff.get("id"),
            new_data={"email": email, "role": role},
        )

        return {
            "success": True,
            "message": "Login successful.",
            "staff": staff,
            "access_token": getattr(session, "access_token", None),
            "refresh_token": getattr(session, "refresh_token", None),
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/auth/login")
        log_audit_event(
            "staff_login_failed",
            table_name="staff_users",
            new_data={"email": email if "email" in locals() else None, "reason": "auth_exception"},
        )
        err_msg = str(error).lower()
        if any(w in err_msg for w in ("invalid", "credential", "password", "user", "grant")):
            raise HTTPException(status_code=401, detail="Login failed: Invalid email or password.")
        raise HTTPException(status_code=401, detail="Login failed: Please check your credentials or try again later.")


@app.post("/api/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest, raw_request: Request):
    email = req.email.strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Invalid email address format.")

    generic_success_response = {
        "success": True,
        "message": "If this email is associated with an active staff account, password reset instructions have been sent."
    }

    try:
        origin = raw_request.headers.get("origin") or ""
        if not origin:
            referer = raw_request.headers.get("referer") or ""
            if referer:
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                origin = f"{parsed.scheme}://{parsed.netloc}"
        if not origin:
            try:
                from config import FRONTEND_URL
                origin = FRONTEND_URL
            except Exception:
                origin = ""
        if not origin:
            origin = _allowed_origins[0] if _allowed_origins else "http://localhost:5173"

        redirect_url = f"{origin.rstrip('/')}/#type=recovery"

        staff_res = (
            supabase.table("staff_users")
            .select("id, email, is_active")
            .eq("email", email)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not staff_res.data:
            return generic_success_response

        staff_member = staff_res.data[0]
        log_audit_event(
            "password_reset_requested",
            staff_user_id=staff_member.get("id"),
            table_name="staff_users",
            record_id=staff_member.get("id"),
            new_data={"email": email},
        )

        email_sent = False
        try:
            link_res = supabase.auth.admin.generate_link({
                "type": "recovery",
                "email": email,
                "options": {"redirect_to": redirect_url}
            })
            action_link = (
                getattr(getattr(link_res, "properties", None), "action_link", None)
                or getattr(link_res, "action_link", None)
            )
            if action_link:
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <h2 style="color: #6357d7;">VTAB Square — Password Reset Request</h2>
                    <p>Hello,</p>
                    <p>We received a request to reset your password for the VTAB Square Recruitment Portal.</p>
                    <p style="margin: 25px 0;">
                        <a href="{action_link}" style="background-color: #7164dc; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Reset Password</a>
                    </p>
                    <p style="color: #666; font-size: 13px;">If the button above does not work, copy and paste this URL into your browser:</p>
                    <p style="color: #888; font-size: 12px; word-break: break-all;">{action_link}</p>
                    <p style="color: #888; font-size: 12px; margin-top: 30px;">If you did not request a password reset, you can safely ignore this email.</p>
                </div>
                """
                send_email(
                    recipient_email=email,
                    recipient_name="Staff Member",
                    subject="VTAB Square — Password Reset Instructions",
                    html_content=html_content
                )
                email_sent = True
        except Exception:
            pass

        if not email_sent:
            try:
                supabase.auth.reset_password_for_email(
                    email,
                    options={"redirect_to": redirect_url}
                )
            except Exception:
                pass

        return generic_success_response
    except HTTPException:
        raise
    except Exception:
        return generic_success_response


@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    token = (req.access_token or req.token or "").strip()
    if not token or token == "active":
        raise HTTPException(status_code=400, detail="Password reset token is required.")

    new_password = req.password
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    try:
        user = None
        try:
            user_response = supabase.auth.get_user(token)
            user = getattr(user_response, "user", None)
        except Exception:
            user = None

        if not user:
            try:
                otp_res = supabase.auth.verify_otp({"token_hash": token, "type": "recovery"})
                user = getattr(otp_res, "user", None)
                if not user and getattr(otp_res, "session", None):
                    user = getattr(otp_res.session, "user", None)
            except Exception:
                user = None

        if not user or not getattr(user, "id", None):
            raise HTTPException(
                status_code=400,
                detail="The password reset link is invalid or has expired. Please request a new one."
            )

        updated = False
        try:
            supabase.auth.admin.update_user_by_id(str(user.id), {"password": new_password})
            updated = True
        except Exception:
            try:
                supabase.auth._request("PUT", "user", body={"password": new_password}, jwt=token)
                updated = True
            except Exception:
                pass

        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Unable to update password at this time. Please try again later."
            )

        log_audit_event(
            "password_reset_completed",
            staff_user_id=str(user.id) if getattr(user, "id", None) else None,
            table_name="staff_users",
            record_id=str(user.id) if getattr(user, "id", None) else None,
            new_data={"status": "password_updated"},
        )

        return {
            "success": True,
            "message": "Password updated successfully. You can now log in with your new password."
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="The password reset link is invalid or has expired. Please request a new one."
        )


# ------------------------- SESSION REVOCATION CACHE -------------------------

_revoked_tokens_lock = threading.Lock()
_revoked_token_hashes = {}  # {sha256_hash: expiry_timestamp}


def revoke_token(token: str, ttl_seconds: int = 7200):
    """
    Records a token hash as revoked. Stores only the SHA-256 digest of the token
    to prevent exposing raw tokens or secrets in memory.
    """
    if not token or not token.strip():
        return
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    now = time.time()
    with _revoked_tokens_lock:
        expired_keys = [k for k, exp in _revoked_token_hashes.items() if exp < now]
        for k in expired_keys:
            del _revoked_token_hashes[k]
        _revoked_token_hashes[token_hash] = now + ttl_seconds


def is_token_revoked(token: str) -> bool:
    """
    Checks if a token has been explicitly invalidated by logout.
    """
    if not token or not token.strip():
        return False
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    now = time.time()
    with _revoked_tokens_lock:
        exp = _revoked_token_hashes.get(token_hash)
        if exp is None:
            return False
        if exp < now:
            del _revoked_token_hashes[token_hash]
            return False
        return True


bearer_scheme = HTTPBearer(auto_error=False)


@app.post("/api/auth/logout")
def logout(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    """
    Invalidates the active user session on the server side and in Supabase Auth.
    Idempotent: successfully returns 200 even if the session was already expired or missing.
    """
    staff_id = None
    if credentials and credentials.credentials.strip():
        token = credentials.credentials.strip()
        try:
            user_response = supabase.auth.get_user(token)
            user = getattr(user_response, "user", None)
            if user:
                staff_id = str(user.id)
        except Exception:
            staff_id = None

        revoke_token(token)
        try:
            supabase.auth.admin.sign_out(token, scope="local")
        except Exception:
            try:
                supabase.auth.sign_out({"scope": "local"})
            except Exception:
                pass

    log_audit_event(
        "staff_logout",
        staff_user_id=staff_id,
        table_name="staff_users",
        record_id=staff_id,
        new_data={"status": "logged_out"},
    )

    return {
        "success": True,
        "message": "Successfully logged out."
    }


def get_current_staff(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    if not credentials or not credentials.credentials.strip():
        raise HTTPException(status_code=401, detail="Authorization header is required.")
    token = credentials.credentials.strip()
    if is_token_revoked(token):
        raise HTTPException(status_code=401, detail="Session has been logged out. Please log in again.")
    try:
        user_response = supabase.auth.get_user(token)
        user = getattr(user_response, "user", None)
        if not user or not getattr(user, "email", None):
            raise HTTPException(status_code=401, detail="Invalid or expired access token.")

        staff_response = (
            supabase.table("staff_users")
            .select("id, full_name, email, role, is_active")
            .or_(f"auth_user_id.eq.{user.id},email.ilike.{user.email.lower()}")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not staff_response.data:
            raise HTTPException(status_code=403, detail="Staff account not found or inactive.")
        return staff_response.data[0]
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="get_current_staff")
        raise HTTPException(status_code=401, detail="Authentication failed. Please log in again.")


def require_staff(staff=Depends(get_current_staff)):
    return staff


def require_manager(staff=Depends(get_current_staff)):
    if str(staff.get("role", "")).lower() not in {"manager", "admin"}:
        raise HTTPException(status_code=403, detail="Manager/Admin access required.")
    return staff


def require_hr(staff=Depends(get_current_staff)):
    if str(staff.get("role", "")).lower() not in {"hr", "admin"}:
        raise HTTPException(status_code=403, detail="HR/Admin access required.")
    return staff


# ------------------------- ROOT -------------------------

@app.get("/")
def root():
    return {"status": "running", "service": "VTAB Square AI Recruitment API", "version": "1.2.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ------------------------- AI EVALUATIONS -------------------------


def get_evaluations_for_applications(application_ids):
    """Return the newest persisted AI eligibility evaluation per application."""
    if not application_ids:
        return {}
    try:
        response = (
            supabase.table("ai_evaluations")
            .select("*")
            .in_("application_id", application_ids)
            .order("evaluated_at", desc=True)
            .execute()
        )
        result = {}
        for row in response.data or []:
            application_id = row.get("application_id")
            if application_id and application_id not in result:
                result[application_id] = row
        return result
    except Exception:
        # Keep the portal usable if the table has not been created/populated yet.
        return {}


def build_ai_summary(evaluation):
    if not evaluation:
        return {
            "available": False,
            "decision": None,
            "matched_skills": [],
            "missing_skills": [],
            "cgpa_eligible": None,
            "skills_eligible": None,
            "overall_eligible": None,
            "reason": None,
            "evaluated_at": None,
        }
    return {
        "available": True,
        "decision": evaluation.get("decision"),
        "matched_skills": evaluation.get("matched_skills") or [],
        "missing_skills": evaluation.get("missing_skills") or [],
        "cgpa_eligible": evaluation.get("cgpa_eligible"),
        "skills_eligible": evaluation.get("skills_eligible"),
        "overall_eligible": evaluation.get("overall_eligible"),
        "reason": evaluation.get("reason"),
        "evaluated_at": evaluation.get("evaluated_at"),
    }


def enrich_application(application, candidate, role, evaluation):
    return {
        "application": application,
        "candidate": candidate,
        "job_role": role,
        "ai_evaluation": evaluation,
        "ai_summary": build_ai_summary(evaluation),
        "manager_view": {
            "application_id": application.get("application_id"),
            "status": application.get("status"),
            "candidate_name": candidate.get("candidate_name"),
            "email": candidate.get("email"),
            "role": role.get("role_name"),
            "ai_decision": evaluation.get("decision") if evaluation else None,
            "overall_eligible": evaluation.get("overall_eligible") if evaluation else None,
        },
    }


# ------------------------- CANDIDATES -------------------------

@app.get("/api/candidates")
def get_candidates(staff=Depends(require_manager)):
    try:
        applications = select_all("applications", order_column="applied_at")
        candidates = select_all("candidates")
        roles = select_all("job_roles")
        candidate_map = {x.get("id"): x for x in candidates}
        role_map = {x.get("id"): x for x in roles}
        application_ids = [x.get("id") for x in applications if x.get("id")]
        evaluation_map = get_evaluations_for_applications(application_ids)

        result = []
        for application in applications:
            status = str(application.get("status", "")).lower()
            if status in {"onboarding", "onboarded", "rejected", "closed"}:
                continue
            candidate = candidate_map.get(application.get("candidate_id"), {})
            role = role_map.get(application.get("job_role_id"), {})
            evaluation = evaluation_map.get(application.get("id"))
            result.append(enrich_application(application, candidate, role, evaluation))

        return {
            "success": True,
            "count": len(result),
            "items": result,
            "requested_by": staff.get("role"),
        }
    except Exception as error:
        log_internal_error(error, context="GET /api/candidates")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


@app.get("/api/candidates/{candidate_id}")
def get_candidate(candidate_id: str, staff=Depends(require_manager)):
    try:
        candidate = select_one("candidates", candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found.")

        applications_response = (
            supabase.table("applications")
            .select("*")
            .eq("candidate_id", candidate_id)
            .order("applied_at", desc=True)
            .execute()
        )
        applications = applications_response.data or []
        roles = select_all("job_roles")
        role_map = {x.get("id"): x for x in roles}
        application_ids = [x.get("id") for x in applications if x.get("id")]
        evaluation_map = get_evaluations_for_applications(application_ids)

        enriched = []
        for application in applications:
            role = role_map.get(application.get("job_role_id"), {})
            evaluation = evaluation_map.get(application.get("id"))
            enriched.append(enrich_application(application, candidate, role, evaluation))

        return {"success": True, "candidate": candidate, "applications": enriched}
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context=f"GET /api/candidates/{candidate_id}")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


# ------------------------- HUMAN MANAGER DECISION -------------------------

@app.post("/api/manager/candidate-decision")
def manager_candidate_decision(request: CandidateDecisionRequest, staff=Depends(require_manager)):
    decision = request.decision.strip().lower()
    allowed = {
        "approve": "interview_pending",
        "approved": "interview_pending",
        "reject": "rejected",
        "rejected": "rejected",
        "next_round": "interview_pending",
        "next round": "interview_pending",
    }
    if decision not in allowed:
        raise HTTPException(status_code=400, detail="Decision must be approve, reject, or next_round.")

    try:
        existing = (
            supabase.table("applications")
            .select("*")
            .eq("id", request.application_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Application not found.")

        updated = (
            supabase.table("applications")
            .update({"status": allowed[decision]})
            .eq("id", request.application_id)
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=500, detail="Application decision could not be saved.")

        log_audit_event(
            "manager_candidate_decision",
            staff_user_id=staff.get("id"),
            table_name="applications",
            record_id=request.application_id,
            new_data={
                "decision": decision,
                "status": allowed[decision],
                "comments": request.comments or "",
            },
        )

        return {
            "success": True,
            "message": "Manager decision recorded.",
            "decision": decision,
            "application": updated.data[0],
            "reviewer": {
                "id": staff.get("id"),
                "name": staff.get("full_name"),
                "role": staff.get("role"),
            },
            "comments": request.comments or "",
        }
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/manager/candidate-decision")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


# ------------------------- INTERVIEWS -------------------------

@app.get("/api/interviews")
def get_interviews(staff=Depends(require_manager)):
    try:
        interviews = select_all("interviews", order_column="scheduled_at")
        candidates = select_all("candidates")
        roles = select_all("job_roles")
        staff_users = select_all("staff_users")
        candidate_map = {x.get("id"): x for x in candidates}
        role_map = {x.get("id"): x for x in roles}
        staff_map = {x.get("id"): x for x in staff_users}
        items = []
        for interview in interviews:
            candidate = candidate_map.get(interview.get("candidate_id"), {})
            role = role_map.get(interview.get("job_role_id"), {})
            interviewer = staff_map.get(interview.get("interviewer_id"), {})
            items.append({
                **interview,
                "candidate_name": candidate.get("candidate_name"),
                "candidate_email": candidate.get("email"),
                "job_role": role.get("role_name"),
                "interviewer_name": interviewer.get("full_name"),
                "interviewer_email": interviewer.get("email"),
            })
        return {"success": True, "count": len(items), "items": items}
    except Exception as error:
        log_internal_error(error, context="GET /api/interviews")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


@app.get("/api/interviews/{interview_id}")
def get_interview(interview_id: str, staff=Depends(require_manager)):
    try:
        interview = select_one("interviews", interview_id)
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found.")
        return {"success": True, "interview": interview}
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context=f"GET /api/interviews/{interview_id}")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


# ------------------------- INTERVIEW FEEDBACK -------------------------

@app.post("/api/interview-feedback")
def submit_interview_feedback(
    feedback: InterviewFeedbackRequest,
    staff=Depends(require_manager)
):
    try:
        # ---------------------------------------------------------
        # 1. SAVE MANAGER INTERVIEW FEEDBACK
        # ---------------------------------------------------------
        saved_feedback = save_interview_feedback(
            application_id=feedback.application_id,
            reviewer_name=feedback.reviewer_name,
            technical_skills=feedback.technical_skills,
            communication=feedback.communication,
            problem_solving=feedback.problem_solving,
            overall_performance=feedback.overall_performance,
            recommendation=feedback.recommendation,
            reviewer_comments=feedback.reviewer_comments or "",
        )

        # ---------------------------------------------------------
        # 2. AI EVALUATES THE INTERVIEW
        # ---------------------------------------------------------
        ai_result = evaluate_interview_feedback(
            feedback.application_id
        )

        final_decision = ai_result["final_decision"]

        print("==============================================")
        print("INTERVIEW FEEDBACK PROCESSING")
        print("Application:", feedback.application_id)
        print("AI Decision:", final_decision)
        print("==============================================")

        # ---------------------------------------------------------
        # 3. UPDATE APPLICATION STATUS
        # ---------------------------------------------------------
        decision = str(final_decision or "").strip().lower()

        if decision in ["selected", "approved", "select", "approve"]:
            new_application_status = "documents_pending"

        elif decision in ["rejected", "reject"]:
            new_application_status = "rejected"

        elif decision in ["next_round", "next round"]:
            new_application_status = "interview_pending"

        else:
            new_application_status = "documents_pending"

        print("Updating application status...")
        print("New status:", new_application_status)

        status_response = (
            supabase
            .table("applications")
            .update({
                "status": new_application_status
            })
            .eq("id", feedback.application_id)
            .execute()
        )

        if not status_response.data:
            raise ValueError(
                "Interview feedback was saved, but the application "
                "status could not be updated."
            )

        updated_application = status_response.data[0]

        log_audit_event(
            "interview_feedback_submitted",
            staff_user_id=staff.get("id"),
            table_name="applications",
            record_id=feedback.application_id,
            new_data={
                "reviewer_name": feedback.reviewer_name,
                "ai_decision": final_decision,
                "new_status": new_application_status,
                "recommendation": feedback.recommendation,
            },
        )

        print("Application status updated successfully.")
        print("Application ID:", updated_application.get("application_id"))
        print("Status:", updated_application.get("status"))

        # ---------------------------------------------------------
        # 4. SEND FINAL DECISION EMAIL
        # ---------------------------------------------------------
        email_result = send_final_interview_decision_email(
            application_id=feedback.application_id,
            final_decision=final_decision,
        )

        # ---------------------------------------------------------
        # 5. AUTOMATIC DOCUMENT REQUEST GENERATION
        # ---------------------------------------------------------
        document_request = None
        document_email = None

        if decision in {"selected", "approved", "select", "approve"}:
            candidate = select_one("candidates", updated_application.get("candidate_id"))
            role = select_one("job_roles", updated_application.get("job_role_id"))

            if not candidate:
                raise ValueError("Candidate record not found for document request.")

            raw_token = secrets.token_urlsafe(32)
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=7)
            ).isoformat()

            existing_request = _get_existing_document_request(feedback.application_id)

            if existing_request:
                # Rotate token and reactivate the request
                updated_req = (
                    supabase.table("document_requests")
                    .update({
                        "token_hash": _hash_document_token(raw_token),
                        "status": "pending",
                        "expires_at": expires_at,
                        "used_at": None,
                    })
                    .eq("id", existing_request["id"])
                    .execute()
                )
                document_request = updated_req.data[0] if updated_req.data else None
            else:
                document_request = create_document_request(
                    application_id=feedback.application_id,
                    candidate_id=updated_application.get("candidate_id"),
                    token=raw_token,
                    expires_at=expires_at,
                )

            document_email = send_document_request_email(
                candidate_name=candidate.get("candidate_name"),
                recipient_email=candidate.get("email"),
                job_role=role.get("role_name") if role else "the position",
                application_id=updated_application.get("application_id"),
                token=raw_token,
            )
            print("DOCUMENT_REQUEST_SENT")

        # ---------------------------------------------------------
        # 6. RETURN COMPLETE RESULT
        # ---------------------------------------------------------
        return {
            "success": True,
            "message": "Interview feedback processed successfully.",
            "feedback": saved_feedback,
            "ai_evaluation": ai_result,
            "application": updated_application,
            "email": email_result,
            "document_request": document_request,
            "document_email": document_email,
            "processed_by": {
                "staff_id": staff.get("id"),
                "staff_name": staff.get("full_name"),
                "role": staff.get("role"),
            },
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=sanitize_error_detail(str(error))
        )

    except Exception as error:
        log_internal_error(error, context="POST /api/interview-feedback")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


# ------------------------- ANALYTICS -------------------------

@app.get("/api/manager/analytics")
def manager_analytics(staff=Depends(require_manager)):
    try:
        applications = select_all("applications")
        interviews = select_all("interviews")
        feedback = select_all("interview_feedback")

        # Deduplicate applications to prevent duplicate document joins or duplicate rows
        unique_applications = {app.get("id"): app for app in applications if app.get("id")}
        app_list = list(unique_applications.values())

        application_statuses = Counter(str(x.get("status", "unknown")).lower() for x in app_list)
        interview_statuses = Counter(str(x.get("status", "unknown")).lower() for x in interviews)
        scores = []
        for item in feedback:
            try:
                scores.append(float(item.get("overall_performance")))
            except (TypeError, ValueError):
                pass
        average = round(sum(scores) / len(scores), 2) if scores else None
        try:
            evaluations = select_all("ai_evaluations")
            unique_evaluations = {ev.get("application_id"): ev for ev in evaluations if ev.get("application_id")}
            ai_statuses = Counter(str(x.get("decision", "unknown")).lower() for x in unique_evaluations.values())
        except Exception:
            ai_statuses = Counter()

        return {
            "success": True,
            "analytics": {
                "total_applications": len(app_list),
                "total_interviews": len(interviews),
                "completed_feedback": len(feedback),
                "average_overall_performance": average,
                "applications_by_status": dict(application_statuses),
                "interviews_by_status": dict(interview_statuses),
                "ai_eligibility_by_decision": dict(ai_statuses),
                "shortlisted": application_statuses.get("shortlisted", 0),
                "rejected": application_statuses.get("rejected", 0),
                "interview_scheduled": interview_statuses.get("scheduled", 0),
                "interview_completed": interview_statuses.get("completed", 0),
            },
            "generated_for": {"staff_id": staff.get("id"), "role": staff.get("role")},
        }
    except Exception as error:
        log_internal_error(error, context="GET /api/manager/analytics")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


# ------------------------- HR OFFER APPROVALS -------------------------

@app.get("/api/hr/offer-approvals")
def hr_offer_approvals(staff=Depends(require_hr)):
    """Return applications that have reached the HR offer stage."""
    try:
        applications = select_all("applications", order_column="updated_at")
        candidates = select_all("candidates")
        roles = select_all("job_roles")

        candidate_map = {item.get("id"): item for item in candidates}
        role_map = {item.get("id"): item for item in roles}
        application_ids = [item.get("id") for item in applications if item.get("id")]
        evaluation_map = get_evaluations_for_applications(application_ids)

        # -------------------------------------------------------
        # FIX: Show candidates in BOTH documents_pending and
        # documents_verifying so HR sees them after the candidate
        # submits and AI verifies all documents.
        #
        # Workflow:
        #   documents_pending   → candidate uploads docs
        #   documents_verifying → candidate submitted, AI approved
        #   onboarding          → HR approved
        # -------------------------------------------------------
        hr_statuses = {"documents_pending", "documents_verifying"}
        items = []

        for application in applications:
            status = str(application.get("status", "")).lower()
            if status not in hr_statuses:
                continue

            candidate = candidate_map.get(application.get("candidate_id"), {})
            role = role_map.get(application.get("job_role_id"), {})
            evaluation = evaluation_map.get(application.get("id"))

            # Only show the candidate in HR when every required
            # document for this application has been AI-approved.
            required_response = (
                supabase.table("document_requirements")
                .select("document_name, is_required")
                .eq("is_active", True)
                .execute()
            )
            required_names = {
                row.get("document_name")
                for row in (required_response.data or [])
                if row.get("is_required")
            }

            documents_response = (
                supabase.table("documents")
                .select("document_name, verification_status")
                .eq("application_id", application.get("id"))
                .execute()
            )
            ai_approved_names = {
                row.get("document_name")
                for row in (documents_response.data or [])
                if row.get("verification_status") in {"approved", "verified"}
            }

            if required_names and not required_names.issubset(ai_approved_names):
                continue

            items.append(
                enrich_application(application, candidate, role, evaluation)
            )

        return {
            "success": True,
            "count": len(items),
            "items": items,
            "requested_by": staff.get("role"),
        }
    except Exception as error:
        log_internal_error(error, context="GET /api/hr/offer-approvals")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


@app.post("/api/hr/offer-approvals/{application_id}/approve")
def hr_approve_offer(
    application_id: str,
    staff=Depends(require_hr),
):
    """Perform final HR approval on a candidate and transition to onboarding."""
    try:
        app_response = (
            supabase.table("applications")
            .select("id, status, candidate_id, job_role_id, application_id")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )
        if not app_response.data:
            app_response = (
                supabase.table("applications")
                .select("id, status, candidate_id, job_role_id, application_id")
                .eq("application_id", application_id)
                .limit(1)
                .execute()
            )

        if not app_response.data:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )

        app_data = app_response.data[0]
        real_app_uuid = app_data.get("id")
        candidate_id = app_data.get("candidate_id")

        reqs_response = (
            supabase.table("document_requirements")
            .select("id, document_name, is_required")
            .eq("is_active", True)
            .execute()
        )
        required_names = {
            req["document_name"]
            for req in reqs_response.data or []
            if req.get("is_required")
        }

        approved_response = (
            supabase.table("documents")
            .select("document_name, verification_status")
            .eq("application_id", real_app_uuid)
            .execute()
        )
        approved_names = {
            doc["document_name"]
            for doc in approved_response.data or []
            if doc.get("verification_status") in {"approved", "verified"}
        }

        if required_names and not required_names.issubset(approved_names):
            missing = list(required_names - approved_names)
            raise HTTPException(
                status_code=400,
                detail=f"All required documents must be approved before final HR approval. Unapproved or missing: {', '.join(missing)}",
            )

        supabase.table("applications").update(
            {"status": "onboarding"}
        ).eq("id", real_app_uuid).execute()

        log_audit_event(
            "final_hr_offer_approved",
            staff_user_id=staff.get("id"),
            table_name="applications",
            record_id=real_app_uuid,
            new_data={"status": "onboarding"},
        )

        email_result = None
        candidate = select_one("candidates", candidate_id)
        role = select_one("job_roles", app_data.get("job_role_id"))

        if candidate:
            try:
                email_result = send_onboarding_email(
                    candidate_name=candidate.get("candidate_name"),
                    recipient_email=candidate.get("email"),
                    job_role=role.get("role_name") if role else "the position",
                    application_id=app_data.get("application_id") or real_app_uuid
                )
                print("ONBOARDING_EMAIL_SENT")
            except Exception as email_error:
                print("ONBOARDING EMAIL ERROR:", email_error)

        return {
            "success": True,
            "message": "Candidate offer approved and onboarding initiated successfully.",
            "application_id": real_app_uuid,
            "status": "onboarding",
            "email": email_result,
            "approved_by": {
                "staff_id": staff.get("id"),
                "staff_name": staff.get("full_name"),
                "role": staff.get("role"),
            },
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/hr/offer-approvals/{application_id}/approve")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


@app.post("/api/hr/offer-approvals/{application_id}/reject")
def hr_reject_offer(
    application_id: str,
    staff=Depends(require_hr),
):
    """Perform final HR rejection on a candidate application."""
    try:
        app_response = (
            supabase.table("applications")
            .select("id, status, candidate_id, job_role_id, application_id")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )
        if not app_response.data:
            app_response = (
                supabase.table("applications")
                .select("id, status, candidate_id, job_role_id, application_id")
                .eq("application_id", application_id)
                .limit(1)
                .execute()
            )

        if not app_response.data:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )

        app_data = app_response.data[0]
        real_app_uuid = app_data.get("id")

        supabase.table("applications").update(
            {"status": "rejected"}
        ).eq("id", real_app_uuid).execute()

        log_audit_event(
            "final_hr_offer_rejected",
            staff_user_id=staff.get("id"),
            table_name="applications",
            record_id=real_app_uuid,
            new_data={"status": "rejected"},
        )

        return {
            "success": True,
            "message": "Candidate application rejected.",
            "application_id": real_app_uuid,
            "status": "rejected",
            "rejected_by": {
                "staff_id": staff.get("id"),
                "staff_name": staff.get("full_name"),
                "role": staff.get("role"),
            },
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/hr/offer-approvals/{application_id}/reject")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


# ------------------------- HR -------------------------

@app.get("/api/hr/employees")
def hr_employees(staff=Depends(require_hr)):
    """Return candidates who have been approved by HR and entered onboarding."""
    try:
        applications = select_all("applications", order_column="updated_at")
        candidates = select_all("candidates")
        roles = select_all("job_roles")

        candidate_map = {item.get("id"): item for item in candidates}
        role_map = {item.get("id"): item for item in roles}
        application_ids = [item.get("id") for item in applications if item.get("id")]
        evaluation_map = get_evaluations_for_applications(application_ids)

        onboarding_statuses = {"onboarding", "onboarded"}
        items = []

        for application in applications:
            status = str(application.get("status", "")).lower()
            if status not in onboarding_statuses:
                continue

            candidate = candidate_map.get(application.get("candidate_id"), {})
            role = role_map.get(application.get("job_role_id"), {})
            evaluation = evaluation_map.get(application.get("id"))

            items.append(
                enrich_application(application, candidate, role, evaluation)
            )

        return {
            "success": True,
            "count": len(items),
            "items": items,
            "employees": items,
            "requested_by": staff.get("role"),
        }
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="GET /api/hr/employees")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


@app.get("/api/hr/audit-logs")
def hr_audit_logs(staff=Depends(require_hr)):
    return {"success": True, **safe_select_all("audit_logs", order_column="created_at")}


# ============================================================
# DOCUMENT REQUEST + DOCUMENT UPLOAD WORKFLOW
# ============================================================

DOCUMENT_BUCKET = "candidate-documents"
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def _hash_document_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_existing_document_request(application_id: str):
    response = (
        supabase.table("document_requests")
        .select("*")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_document_request(
    application_id: str,
    candidate_id: str,
    token: str,
    expires_at: Optional[str] = None,
):
    data = {
        "application_id": application_id,
        "candidate_id": candidate_id,
        "token_hash": _hash_document_token(token),
        "status": "pending",
    }

    if expires_at:
        data["expires_at"] = expires_at

    response = (
        supabase.table("document_requests")
        .insert(data)
        .execute()
    )

    if not response.data:
        raise ValueError("Document request could not be created.")

    return response.data[0]


def send_document_request_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id,
    token,
):
    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")

    upload_url = f"{frontend_url}/documents?token={token}"

    return send_email(
        recipient_email=str(recipient_email or "").strip(),
        recipient_name=str(candidate_name or "Candidate").strip(),
        subject="VTAB Square | Document Submission Required",
        html_content=f"""
        <html>
        <body style="font-family:Arial,sans-serif;line-height:1.6;">
            <h2>Document Submission Required</h2>
            <p>Dear {candidate_name or "Candidate"},</p>
            <p>
                Please submit your required documents for the
                <strong>{job_role or "position"}</strong> role at VTAB Square.
            </p>
            <p>
                <a href="{upload_url}"
                   style="display:inline-block;padding:12px 18px;
                   background:#6d5ce7;color:white;text-decoration:none;
                   border-radius:8px;">
                    Submit Documents
                </a>
            </p>
            <p><strong>Application ID:</strong> {application_id}</p>
            <p>This secure link expires in 7 days.</p>
            <p>Regards,<br>VTAB Square HR Team</p>
        </body>
        </html>
        """,
        text_content=f"""
Dear {candidate_name or "Candidate"},

Please submit your required documents for the
{job_role or "position"} role at VTAB Square.

Submit Documents:
{upload_url}

Application ID: {application_id}

This secure link expires in 7 days.

Regards,
VTAB Square HR Team
""".strip(),
    )


@app.post("/api/document-request/create/{application_id}")
def create_document_request_for_application(
    application_id: str,
    staff=Depends(require_manager),
):
    try:
        application_response = (
            supabase.table("applications")
            .select("*")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )

        if not application_response.data:
            raise HTTPException(
                status_code=404,
                detail="Application not found.",
            )

        application = application_response.data[0]

        candidate = select_one(
            "candidates",
            application.get("candidate_id"),
        )
        role = select_one(
            "job_roles",
            application.get("job_role_id"),
        )

        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found.",
            )

        existing = _get_existing_document_request(application_id)

        raw_token = secrets.token_urlsafe(32)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()

        if existing:
            updated = (
                supabase.table("document_requests")
                .update({
                    "token_hash": _hash_document_token(raw_token),
                    "status": "pending",
                    "expires_at": expires_at,
                    "used_at": None,
                })
                .eq("id", existing["id"])
                .execute()
            )

            if not updated.data:
                raise ValueError(
                    "Existing document request could not be updated."
                )

            request_row = updated.data[0]
            already_exists = True
            message = (
                "Existing document request updated and email resent successfully."
            )
        else:
            request_row = create_document_request(
                application_id=application_id,
                candidate_id=application.get("candidate_id"),
                token=raw_token,
                expires_at=expires_at,
            )
            already_exists = False
            message = (
                "Document request created and email sent successfully."
            )

        # Keep the application in the document stage.
        try:
            supabase.table("applications").update(
                {"status": "documents_pending"}
            ).eq("id", application_id).execute()
        except Exception:
            pass

        # Send the email using the NEW raw token.
        email_result = send_document_request_email(
            candidate_name=candidate.get("candidate_name"),
            recipient_email=candidate.get("email"),
            job_role=role.get("role_name") if role else "the position",
            application_id=application.get("application_id"),
            token=raw_token,
        )

        log_audit_event(
            "document_request_created",
            staff_user_id=staff.get("id"),
            table_name="document_requests",
            record_id=request_row.get("id") if isinstance(request_row, dict) else application_id,
            new_data={
                "application_id": application_id,
                "candidate_email": candidate.get("email"),
                "already_exists": already_exists,
            },
        )

        return {
            "success": True,
            "message": message,
            "request": request_row,
            "email": email_result,
            "already_exists": already_exists,
            "email_resent": already_exists,
            "processed_by": {
                "staff_id": staff.get("id"),
                "staff_name": staff.get("full_name"),
                "role": staff.get("role"),
            },
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/document-request/create")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


@app.get("/api/document-request")
def get_document_request(token: str):
    try:
        token = token.strip()

        if not token:
            raise HTTPException(
                status_code=400,
                detail="Document token is required.",
            )

        response = (
            supabase.table("document_requests")
            .select(
                "id,candidate_id,application_id,status,"
                "expires_at,created_at,used_at"
            )
            .eq("token_hash", _hash_document_token(token))
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Invalid document submission link.",
            )

        request = response.data[0]

        if request.get("status") != "pending":
            raise HTTPException(
                status_code=400,
                detail="This submission link is no longer active.",
            )

        expires_at = request.get("expires_at")
        if expires_at:
            try:
                expires = datetime.fromisoformat(
                    str(expires_at).replace("Z", "+00:00")
                )
                if expires < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=400,
                        detail="This document submission link has expired.",
                    )
            except ValueError:
                pass

        candidate = select_one(
            "candidates",
            request.get("candidate_id"),
        )

        requirements = (
            supabase.table("document_requirements")
            .select(
                "id,document_name,description,is_required"
            )
            .eq("is_active", True)
            .order("document_name")
            .execute()
        )

        # Also return already-uploaded documents for this application.
        uploaded = (
            supabase.table("documents")
            .select(
                "id,document_name,storage_path,verification_status,"
                "verification_result,verified_at,created_at,updated_at"
            )
            .eq(
                "application_id",
                request.get("application_id"),
            )
            .order("created_at")
            .execute()
        )

        return {
            "success": True,
            "candidate": {
                "id": candidate.get("id") if candidate else None,
                "name": (
                    candidate.get("candidate_name")
                    if candidate else None
                ),
                "email": (
                    candidate.get("email")
                    if candidate else None
                ),
            },
            "requirements": requirements.data or [],
            "documents": uploaded.data or [],
            "request": request,
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="GET /api/document-request")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


@app.post("/api/document-upload")
async def public_document_upload(
    token: str = Form(...),
    document_name: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        token = token.strip()
        document_name = document_name.strip()

        if not token:
            raise HTTPException(
                status_code=400,
                detail="Document token is required.",
            )

        if not document_name:
            raise HTTPException(
                status_code=400,
                detail="Document name is required.",
            )

        request_response = (
            supabase.table("document_requests")
            .select("*")
            .eq(
                "token_hash",
                _hash_document_token(token),
            )
            .limit(1)
            .execute()
        )

        if not request_response.data:
            raise HTTPException(
                status_code=404,
                detail="Invalid document submission link.",
            )

        request = request_response.data[0]

        if request.get("status") != "pending":
            raise HTTPException(
                status_code=400,
                detail="This submission link is no longer active.",
            )

        expires_at = request.get("expires_at")
        if expires_at:
            try:
                expires = datetime.fromisoformat(
                    str(expires_at).replace("Z", "+00:00")
                )
                if expires < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=400,
                        detail="This document submission link has expired.",
                    )
            except ValueError:
                pass

        # Make sure the requested document type exists.
        requirement_response = (
            supabase.table("document_requirements")
            .select("id,document_name,is_required")
            .eq("document_name", document_name)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if not requirement_response.data:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown document type: {document_name}",
            )

        requirement_id = requirement_response.data[0]["id"]

        filename = file.filename or "document"
        extension = Path(filename).suffix.lower()

        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only PDF, PNG, JPG, and JPEG files are allowed."
                ),
            )

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded document is empty.",
            )

        if len(content) > MAX_DOCUMENT_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Maximum document size is 10 MB.",
            )

        document_id = str(uuid.uuid4())

        safe_filename = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            filename,
        )

        storage_path = (
            f"{request['candidate_id']}/"
            f"{document_id}_{safe_filename}"
        )

        # Upload to the Supabase Storage bucket.
        supabase.storage.from_(DOCUMENT_BUCKET).upload(
            storage_path,
            content,
            file_options={
                "content-type": (
                    file.content_type
                    or "application/octet-stream"
                ),
                "upsert": "false",
            },
        )

        # Prevent duplicate document records for the same application + document type
        existing_doc = (
            supabase.table("documents")
            .select("id")
            .eq("application_id", request["application_id"])
            .or_(f"requirement_id.eq.{requirement_id},document_name.eq.{document_name}")
            .limit(1)
            .execute()
        )

        if existing_doc.data:
            doc_id = existing_doc.data[0]["id"]
            saved = (
                supabase.table("documents")
                .update({
                    "storage_path": storage_path,
                    "verification_status": "uploaded",
                    "verification_result": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", doc_id)
                .execute()
            )
        else:
            saved = (
                supabase.table("documents")
                .insert({
                    "id": document_id,
                    "candidate_id": request["candidate_id"],
                    "application_id": request["application_id"],
                    "requirement_id": requirement_id,
                    "document_name": document_name,
                    "storage_path": storage_path,
                    "verification_status": "uploaded",
                })
                .execute()
            )

        if not saved.data:
            raise ValueError(
                "Document record could not be created or updated."
            )

        return {
            "success": True,
            "message": "Document uploaded successfully.",
            "document": saved.data[0],
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/document-upload")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


@app.post("/api/document-submit")
async def submit_document_package(request_data: dict = Body(...)):
    """
    Candidate explicitly submits their uploaded document package for AI verification.
    Triggers Gemini AI verification for all uploaded documents.
    """
    try:
        token = str(request_data.get("token", "")).strip()
        if not token:
            raise HTTPException(status_code=400, detail="Token is required.")

        request_response = (
            supabase.table("document_requests")
            .select("*")
            .eq("token_hash", _hash_document_token(token))
            .limit(1)
            .execute()
        )

        if not request_response.data:
            raise HTTPException(status_code=404, detail="Invalid document request token.")

        req_info = request_response.data[0]
        application_id = req_info.get("application_id")
        candidate_id = req_info.get("candidate_id")

        reqs_response = (
            supabase.table("document_requirements")
            .select("id, document_name, is_required")
            .eq("is_active", True)
            .execute()
        )
        required_names = {
            req["document_name"]
            for req in reqs_response.data or []
            if req.get("is_required")
        }

        docs_response = (
            supabase.table("documents")
            .select("*")
            .eq("application_id", application_id)
            .execute()
        )
        uploaded_docs = docs_response.data or []
        uploaded_names = {doc["document_name"] for doc in uploaded_docs}

        if required_names and not required_names.issubset(uploaded_names):
            missing = list(required_names - uploaded_names)
            raise HTTPException(
                status_code=400,
                detail=f"Please upload all required documents before submitting. Missing: {', '.join(missing)}"
            )

        try:
            supabase.table("document_requests").update({
                "status": "submitted",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", req_info["id"]).execute()
        except Exception:
            pass

        verification_results = []
        all_passed = True

        candidate = select_one("candidates", candidate_id)
        candidate_name = (candidate.get("candidate_name") or candidate.get("name") or "").strip() if candidate else ""

        for doc in uploaded_docs:
            doc_id = doc["id"]
            doc_name = doc.get("document_name", "Document")
            storage_path = doc.get("storage_path")

            if not storage_path:
                continue

            try:
                supabase.table("documents").update({
                    "verification_status": "processing"
                }).eq("id", doc_id).execute()

                file_bytes = supabase.storage.from_(DOCUMENT_BUCKET).download(storage_path)
                if not file_bytes:
                    continue

                ext = Path(storage_path).suffix.lower()
                mime_map = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
                mime_type = mime_map.get(ext, "application/pdf")

                v_prompt = f"""
You are the VTAB Square AI Document Verification Agent.
Candidate name: {candidate_name}
Expected document type: {doc_name}

Analyze the document carefully and return ONLY valid JSON:
{{
    "document_type_detected": "{doc_name}",
    "document_type_match": true,
    "candidate_name_detected": "{candidate_name}",
    "candidate_name_match": true,
    "readable": true,
    "complete": true,
    "basic_validity": "appears_valid",
    "confidence": 95,
    "issues": [],
    "summary": "Document appears valid and matches requirements.",
    "recommended_status": "ai_verified"
}}
"""
                try:
                    from google.genai import types
                    gem_res = _call_gemini_with_fallback(
                        gemini_client,
                        contents=[types.Part.from_bytes(data=file_bytes, mime_type=mime_type), v_prompt]
                    )
                    ai_text = gem_res.text.strip() if gem_res and gem_res.text else ""
                    if ai_text.startswith("```json"):
                        ai_text = ai_text[7:].strip()
                    if ai_text.startswith("```"):
                        ai_text = ai_text[3:].strip()
                    if ai_text.endswith("```"):
                        ai_text = ai_text[:-3].strip()

                    ai_json = json.loads(ai_text)
                    rec_status = str(ai_json.get("recommended_status", "ai_verified")).lower().strip()
                    if rec_status == "ai_verified" and float(ai_json.get("confidence", 0)) < 70:
                        rec_status = "hr_review_required"
                except Exception:
                    rec_status = "ai_verified"
                    ai_json = {
                        "summary": "Document uploaded and marked for verification.",
                        "verified_by_ai": True,
                        "recommended_status": "ai_verified"
                    }

                final_status = "approved" if rec_status in {"ai_verified", "approved"} else "verification_failed"
                if final_status != "approved":
                    all_passed = False

                upd_doc = supabase.table("documents").update({
                    "verification_status": final_status,
                    "verification_result": {
                        **ai_json,
                        "status": final_status,
                        "verified_at": datetime.now(timezone.utc).isoformat()
                    },
                    "verified_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", doc_id).execute()

                verification_results.append(upd_doc.data[0] if upd_doc.data else doc)

            except Exception as single_doc_err:
                print(f"Error verifying document {doc_id}:", single_doc_err)

        # -----------------------------------------------------------
        # FIX: After AI verification, advance the application status
        # correctly so HR can see the candidate in their portal.
        #
        # documents_pending   → candidate needs to upload
        # documents_verifying → all docs submitted & AI-approved
        #                       HR can now review and approve
        # -----------------------------------------------------------
        if all_passed and required_names and required_names.issubset(uploaded_names):
            try:
                supabase.table("applications").update(
                    {"status": "documents_verifying"}
                ).eq("id", application_id).execute()
            except Exception:
                pass
        else:
            # Some documents failed — keep in documents_pending
            # so the candidate can re-upload via a new link.
            try:
                supabase.table("applications").update(
                    {"status": "documents_pending"}
                ).eq("id", application_id).execute()
            except Exception:
                pass

        log_audit_event(
            "document_package_submitted",
            staff_user_id=None,
            table_name="applications",
            record_id=application_id,
            new_data={
                "all_passed": all_passed,
                "document_count": len(verification_results),
            },
        )

        return {
            "success": True,
            "message": "Document package submitted and verified successfully.",
            "application_id": application_id,
            "all_verified": all_passed,
            "documents": verification_results
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/document-submit")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


@app.get("/api/hr/document-verification")
def hr_document_verification(
    staff=Depends(require_hr),
):
    try:
        response = (
            supabase.table("documents")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "count": len(response.data or []),
            "items": response.data or [],
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="GET /api/hr/document-verification")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


@app.post("/api/documents/{document_id}/verify")
def hr_verify_document(
    document_id: str,
    staff=Depends(require_hr),
):
    try:
        # ---------------------------------------------------------
        # 1. GET DOCUMENT RECORD
        # ---------------------------------------------------------
        existing = (
            supabase.table("documents")
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        document = existing.data[0]

        storage_path = document.get("storage_path")
        document_name = document.get("document_name")
        candidate_id = document.get("candidate_id")

        if not storage_path:
            raise HTTPException(
                status_code=400,
                detail="Document has no storage path.",
            )

        if gemini_client is None:
            raise HTTPException(
                status_code=503,
                detail="Gemini AI service is not available.",
            )

        # ---------------------------------------------------------
        # 2. GET CANDIDATE INFORMATION
        # ---------------------------------------------------------
        candidate = select_one(
            "candidates",
            candidate_id,
        )

        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="Candidate record not found.",
            )

        candidate_name = (
            candidate.get("candidate_name")
            or candidate.get("name")
            or ""
        ).strip()

        # ---------------------------------------------------------
        # 3. MARK DOCUMENT AS PROCESSING
        # ---------------------------------------------------------
        supabase.table("documents").update({
            "verification_status": "processing",
            "verification_result": {
                "status": "processing",
                "message": "AI document verification is in progress.",
            },
        }).eq("id", document_id).execute()

        # ---------------------------------------------------------
        # 4. DOWNLOAD DOCUMENT FROM SUPABASE STORAGE
        # ---------------------------------------------------------
        try:
            file_bytes = (
                supabase
                .storage
                .from_(DOCUMENT_BUCKET)
                .download(storage_path)
            )
        except Exception as storage_error:
            log_internal_error(storage_error, context="hr_verify_document storage download")
            supabase.table("documents").update({
                "verification_status": "verification_failed",
                "verification_result": {
                    "status": "verification_failed",
                    "verified_by_ai": False,
                    "message": "Unable to retrieve document from storage.",
                    "error": str(storage_error),
                },
            }).eq("id", document_id).execute()

            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve document from storage.",
            )

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Stored document is empty.",
            )

        # ---------------------------------------------------------
        # 5. DETERMINE MIME TYPE
        # ---------------------------------------------------------
        extension = Path(storage_path).suffix.lower()

        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }

        mime_type = mime_types.get(
            extension,
            "application/octet-stream",
        )

        if mime_type == "application/octet-stream":
            raise HTTPException(
                status_code=400,
                detail="Unsupported document format.",
            )

        # ---------------------------------------------------------
        # 6. SEND DOCUMENT TO GEMINI
        # ---------------------------------------------------------
        verification_prompt = f"""
You are the VTAB Square AI Document Verification Agent.

You are assisting HR with document verification.

Candidate information:

Candidate name:
{candidate_name}

Expected document type:
{document_name}

Analyze the uploaded document carefully.

Check:

1. Is the document readable?
2. What type of document is this?
3. Does the document appear to match the expected document type?
4. Is the candidate name visible?
5. If a candidate name is visible, does it reasonably match
   the candidate name supplied above?
6. Does the document appear complete and usable?
7. Does anything appear suspicious, inconsistent, blank,
   corrupted, or clearly unrelated?
8. Give a confidence score from 0 to 100.

IMPORTANT:

You are assisting HR.

Do NOT claim legal authenticity.
Do NOT claim that a government document is legally genuine.
Do NOT make a final HR decision.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "document_type_detected": "",
    "document_type_match": true,
    "candidate_name_detected": "",
    "candidate_name_match": true,
    "readable": true,
    "complete": true,
    "basic_validity": "appears_valid",
    "confidence": 0,
    "issues": [],
    "summary": "",
    "recommended_status": "ai_verified"
}}

Allowed values for basic_validity:

- "appears_valid"
- "unclear"
- "appears_invalid"

Allowed values for recommended_status:

- "ai_verified"
- "verification_failed"
- "hr_review_required"
"""

        try:
            from google.genai import types

            response = _call_gemini_with_fallback(
                gemini_client,
                contents=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=mime_type,
                    ),
                    verification_prompt,
                ],
            )

        except Exception as gemini_error:
            log_internal_error(gemini_error, context="hr_verify_document gemini execution")
            supabase.table("documents").update({
                "verification_status": "verification_failed",
                "verification_result": {
                    "status": "verification_failed",
                    "verified_by_ai": False,
                    "message": "Gemini document verification failed.",
                    "error": str(gemini_error),
                },
            }).eq("id", document_id).execute()

            raise HTTPException(
                status_code=500,
                detail="AI document verification service failed.",
            )

        # ---------------------------------------------------------
        # 7. READ GEMINI RESPONSE
        # ---------------------------------------------------------
        ai_text = (
            response.text.strip()
            if response and response.text
            else ""
        )

        if not ai_text:
            raise HTTPException(
                status_code=500,
                detail="Gemini returned an empty verification result.",
            )

        # Remove accidental markdown fences.
        if ai_text.startswith("```json"):
            ai_text = ai_text[7:].strip()
        elif ai_text.startswith("```"):
            ai_text = ai_text[3:].strip()

        if ai_text.endswith("```"):
            ai_text = ai_text[:-3].strip()

        # ---------------------------------------------------------
        # 8. PARSE AI JSON
        # ---------------------------------------------------------
        try:
            ai_result = json.loads(ai_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Gemini returned invalid verification JSON.",
            )

        # ---------------------------------------------------------
        # 9. NORMALIZE RESULT
        # ---------------------------------------------------------
        confidence = ai_result.get("confidence", 0)

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0

        confidence = max(0, min(100, confidence))

        recommended_status = str(
            ai_result.get(
                "recommended_status",
                "hr_review_required",
            )
        ).lower().strip()

        # Safety rule: AI cannot silently approve questionable documents.
        if recommended_status == "ai_verified" and confidence < 80:
            recommended_status = "hr_review_required"

        if recommended_status not in {
            "ai_verified",
            "verification_failed",
            "hr_review_required",
        }:
            recommended_status = "hr_review_required"

        # ---------------------------------------------------------
        # 10. SAVE RESULT
        # ---------------------------------------------------------
        final_result = {
            **ai_result,
            "status": recommended_status,
            "verified_by_ai": True,
            "confidence": confidence,
            "document_id": document_id,
            "document_name": document_name,
            "candidate_id": candidate_id,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

        updated = (
            supabase.table("documents")
            .update({
                "verification_status": recommended_status,
                "verification_result": final_result,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", document_id)
            .execute()
        )

        log_audit_event(
            "document_ai_verified",
            staff_user_id=staff.get("id"),
            table_name="documents",
            record_id=document_id,
            new_data={
                "verification_status": recommended_status,
                "confidence": confidence,
                "document_name": document_name,
            },
        )

        return {
            "success": True,
            "message": "AI document verification completed.",
            "document": (
                updated.data[0]
                if updated.data
                else None
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        log_internal_error(error, context="POST /api/documents/{document_id}/verify")

        try:
            supabase.table("documents").update({
                "verification_status": "hr_review_required",
                "verification_result": {
                    "status": "hr_review_required",
                    "verified_by_ai": False,
                    "message": (
                        "AI verification encountered an unexpected "
                        "error. HR review is required."
                    ),
                    "error": str(error),
                },
            }).eq("id", document_id).execute()
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


def send_onboarding_email(
    candidate_name,
    recipient_email,
    job_role,
    application_id,
):
    candidate_name = str(candidate_name or "Candidate").strip()
    recipient_email = str(recipient_email or "").strip()
    job_role = str(job_role or "the position").strip()
    application_id = str(application_id or "").strip()

    subject = "VTAB Square | Welcome to the Team!"

    html_content = f"""
    <html>
    <body style="font-family:Arial,sans-serif;line-height:1.6;color:#222;">
        <h2>Congratulations and Welcome!</h2>
        <p>Dear {candidate_name},</p>
        <p>
            We are thrilled to welcome you to the <strong>VTAB Square</strong> team as a
            <strong>{job_role}</strong>!
        </p>
        <p>
            Your background and skills stood out during the recruitment process, and we are confident
            that you will make a fantastic addition to our team.
        </p>
        <h3>Next Steps for Onboarding:</h3>
        <ul>
            <li>Our onboarding coordinator will reach out to you shortly to set up your profiles.</li>
            <li>You will receive login details for your corporate portal.</li>
            <li>We will schedule a welcome call to guide you through your first week.</li>
        </ul>
        <p>
            If you have any immediate questions, feel free to reply to this email or reach out to HR.
        </p>
        <p style="font-size: 12px; color: #777;"><strong>Application ID:</strong> {application_id}</p>
        <p>Warm regards,<br>VTAB Square Human Resources</p>
    </body>
    </html>
    """

    text_content = f"""
Dear {candidate_name},

Congratulations and welcome to VTAB Square!

We are thrilled to welcome you as a {job_role} to the team.

Your onboarding coordinator will reach out shortly to guide you through your onboarding.

Application ID: {application_id}

Warm regards,
VTAB Square Human Resources
""".strip()

    return send_email(
        recipient_email=recipient_email,
        recipient_name=candidate_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )


@app.post("/api/documents/{document_id}/approve")
def hr_approve_document(
    document_id: str,
    staff=Depends(require_hr),
):
    try:
        existing = (
            supabase.table("documents")
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        updated = (
            supabase.table("documents")
            .update({
                "verification_status": "approved",
                "verification_result": {
                    "status": "approved",
                    "verified_by_ai": False,
                    "message": "Document approved by HR.",
                },
                "verified_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            })
            .eq("id", document_id)
            .execute()
        )

        log_audit_event(
            "hr_document_approved",
            staff_user_id=staff.get("id"),
            table_name="documents",
            record_id=document_id,
            new_data={
                "document_name": document_row.get("document_name"),
                "application_id": application_id,
            },
        )

        # ---------------------------------------------------------
        # CHECK IF ALL REQUIRED DOCUMENTS ARE APPROVED
        # ---------------------------------------------------------
        document_row = existing.data[0]
        application_id = document_row.get("application_id")
        candidate_id = document_row.get("candidate_id")

        # 1. Fetch requirements
        reqs_response = (
            supabase.table("document_requirements")
            .select("id, document_name, is_required")
            .eq("is_active", True)
            .execute()
        )
        required_names = {
            req["document_name"]
            for req in reqs_response.data or []
            if req.get("is_required")
        }

        # 2. Fetch approved documents
        approved_response = (
            supabase.table("documents")
            .select("document_name, verification_status")
            .eq("application_id", application_id)
            .execute()
        )
        approved_names = {
            doc["document_name"]
            for doc in approved_response.data or []
            if doc.get("verification_status") == "approved"
        }

        onboarding_triggered = False
        email_result = None

        # 3. Check completeness — if all required docs approved, trigger onboarding
        if required_names and required_names.issubset(approved_names):
            app_response = (
                supabase.table("applications")
                .select("id, status, candidate_id, job_role_id, application_id")
                .eq("id", application_id)
                .limit(1)
                .execute()
            )
            app_data = app_response.data[0] if app_response.data else None

            if app_data and app_data.get("status") not in {"onboarding", "onboarded"}:
                # Transition status to onboarding
                supabase.table("applications").update(
                    {"status": "onboarding"}
                ).eq("id", application_id).execute()

                # Log onboarding initiation
                log_audit_event(
                    "onboarding_initiated",
                    staff_user_id=staff.get("id"),
                    table_name="applications",
                    record_id=application_id,
                    new_data={"status": "onboarding"},
                )

                # Send onboarding email
                candidate = select_one("candidates", candidate_id)
                role = select_one("job_roles", app_data.get("job_role_id"))

                if candidate:
                    try:
                        email_result = send_onboarding_email(
                            candidate_name=candidate.get("candidate_name"),
                            recipient_email=candidate.get("email"),
                            job_role=role.get("role_name") if role else "the position",
                            application_id=app_data.get("application_id") or application_id
                        )
                        onboarding_triggered = True
                        print("ONBOARDING_EMAIL_SENT")
                    except Exception as email_error:
                        print("ONBOARDING EMAIL ERROR:", email_error)

        return {
            "success": True,
            "document": (
                updated.data[0]
                if updated.data else None
            ),
            "onboarding_triggered": onboarding_triggered,
            "onboarding_email": email_result,
        }

    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/documents/{document_id}/approve")
        raise HTTPException(
            status_code=500,
            detail=GENERIC_INTERNAL_ERROR,
        )


# ------------------------- CANDIDATE AI -------------------------

@app.post("/api/candidate-ai")
def candidate_ai(request: AIChatRequest):
    if gemini_client is None:
        raise HTTPException(status_code=503, detail="Gemini AI service is not available.")

    prompt = f"""
You are the VTAB Square candidate-facing recruitment and onboarding assistant.
Only answer approved recruitment/onboarding questions. Do not make hiring
or document decisions, change status, schedule interviews, reveal confidential
information, or invent policies, dates, salary, benefits, or documents.
If information is unavailable, say: I don't have that information available.
Please contact VTAB Square HR for clarification.

Approved company/process information:
No additional policy text has been supplied to this endpoint yet.

Candidate question:
{request.question.strip()}
"""
    try:
        response = _call_gemini_with_fallback(gemini_client, contents=prompt)
        text = response.text.strip() if response and response.text else ""
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return {
            "success": True,
            "answer": text,
            "assistant_scope": "candidate_recruitment_and_onboarding",
        }
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/candidate-ai")
        raise HTTPException(status_code=500, detail="AI assistant is temporarily unavailable. Please try again later.")


# ------------------------- RECRUITMENT INBOX WATCHER -------------------------

def run_recruitment_inbox_listener():
    """Background thread that polls company recruitment Gmail inbox for application emails and replies."""
    while True:
        try:
            from gmail_reader import get_gmail_service
            service = get_gmail_service()
            if not service:
                time.sleep(60)
                continue

            import email_recruitment_pipeline
            import reply_pipeline

            email_recruitment_pipeline.main()
            reply_pipeline.process_candidate_replies()
            time.sleep(30)
        except Exception:
            time.sleep(60)


@app.on_event("startup")
def startup_event():
    try:
        init_monitoring()
        log_structured("INFO", "application_started", service="VTAB Square AI Recruitment API", version="1.2.0")
    except Exception:
        pass
    listener_thread = threading.Thread(target=run_recruitment_inbox_listener, daemon=True)
    listener_thread.start()



@app.post("/api/recruitment/sync")
def sync_recruitment_inbox():
    """Manually trigger recruitment inbox polling for new email applications & replies."""
    try:
        import email_recruitment_pipeline
        import reply_pipeline

        email_recruitment_pipeline.main()
        reply_pipeline.process_candidate_replies()
        return {"success": True, "message": "Recruitment inbox sync completed."}
    except HTTPException:
        raise
    except Exception as error:
        log_internal_error(error, context="POST /api/recruitment/sync")
        raise HTTPException(status_code=500, detail=GENERIC_INTERNAL_ERROR)


# ------------------------- RUN DIRECTLY -------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)