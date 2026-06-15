"""Unit tests for Audit Logging (Phase 6)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.core.audit import (
    AuditLogger,
    log_user_login,
    log_api_request,
    log_rbac_denied,
    log_rate_limit_hit,
    log_prompt_injection,
    log_auth_failure,
)


@pytest.fixture
def tmp_audit_log():
    """Create a temporary directory for audit logs and patch settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Monkey-patch the audit logger to write to our temp dir
        logger = AuditLogger()
        logger._enabled = True
        log_file = tmp_path / "audit.log"
        logger._handler = open(log_file, "a")
        logger._handler.close()
        import builtins
        original_open = builtins.open

        class MockHandler:
            def __init__(self, f):
                self._f = f
                self.stream = f
            def close(self):
                self._f.close()

        def mock_open(*args, **kwargs):
            if "audit.log" in str(args[0]):
                f = original_open(log_file, *args[1:], **kwargs)
                return f
            return original_open(*args, **kwargs)

        yield tmp_path, log_file


class TestAuditLogger:
    def test_logger_initialization(self):
        logger = AuditLogger()
        assert logger is not None

    def test_log_event_structure(self, monkeypatch):
        """Verify that logged events have the expected structure."""
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        logger = AuditLogger()
        logger._handler = FakeHandler()
        logger._enabled = True

        logger.log(
            "test.event",
            user_uuid="user-123",
            ip_address="192.168.1.1",
            endpoint="/api/test",
            method="GET",
        )
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "test.event"
        assert event["user_uuid"] == "user-123"
        assert event["ip_address"] == "192.168.1.1"
        assert event["endpoint"] == "/api/test"
        assert "timestamp" in event

    def test_log_pii_hashed(self, monkeypatch):
        """Verify that email is hashed when logged."""
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        logger = AuditLogger()
        logger._handler = FakeHandler()
        logger._enabled = True

        logger.log(
            "test.event",
            email="user@example.com",
        )
        event = json.loads(events[0])
        assert "email_hash" in event
        assert event["email_hash"] != "user@example.com"
        assert len(event["email_hash"]) == 64  # SHA-256 hex


class TestConvenienceFunctions:
    def test_log_user_login(self, monkeypatch):
        """Verify log_user_login produces correct event."""
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_user_login(email="user@test.com", ip_address="10.0.0.1", user_agent="test-agent")
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "user.login"
        assert event["ip_address"] == "10.0.0.1"
        assert event["user_agent"] == "test-agent"
        assert "email_hash" in event

        audit_module.audit_logger = original_logger

    def test_log_api_request(self, monkeypatch):
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_api_request(method="POST", path="/api/ingest", status_code=200,
                        client_ip="10.0.0.1", duration_ms=45.2)
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "api.request"
        assert event["method"] == "POST"
        assert event["endpoint"] == "/api/ingest"
        assert event["status_code"] == "200"
        assert event["duration_ms"] == 45.2

        audit_module.audit_logger = original_logger

    def test_log_rbac_denied(self, monkeypatch):
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_rbac_denied(user_uuid="user-123", role="viewer",
                        required_role="admin", endpoint="/admin")
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "rbac.denied"
        assert event["role"] == "viewer"
        assert event["required_role"] == "admin"
        assert event["endpoint"] == "/admin"

        audit_module.audit_logger = original_logger

    def test_log_rate_limit_hit(self, monkeypatch):
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_rate_limit_hit(ip_address="10.0.0.1", user_uuid="user-123",
                          endpoint="/api/query")
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "rate_limit.hit"
        assert event["ip_address"] == "10.0.0.1"
        assert event["endpoint"] == "/api/query"

        audit_module.audit_logger = original_logger

    def test_log_prompt_injection(self, monkeypatch):
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_prompt_injection(query_hash="abc123", threat_level="high",
                            user_uuid="user-123")
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "prompt_injection"
        assert event["threat_level"] == "high"

        audit_module.audit_logger = original_logger

    def test_log_auth_failure(self, monkeypatch):
        events = []

        class FakeHandler:
            def __init__(self):
                self.stream = self
            def write(self, s):
                events.append(s)
            def flush(self):
                pass

        import backend.core.audit as audit_module
        original_logger = audit_module.audit_logger
        audit_module.audit_logger = AuditLogger()
        audit_module.audit_logger._handler = FakeHandler()
        audit_module.audit_logger._enabled = True

        log_auth_failure(email="user@test.com", ip_address="10.0.0.1",
                        reason="invalid password")
        assert len(events) == 1
        event = json.loads(events[0])
        assert event["event"] == "auth.failure"
        assert event["reason"] == "invalid password"

        audit_module.audit_logger = original_logger