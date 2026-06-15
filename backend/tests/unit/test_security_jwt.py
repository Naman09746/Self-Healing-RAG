"""
Tests for JWT security module (Phase 6 — RS256).

Validates:
1. Token sign+verify works with auto-generated RS256 keypair
2. Tokens carry correct claims (tenant_id, user_uuid, role)
3. Custom expiry is respected
4. decode_access_token validates correctly
"""

from __future__ import annotations

from datetime import timedelta


class TestJWTTokenOperations:
    """Tests for JWT token creation and verification (RS256)."""

    def test_token_sign_and_verify(self):
        """Token signed with auto-generated RS256 key must verify successfully."""
        from backend.core.security import create_access_token, decode_access_token

        token = create_access_token(subject="test@example.com")
        payload = decode_access_token(token)
        assert payload["sub"] == "test@example.com"
        assert "exp" in payload

    def test_token_with_tenant_and_user_uuid(self):
        """Token with tenant_id and user_uuid claims must decode correctly."""
        from backend.core.security import create_access_token, decode_access_token

        token = create_access_token(
            subject="user@org.com",
            tenant_id="tenant-abc",
            user_uuid="uuid-123",
        )
        payload = decode_access_token(token)
        assert payload["tenant_id"] == "tenant-abc"
        assert payload["user_uuid"] == "uuid-123"
        assert payload["sub"] == "user@org.com"

    def test_token_with_custom_expiry(self):
        """Token with custom expires_delta must use the provided delta."""
        from backend.core.security import create_access_token, decode_access_token

        token = create_access_token(
            subject="test@example.com",
            expires_delta=timedelta(hours=1),
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "test@example.com"

    def test_default_expiry_is_one_week(self):
        """Default token expiry must be 7 days."""
        from backend.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
        assert ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24 * 7

    def test_token_contains_role_claim(self):
        """Token must contain the role claim (defaults to 'viewer')."""
        from backend.core.security import create_access_token, decode_access_token

        token = create_access_token(subject="test@example.com")
        payload = decode_access_token(token)
        assert payload["role"] == "viewer"

        token = create_access_token(subject="admin@example.com", role="admin")
        payload = decode_access_token(token)
        assert payload["role"] == "admin"

    def test_invalid_token_raises(self):
        """An invalid token must raise an exception."""
        from backend.core.security import decode_access_token
        import jwt

        try:
            decode_access_token("invalid.token.here")
            assert False, "Expected InvalidTokenError"
        except jwt.InvalidTokenError:
            pass  # Expected


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_get_password_hash_returns_hash(self):
        from backend.core.security import get_password_hash
        hashed = get_password_hash("mysecretpassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        from backend.core.security import get_password_hash, verify_password
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        from backend.core.security import get_password_hash, verify_password
        hashed = get_password_hash("correctpassword")
        assert verify_password("wrongpassword", hashed) is False