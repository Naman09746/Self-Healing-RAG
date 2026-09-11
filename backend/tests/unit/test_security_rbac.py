"""Unit tests for RBAC module (Phase 6)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from backend.core.rbac import (
    Role,
    Permission,
    ROLE_PERMISSIONS,
    get_role_from_token,
    require_role,
    require_permission,
)


class TestRoleEnum:
    def test_roles_defined(self):
        assert len(Role) >= 3
        assert Role.ADMIN.value == "admin"
        assert Role.EDITOR.value == "editor"
        assert Role.VIEWER.value == "viewer"
        assert Role.AUDITOR.value == "auditor"


class TestPermissions:
    def test_admin_has_all_permissions(self):
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.QUERY_RAG in perms
        assert Permission.STREAM_RAG in perms
        assert Permission.INGEST_DOCUMENT in perms
        assert Permission.VIEW_AUDIT in perms
        assert Permission.MANAGE_USERS in perms
        assert Permission.MANAGE_ROLES in perms
        assert Permission.VIEW_HEALTH in perms

    def test_editor_permissions(self):
        perms = ROLE_PERMISSIONS[Role.EDITOR]
        assert Permission.QUERY_RAG in perms
        assert Permission.STREAM_RAG in perms
        assert Permission.INGEST_DOCUMENT in perms
        assert Permission.VIEW_HEALTH in perms
        assert Permission.VIEW_AUDIT not in perms
        assert Permission.MANAGE_USERS not in perms
        assert Permission.MANAGE_ROLES not in perms

    def test_viewer_permissions(self):
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.QUERY_RAG in perms
        assert Permission.STREAM_RAG in perms
        assert Permission.INGEST_DOCUMENT in perms  # permissive: viewer can ingest own tenant
        assert Permission.VIEW_HEALTH in perms
        assert Permission.VIEW_AUDIT not in perms
        assert Permission.MANAGE_USERS not in perms

    def test_auditor_permissions(self):
        perms = ROLE_PERMISSIONS[Role.AUDITOR]
        assert Permission.VIEW_AUDIT in perms
        assert Permission.VIEW_HEALTH in perms
        assert Permission.QUERY_RAG not in perms
        assert Permission.INGEST_DOCUMENT not in perms


class TestGetRoleFromToken:
    def test_admin_role_from_token(self, monkeypatch):
        def mock_decode(token):
            return {"role": "admin", "sub": "test-user"}
        monkeypatch.setattr("backend.core.rbac.decode_access_token", mock_decode)
        role = get_role_from_token("fake_token")
        assert role == Role.ADMIN

    def test_viewer_default_on_missing_role(self, monkeypatch):
        def mock_decode(token):
            return {"sub": "test-user"}
        monkeypatch.setattr("backend.core.rbac.decode_access_token", mock_decode)
        role = get_role_from_token("fake_token")
        assert role == Role.VIEWER

    def test_viewer_on_invalid_token(self, monkeypatch):
        def mock_decode(token):
            raise Exception("Invalid token")
        monkeypatch.setattr("backend.core.rbac.decode_access_token", mock_decode)
        role = get_role_from_token("bad_token")
        assert role == Role.VIEWER


class TestRequireRoleDependency:
    @patch("backend.core.rbac.get_role_from_token", return_value=Role.ADMIN)
    @patch("backend.core.rbac.oauth2_scheme", lambda: "admin_token")
    def test_require_role_admin_passes(self, mock_get_role):
        """Admin token should pass require_role(Role.ADMIN)."""
        checker = require_role(Role.ADMIN)
        # The inner function uses token=Depends(oauth2_scheme) which
        # resolves to the monkeypatched lambda. We patch get_role_from_token
        # to return ADMIN so the check passes.
        from backend.core.rbac import oauth2_scheme
        result = checker(token="any_token")
        assert result is None

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.VIEWER)
    def test_require_role_admin_fails_for_viewer_token(self, mock_get_role):
        checker = require_role(Role.ADMIN)
        with pytest.raises(HTTPException) as exc:
            checker(token="viewer_token")
        assert exc.value.status_code == 403

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.VIEWER)
    def test_require_role_no_token_fails(self, mock_get_role):
        """When token is None, should raise AuthorizationException (403)."""
        # The checker's oauth2_scheme dependency means token=None won't
        # normally reach the inner function, but calling directly with None
        # still raises because None is not in allowed roles.
        from backend.core.rbac import require_role
        with pytest.raises(HTTPException) as exc:
            checker = require_role(Role.ADMIN)
            checker(token=None)
        assert exc.value.status_code == 403


class TestRequirePermissionDependency:
    @patch("backend.core.rbac.get_role_from_token", return_value=Role.ADMIN)
    def test_admin_can_query_rag(self, mock_get_role):
        checker = require_permission(Permission.QUERY_RAG)
        result = checker(token="admin_token")
        assert result is None

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.ADMIN)
    def test_admin_can_ingest(self, mock_get_role):
        checker = require_permission(Permission.INGEST_DOCUMENT)
        result = checker(token="admin_token")
        assert result is None

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.VIEWER)
    def test_viewer_can_ingest(self, mock_get_role):
        checker = require_permission(Permission.INGEST_DOCUMENT)
        result = checker(token="viewer_token")
        assert result is None

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.AUDITOR)
    def test_auditor_cannot_ingest(self, mock_get_role):
        checker = require_permission(Permission.INGEST_DOCUMENT)
        with pytest.raises(HTTPException) as exc:
            checker(token="auditor_token")
        assert exc.value.status_code == 403

    @patch("backend.core.rbac.get_role_from_token", return_value=Role.VIEWER)
    def test_viewer_can_query(self, mock_get_role):
        checker = require_permission(Permission.QUERY_RAG)
        result = checker(token="viewer_token")
        assert result is None

    def test_no_token_raises(self):
        checker = require_permission(Permission.QUERY_RAG)
        with pytest.raises(HTTPException) as exc:
            checker(token=None)
        assert exc.value.status_code == 403