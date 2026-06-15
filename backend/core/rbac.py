"""
RBAC Module — Role-Based Access Control (Phase 6).

Provides role and permission enums, FastAPI dependencies for route protection,
and a utility for extracting roles from JWT tokens.
"""

from __future__ import annotations

import enum
from typing import Annotated, List, Optional, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.core.security import decode_access_token

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class Role(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    AUDITOR = "auditor"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class Permission(str, enum.Enum):
    QUERY_RAG = "query:rag"
    STREAM_RAG = "query:stream"
    INGEST_DOCUMENT = "ingest:document"
    VIEW_AUDIT = "audit:view"
    MANAGE_USERS = "users:manage"
    MANAGE_ROLES = "roles:manage"
    VIEW_HEALTH = "health:view"


# ---------------------------------------------------------------------------
# Role → Permission mapping
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.QUERY_RAG,
        Permission.STREAM_RAG,
        Permission.INGEST_DOCUMENT,
        Permission.VIEW_AUDIT,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.VIEW_HEALTH,
    },
    Role.EDITOR: {
        Permission.QUERY_RAG,
        Permission.STREAM_RAG,
        Permission.INGEST_DOCUMENT,
        Permission.VIEW_HEALTH,
    },
    Role.VIEWER: {
        Permission.QUERY_RAG,
        Permission.STREAM_RAG,
        Permission.VIEW_HEALTH,
    },
    Role.AUDITOR: {
        Permission.VIEW_AUDIT,
        Permission.VIEW_HEALTH,
    },
}


# ---------------------------------------------------------------------------
# Role extraction from JWT
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


def get_role_from_token(token: str) -> Role:
    """Extract the role claim from a JWT token.

    If the token is invalid or the role claim is missing, returns ``Role.VIEWER``.
    """
    try:
        payload = decode_access_token(token)
        role_str = payload.get("role", "viewer")
        return Role(role_str)
    except Exception:
        return Role.VIEWER


def get_current_user_role(
    token: str = Depends(oauth2_scheme),
) -> Optional[Role]:
    """FastAPI dependency that extracts the user's role from the JWT.

    Returns None for unauthenticated requests (no token provided).
    """
    if token is None:
        return None
    return get_role_from_token(token)


# ---------------------------------------------------------------------------
# FastAPI dependency guards
# ---------------------------------------------------------------------------

class AuthorizationException(HTTPException):
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def require_role(*roles: Role):
    """FastAPI dependency: require the authenticated user to have one of the
    specified roles.

    Usage::

        @router.get("/admin")
        async def admin_endpoint(_: None = Depends(require_role(Role.ADMIN))):
            ...
    """
    allowed_roles = set(roles)

    def role_checker(token: str = Depends(oauth2_scheme)) -> None:
        if token is None:
            raise AuthorizationException("Authentication required")
        user_role = get_role_from_token(token)
        if user_role not in allowed_roles:
            raise AuthorizationException(
                f"Requires one of roles: {', '.join(r.value for r in allowed_roles)}"
            )

    return role_checker


def require_permission(permission: Permission):
    """FastAPI dependency: require the authenticated user to have a specific
    permission.

    Usage::

        @router.post("/ingest")
        async def ingest_file(
            _: None = Depends(require_permission(Permission.INGEST_DOCUMENT)),
        ):
            ...
    """

    def permission_checker(token: str = Depends(oauth2_scheme)) -> None:
        if token is None:
            raise AuthorizationException("Authentication required")
        user_role = get_role_from_token(token)
        user_permissions = ROLE_PERMISSIONS.get(user_role, set())
        if permission not in user_permissions:
            raise AuthorizationException(
                f"Requires permission: {permission.value}"
            )

    return permission_checker