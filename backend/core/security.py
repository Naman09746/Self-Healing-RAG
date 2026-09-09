"""
Security Module — RS256 JWT, password hashing, key management.

Phase 6 migration:
- Replaced HS256 (symmetric) with RS256 (asymmetric RSA-SHA256).
- Removed hardcoded SECRET_KEY fallback (security vulnerability).
- Added auto-generation of RSA keypair for development.
- Added generate_rsa_keypair() helper for key rotation.
"""

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Tuple

import jwt
import bcrypt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------
# Phase 6: RS256 asymmetric keys.
# Keys are stored as base64-encoded PEM strings in settings (loaded from .env).
# If no keys are configured, auto-generate a keypair for development.

_PRIVATE_KEY: Optional[Any] = None
_PUBLIC_KEY: Optional[Any] = None


def _load_or_generate_keys() -> Tuple[Any, Any]:
    """Load RSA keypair from settings, or generate one for development."""
    global _PRIVATE_KEY, _PUBLIC_KEY

    if _PRIVATE_KEY is not None and _PUBLIC_KEY is not None:
        return _PRIVATE_KEY, _PUBLIC_KEY

    private_key_pem_b64 = settings.JWT_PRIVATE_KEY
    public_key_pem_b64 = settings.JWT_PUBLIC_KEY

    if private_key_pem_b64:
        # Decode from base64
        try:
            private_key_pem = base64.b64decode(private_key_pem_b64).decode("utf-8")
            _PRIVATE_KEY = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
        except Exception as e:
            logger.error("Failed to load JWT_PRIVATE_KEY", error=str(e))
            raise RuntimeError(
                "JWT_PRIVATE_KEY is set but could not be decoded. "
                "Ensure it is a base64-encoded PEM string."
            ) from e

        if public_key_pem_b64:
            try:
                public_key_pem = base64.b64decode(public_key_pem_b64).decode("utf-8")
                _PUBLIC_KEY = serialization.load_pem_public_key(
                    public_key_pem.encode("utf-8"),
                    backend=default_backend(),
                )
            except Exception as e:
                logger.error("Failed to load JWT_PUBLIC_KEY", error=str(e))
                raise RuntimeError(
                    "JWT_PUBLIC_KEY is set but could not be decoded."
                ) from e
        else:
            _PUBLIC_KEY = _PRIVATE_KEY.public_key()
            logger.info("JWT_PUBLIC_KEY not provided; derived from private key.")
    else:
        # Auto-generate development keypair
        logger.warning(
            "No JWT_PRIVATE_KEY configured. Auto-generating development keypair. "
            "Set JWT_PRIVATE_KEY and JWT_PUBLIC_KEY in .env for production."
        )
        _PRIVATE_KEY = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        _PUBLIC_KEY = _PRIVATE_KEY.public_key()

    return _PRIVATE_KEY, _PUBLIC_KEY


def get_private_key() -> Any:
    """Get the RSA private key for signing JWT tokens."""
    return _load_or_generate_keys()[0]


def get_public_key() -> Any:
    """Get the RSA public key for verifying JWT tokens."""
    return _load_or_generate_keys()[1]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def generate_rsa_keypair() -> str:
    """
    Generate and print a new RSA-2048 keypair as base64-encoded PEM strings.

    Usage::
        python -c "from backend.core.security import generate_rsa_keypair; print(generate_rsa_keypair())"

    Returns instructions for updating .env.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_b64 = base64.b64encode(private_pem).decode("utf-8")
    public_b64 = base64.b64encode(public_pem).decode("utf-8")

    return (
        f"# Add these to your .env file:\n"
        f"JWT_PRIVATE_KEY={private_b64}\n"
        f"JWT_PUBLIC_KEY={public_b64}\n"
    )


# ---------------------------------------------------------------------------
# Token lifetime
# ---------------------------------------------------------------------------
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT creation & verification
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str | Any,
    expires_delta: timedelta = None,
    tenant_id: Optional[str] = None,
    user_uuid: Optional[str] = None,
    role: str = "viewer",
) -> str:
    """Create an RS256-signed JWT access token.

    Parameters
    ----------
    subject : str
        Typically the user's email.
    expires_delta : timedelta, optional
        Token expiry. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.
    tenant_id : str, optional
        Multi-tenant identifier.
    user_uuid : str, optional
        Immutable user UUID for storage isolation.
    role : str
        User role for RBAC. Defaults to 'viewer'.

    Returns
    -------
    str
        Encoded JWT string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
    }
    if tenant_id is not None:
        to_encode["tenant_id"] = tenant_id
    if user_uuid is not None:
        to_encode["user_uuid"] = user_uuid

    private_key = get_private_key()
    encoded_jwt = jwt.encode(
        to_encode, private_key, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify an RS256-signed JWT access token.

    Parameters
    ----------
    token : str
        The JWT string to decode.

    Returns
    -------
    dict
        The decoded payload.

    Raises
    ------
    jwt.InvalidTokenError
        If the token is invalid, expired, or tampered.
    """
    public_key = get_public_key()
    return jwt.decode(
        token, public_key, algorithms=[settings.JWT_ALGORITHM]
    )