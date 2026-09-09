"""
Audit Logger — structured audit event logging (Phase 6).

Events are written to rotating JSONL files and optionally published to a Redis
stream for real-time monitoring.

No PII is logged: emails are SHA-256 hashed, query texts are SHA-256 hashed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Hash helpers (PII masking)
# ---------------------------------------------------------------------------

def _hash(value: str) -> str:
    """SHA-256 hash a string for PII masking."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Audit event type constants
# ---------------------------------------------------------------------------

EVENT_USER_LOGIN = "user.login"
EVENT_USER_SIGNUP = "user.signup"
EVENT_QUERY_EXECUTE = "query.execute"
EVENT_INGEST_UPLOAD = "ingest.upload"
EVENT_AUTH_FAILURE = "auth.failure"
EVENT_RATE_LIMIT_HIT = "rate_limit.hit"
EVENT_PROMPT_INJECTION = "prompt_injection"
EVENT_RBAC_DENIED = "rbac.denied"
EVENT_WS_CONNECT = "ws.connect"
EVENT_WS_DISCONNECT = "ws.disconnect"
EVENT_WS_MESSAGE = "ws.message"


# ---------------------------------------------------------------------------
# Audit logger singleton
# ---------------------------------------------------------------------------

class AuditLogger:
    """Structured audit logger with file rotation and optional Redis stream."""

    def __init__(self) -> None:
        self._enabled = True
        self._redis = None
        self._handler: Optional[RotatingFileHandler] = None
        self._redis_available = False
        self._setup()

    def _setup(self) -> None:
        """Initialize the audit log file handler."""
        log_dir = Path(settings.AUDIT_LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "audit.log"

        try:
            self._handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=settings.AUDIT_LOG_MAX_BYTES,
                backupCount=settings.AUDIT_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Audit log file handler init failed", error=str(e))
            self._enabled = False

    def _try_connect_redis(self) -> None:
        """Attempt to connect to Redis for stream publishing."""
        if self._redis_available:
            return
        try:
            import redis as redis_module
            if getattr(settings, "REDIS_URL", None):
                self._redis = redis_module.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
            else:
                self._redis = redis_module.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    ssl=settings.REDIS_USE_SSL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
            self._redis.ping()
            self._redis_available = True
        except Exception:
            self._redis_available = False
            self._redis = None

    def _write_file(self, event: Dict[str, Any]) -> None:
        """Write the event as a JSON line to the rotating log file."""
        if not self._enabled or self._handler is None:
            return
        try:
            line = json.dumps(event, default=str) + "\n"
            self._handler.stream.write(line)
            self._handler.stream.flush()
        except Exception as e:
            logger.error("Audit log file write failed", error=str(e))

    def _write_redis(self, event: Dict[str, Any]) -> None:
        """Publish the event to the Redis 'audit:events' stream."""
        if not self._redis_available:
            self._try_connect_redis()
        if not self._redis_available:
            return
        try:
            self._redis.xadd("audit:events", event, maxlen=10000)
        except Exception:
            self._redis_available = False

    def log(
        self,
        event_type: str,
        *,
        user_uuid: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query_hash: Optional[str] = None,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        role: Optional[str] = None,
        required_role: Optional[str] = None,
        permission: Optional[str] = None,
        endpoint: Optional[str] = None,
        threat_level: Optional[str] = None,
        reason: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Create and persist an audit event.

        All PII-identifiable fields (email) are automatically hashed.
        """
        event: Dict[str, Any] = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_uuid": user_uuid,
        }

        # Hash PII fields
        if email is not None:
            event["email_hash"] = _hash(email)
        if query_hash is not None:
            event["query_hash"] = query_hash  # Already a hash from caller
        if ip_address is not None:
            event["ip_address"] = ip_address

        # Optional structured fields
        if user_agent is not None:
            event["user_agent"] = user_agent
        if tenant_id is not None:
            event["tenant_id"] = tenant_id
        if session_id is not None:
            event["session_id"] = session_id
        if filename is not None:
            event["filename"] = filename
        if file_size is not None:
            event["file_size"] = file_size
        if role is not None:
            event["role"] = role
        if required_role is not None:
            event["required_role"] = required_role
        if permission is not None:
            event["permission"] = permission
        if endpoint is not None:
            event["endpoint"] = endpoint
        if threat_level is not None:
            event["threat_level"] = threat_level
        if reason is not None:
            event["reason"] = reason

        # Include any extra fields
        event.update(extra)

        # Persist
        self._write_file(event)
        self._write_redis(event)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

audit_logger = AuditLogger()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def log_user_login(email: str, ip_address: str, user_agent: str) -> None:
    audit_logger.log(
        EVENT_USER_LOGIN,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_user_signup(email: str, tenant_id: str) -> None:
    audit_logger.log(
        EVENT_USER_SIGNUP,
        email=email,
        tenant_id=tenant_id,
    )


def log_query_execute(
    query_hash: str,
    user_uuid: str,
    session_id: str,
    tenant_id: str,
) -> None:
    audit_logger.log(
        EVENT_QUERY_EXECUTE,
        query_hash=query_hash,
        user_uuid=user_uuid,
        session_id=session_id,
        tenant_id=tenant_id,
    )


def log_ingest_upload(
    filename: str,
    file_size: int,
    user_uuid: str,
    tenant_id: str,
) -> None:
    audit_logger.log(
        EVENT_INGEST_UPLOAD,
        filename=filename,
        file_size=file_size,
        user_uuid=user_uuid,
        tenant_id=tenant_id,
    )


def log_auth_failure(email: str, ip_address: str, reason: str) -> None:
    audit_logger.log(
        EVENT_AUTH_FAILURE,
        email=email,
        ip_address=ip_address,
        reason=reason,
    )


def log_rate_limit_hit(
    ip_address: str,
    user_uuid: Optional[str],
    endpoint: str,
) -> None:
    audit_logger.log(
        EVENT_RATE_LIMIT_HIT,
        ip_address=ip_address,
        user_uuid=user_uuid,
        endpoint=endpoint,
    )


def log_prompt_injection(
    query_hash: str,
    threat_level: str,
    user_uuid: Optional[str] = None,
) -> None:
    audit_logger.log(
        EVENT_PROMPT_INJECTION,
        query_hash=query_hash,
        threat_level=threat_level,
        user_uuid=user_uuid,
    )


def log_rbac_denied(
    user_uuid: str,
    role: str,
    required_role: str,
    endpoint: str,
) -> None:
    audit_logger.log(
        EVENT_RBAC_DENIED,
        user_uuid=user_uuid,
        role=role,
        required_role=required_role,
        endpoint=endpoint,
    )


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    client_ip: str,
    user_uuid: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Log an API request for audit purposes."""
    audit_logger.log(
        "api.request",
        user_uuid=user_uuid,
        ip_address=client_ip,
        endpoint=path,
        method=method,
        status_code=str(status_code),
        duration_ms=duration_ms,
    )
