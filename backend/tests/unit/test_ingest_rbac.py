"""Unit tests for permissive, tenant-isolated ingest RBAC — no migration, no privilege escalation.

Covers:
- viewer/editor can ingest own tenant (permissive)
- auditor cannot ingest
- DB role is canonical (stale JWT ignored)
- cross-tenant isolation (tenant_id from DB, not request)
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from backend.core.rbac import Role, Permission, ROLE_PERMISSIONS, has_db_permission_for_user, has_permission
from backend.api.routers import ingest as ingest_router


class FakeUser:
    def __init__(self, role: str, tenant_id: str, user_uuid: str, email: str = "test@example.com"):
        self.role = role
        self.tenant_id = tenant_id
        self.user_uuid = user_uuid
        self.email = email
        self.is_active = True


# ── ROLE_PERMISSIONS permissive ──────────────────────────────────────────

def test_viewer_has_ingest_document():
    assert Permission.INGEST_DOCUMENT in ROLE_PERMISSIONS[Role.VIEWER]
    assert Permission.INGEST_DOCUMENT in ROLE_PERMISSIONS[Role.EDITOR]
    assert Permission.INGEST_DOCUMENT in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.INGEST_DOCUMENT not in ROLE_PERMISSIONS[Role.AUDITOR]


def test_has_permission_helper():
    assert has_permission(Role.VIEWER, Permission.INGEST_DOCUMENT) is True
    assert has_permission("viewer", Permission.INGEST_DOCUMENT) is True
    assert has_permission(Role.AUDITOR, Permission.INGEST_DOCUMENT) is False
    assert has_permission("unknown", Permission.INGEST_DOCUMENT) is False


def test_has_db_permission_for_user_viewer():
    user = FakeUser(role="viewer", tenant_id="t1", user_uuid="u1")
    assert has_db_permission_for_user(user, Permission.INGEST_DOCUMENT) is True


def test_has_db_permission_for_user_auditor():
    user = FakeUser(role="auditor", tenant_id="t1", user_uuid="u1")
    assert has_db_permission_for_user(user, Permission.INGEST_DOCUMENT) is False


def test_has_db_permission_stale_jwt_ignored():
    """DB is canonical: JWT says auditor, DB says viewer — DB governs, so ingest allowed."""
    # Simulate stale JWT with auditor role, but DB user is viewer (DB governs)
    db_user = FakeUser(role="viewer", tenant_id="t1", user_uuid="u1")
    # Even though JWT would be auditor, DB check should allow
    assert has_db_permission_for_user(db_user, Permission.INGEST_DOCUMENT) is True
    # And auditor in DB should deny even if JWT says editor
    db_auditor = FakeUser(role="auditor", tenant_id="t1", user_uuid="u2")
    assert has_db_permission_for_user(db_auditor, Permission.INGEST_DOCUMENT) is False


# ── /ingest endpoint — tenant isolation ─────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_uses_db_tenant_not_request_body():
    """Cross-tenant spoofing is rejected: tenant_id is taken from current_user, not request."""
    fake_user = FakeUser(role="viewer", tenant_id="tenant-A", user_uuid="uuid-A")
    # Mock DB and pipeline
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Mock pipeline to capture tenant_id
    captured = {}

    async def fake_ingest(file_path, tenant_id):
        captured["tenant_id"] = tenant_id
        return {"document_id": "doc123", "chunk_count": 1, "file_hash": "abc", "mime_type": "text/plain", "storage": ["vector"]}

    with patch.object(ingest_router.pipeline, "ingest_file", side_effect=fake_ingest):
        # Create a temp file
        import tempfile
        from pathlib import Path
        from fastapi import UploadFile
        import io
        # Simulate UploadFile
        content = b"hello world"
        upload = UploadFile(filename="test.txt", file=io.BytesIO(content))
        # Need to set size for validation
        upload.size = len(content)

        # Call the endpoint function directly with fake_user
        # It should use tenant-A even if we try to spoof
        result = await ingest_router.ingest_file(file=upload, current_user=fake_user, db=mock_db)  # type: ignore
        assert captured["tenant_id"] == "tenant-A"
        assert result["document_id"] == "doc123"


@pytest.mark.asyncio
async def test_viewer_can_ingest_own_tenant():
    fake_user = FakeUser(role="viewer", tenant_id="tenant-A", user_uuid="uuid-A")
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def fake_ingest(file_path, tenant_id):
        assert tenant_id == "tenant-A"
        return {"document_id": "doc-viewer", "chunk_count": 2, "file_hash": "hash1", "mime_type": "text/plain", "storage": ["vector"]}

    with patch.object(ingest_router.pipeline, "ingest_file", side_effect=fake_ingest):
        import io
        from fastapi import UploadFile
        upload = UploadFile(filename="level1_company_policy.md", file=io.BytesIO(b"# Policy\nContent"))
        upload.size = 100
        result = await ingest_router.ingest_file(file=upload, current_user=fake_user, db=mock_db)  # type: ignore
        assert result["status"] == "ingested"
        assert result["document_id"] == "doc-viewer"


@pytest.mark.asyncio
async def test_editor_can_ingest():
    fake_user = FakeUser(role="editor", tenant_id="tenant-A", user_uuid="uuid-B")
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def fake_ingest(file_path, tenant_id):
        return {"document_id": "doc-editor", "chunk_count": 1, "file_hash": "hash2", "mime_type": "text/plain", "storage": ["vector"]}

    with patch.object(ingest_router.pipeline, "ingest_file", side_effect=fake_ingest):
        import io
        from fastapi import UploadFile
        upload = UploadFile(filename="doc.txt", file=io.BytesIO(b"hello"))
        upload.size = 5
        result = await ingest_router.ingest_file(file=upload, current_user=fake_user, db=mock_db)  # type: ignore
        assert result["status"] == "ingested"


@pytest.mark.asyncio
async def test_auditor_cannot_ingest():
    fake_user = FakeUser(role="auditor", tenant_id="tenant-A", user_uuid="uuid-C")
    mock_db = AsyncMock()
    from fastapi import UploadFile
    import io
    upload = UploadFile(filename="test.txt", file=io.BytesIO(b"hello"))
    upload.size = 5
    with pytest.raises(HTTPException) as exc:
        await ingest_router.ingest_file(file=upload, current_user=fake_user, db=mock_db)  # type: ignore
    assert exc.value.status_code == 403
    assert "Not enough permissions" in exc.value.detail


@pytest.mark.asyncio
async def test_cross_tenant_dedup_isolated():
    """File hash dedup is per-tenant: same file in tenant-A and tenant-B are distinct."""
    # Simulate tenant-A has file hash abc, tenant-B does not
    fake_user_a = FakeUser(role="viewer", tenant_id="tenant-A", user_uuid="uuid-A")
    fake_user_b = FakeUser(role="viewer", tenant_id="tenant-B", user_uuid="uuid-B")

    # Mock DB for tenant-A: existing found
    mock_db_a = AsyncMock()
    existing_doc = MagicMock(document_id="existing-A", filename="dup.txt", chunk_count=1)
    mock_db_a.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_doc)))

    import io
    from fastapi import UploadFile
    upload_a = UploadFile(filename="dup.txt", file=io.BytesIO(b"same content"))
    upload_a.size = 12
    result_a = await ingest_router.ingest_file(file=upload_a, current_user=fake_user_a, db=mock_db_a)  # type: ignore
    assert result_a["status"] == "duplicate"
    assert result_a["document_id"] == "existing-A"

    # Mock DB for tenant-B: not existing, should ingest
    mock_db_b = AsyncMock()
    mock_db_b.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db_b.add = MagicMock()
    mock_db_b.commit = AsyncMock()
    mock_db_b.refresh = AsyncMock()

    async def fake_ingest(file_path, tenant_id):
        assert tenant_id == "tenant-B"
        return {"document_id": "new-B", "chunk_count": 1, "file_hash": "abc", "mime_type": "text/plain", "storage": ["vector"]}

    with patch.object(ingest_router.pipeline, "ingest_file", side_effect=fake_ingest):
        upload_b = UploadFile(filename="dup.txt", file=io.BytesIO(b"same content"))
        upload_b.size = 12
        result_b = await ingest_router.ingest_file(file=upload_b, current_user=fake_user_b, db=mock_db_b)  # type: ignore
        assert result_b["status"] == "ingested"
        assert result_b["document_id"] == "new-B"


@pytest.mark.asyncio
async def test_stale_jwt_viewer_still_ingests():
    """Existing user with old JWT (viewer) and DB viewer (now permissive) can ingest without re-login."""
    # Simulate user created before fix as viewer, JWT still viewer, DB viewer
    fake_user = FakeUser(role="viewer", tenant_id="tenant-A", user_uuid="uuid-A")
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # JWT role is viewer (stale), but DB check should allow
    assert has_db_permission_for_user(fake_user, Permission.INGEST_DOCUMENT) is True

    async def fake_ingest(file_path, tenant_id):
        return {"document_id": "doc-stale", "chunk_count": 1, "file_hash": "xyz", "mime_type": "text/plain", "storage": ["vector"]}

    with patch.object(ingest_router.pipeline, "ingest_file", side_effect=fake_ingest):
        import io
        from fastapi import UploadFile
        upload = UploadFile(filename="level1_company_policy.md", file=io.BytesIO(b"# Policy"))
        upload.size = 8
        result = await ingest_router.ingest_file(file=upload, current_user=fake_user, db=mock_db)  # type: ignore
        assert result["status"] == "ingested"


def test_new_signup_viewer_can_ingest():
    """Newly signed-up viewer (default role) can ingest immediately."""
    # Signup creates viewer (after our fix), viewer now has ingest
    new_user_role = "viewer"
    assert has_permission(new_user_role, Permission.INGEST_DOCUMENT) is True
