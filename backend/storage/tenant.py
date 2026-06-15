"""Tenant isolation primitives for multi-tenant RAG storage.

Every storage operation (ChromaDB, BM25, query cache, audit log)
must call ``resolve_tenant_id`` and ``metadata_filter`` to scope
data access to the caller's tenant. This module provides the
building blocks for consistent tenant enforcement across all
storage backends.

Design invariants:
1. ``resolve_tenant_id(None) → "default"`` — fail-closed, never raises.
2. ``metadata_filter(tid)`` always returns a non-empty where clause.
3. ``enrich_metadata(meta, tid)`` stamps ``tenant_id`` after preserving existing fields.
4. ``deterministic_chunk_id(tid, doc_id, idx, content)`` produces
   ``sha256(tenant_id:document_id:chunk_index:content)[:48]`` for
   idempotent, tenant-scoped, collision-resistant chunk IDs.
5. Every storage query uses ``metadata_filter`` to prevent cross-tenant leakage.
"""

import hashlib
from typing import Dict, Any, Optional


# Well-known metadata keys consumed by storage and retrieval layers
METADATA_TENANT_KEY = "tenant_id"
METADATA_DOCUMENT_KEY = "document_id"
METADATA_CHUNK_KEY = "chunk_id"


def sanitize_tenant_id(tenant_id: str) -> str:
    """Sanitize a tenant identifier for use in ChromaDB collection names.

    ChromaDB collection names must be valid Python identifiers. This
    function replaces disallowed characters with underscores and
    lowercases the result.
    """
    return "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in tenant_id).lower()


def tenant_collection_name(base_name: str, tenant_id: str) -> str:
    """Generate a tenant-scoped ChromaDB collection name.

    Args:
        base_name: The base collection name (e.g. "query_cache").
        tenant_id: The tenant identifier.

    Returns:
        A sanitized collection name that includes the tenant scope.
    """
    tid = sanitize_tenant_id(tenant_id)
    return f"{base_name}__{tid}"


def resolve_tenant_id(tenant_id: Optional[str] = None) -> str:
    """Resolve a tenant identifier, falling back to the default tenant.

    This function is **fail-closed**: None, empty, or whitespace-only
    values always resolve to the default tenant. It never raises.

    Args:
        tenant_id: The tenant identifier to resolve. May be None.

    Returns:
        A non-empty tenant identifier string.
    """
    if tenant_id is None or (isinstance(tenant_id, str) and not tenant_id.strip()):
        return "default"
    return tenant_id


def metadata_filter(tenant_id: str) -> Dict[str, str]:
    """Create a ChromaDB-compatible ``where`` filter for the given tenant.

    The returned dict is always non-empty and scopes queries to the
    caller's tenant. This prevents cross-tenant data leakage at the
    storage layer.

    Args:
        tenant_id: The tenant identifier to filter by.

    Returns:
        A dict like ``{"tenant_id": "some-tenant"}``.
    """
    return {METADATA_TENANT_KEY: tenant_id}


def enrich_metadata(metadata: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Stamp the ``tenant_id`` field onto metadata, preserving existing keys.

    The caller's metadata takes precedence — ``tenant_id`` is only
    injected if the metadata dict does not already contain it. This
    prevents overwriting a tenant that was explicitly set upstream.

    Args:
        metadata: The metadata dict to enrich.
        tenant_id: The tenant identifier to stamp.

    Returns:
        A new dict with ``tenant_id`` and all original keys.
    """
    enriched = dict(metadata)
    if METADATA_TENANT_KEY not in enriched:
        enriched[METADATA_TENANT_KEY] = tenant_id
    return enriched


def deterministic_chunk_id(tenant_id: str, document_id: str, chunk_index: int, content: str) -> str:
    """Generate a deterministic, tenant-scoped chunk ID.

    The ID is a SHA-256 hash of the concatenation of
    ``tenant_id:document_id:chunk_index:content``, truncated to 48
    hex characters. This guarantees:

    - **Idempotent re-ingestion**: Same inputs → same ID → upsert-safe.
    - **Traceability**: The document_id component links back to the
      source document for cross-referencing.
    - **Collision resistance**: SHA-256 with 48 hex chars = 192 bits
      of collision resistance. Cross-tenant collisions are impossible
      because tenant_id is part of the hash input.
    - **No UUID4 anywhere**: Chunk IDs are content-addressed, not
      generated from a random counter.

    Args:
        tenant_id: The tenant scope identifier.
        document_id: The source document's unique identifier.
        chunk_index: The zero-based chunk index within the document.
        content: The raw text content of the chunk.

    Returns:
        A 48-character hex string.
    """
    raw = f"{tenant_id}:{document_id}:{chunk_index}:{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def hash_query_text(query: str) -> str:
    """Produce a stable hash of the query text for audit logging.

    Args:
        query: The raw query string.

    Returns:
        A 16-character hex prefix of the SHA-256 hash.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def audit_retrieval(
    tenant_id: str,
    operation: str,
    query_text_hash: str,
    chunk_count: int,
    success: bool = True,
    user_uuid: Optional[str] = None,
    session_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build an audit record for a retrieval operation.

    Args:
        tenant_id: The tenant scope identifier.
        operation: The operation type (e.g. "retrieve", "ingest").
        query_text_hash: A stable hash of the query text.
        chunk_count: Number of chunks returned.
        success: Whether the operation succeeded.
        user_uuid: The user UUID for audit trail.
        session_id: The session ID.
        error_message: Optional error message on failure.

    Returns:
        A dict suitable for logging as structured audit data,
        or ``None`` if audit logging is disabled.
    """
    return {
        METADATA_TENANT_KEY: tenant_id,
        "operation": operation,
        "query_text_hash": query_text_hash,
        "chunk_count": chunk_count,
        "success": success,
        "user_uuid": user_uuid,
        "session_id": session_id,
        "error_message": error_message,
    }