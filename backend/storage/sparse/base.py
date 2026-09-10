"""SparseStore protocol — pluggable sparse retrieval backends."""

from __future__ import annotations

from typing import Protocol, List, Dict, Optional, runtime_checkable


@runtime_checkable
class SparseStore(Protocol):
    """Protocol for sparse retrieval stores.

    Tenant isolation is enforced at retrieval time via tenant_id.
    """

    def index(self, documents: List[str], metadata: Optional[List[Dict]] = None, tenant_id: Optional[str] = None) -> None:
        ...

    def retrieve(self, query: str, k: int = 5, tenant_id: Optional[str] = None) -> List[Dict]:
        ...

    def delete_document(self, document_id: str, tenant_id: Optional[str] = None) -> None:
        ...

    def reset(self) -> None:
        ...

    def heartbeat(self) -> bool:
        ...

    def count(self, tenant_id: Optional[str] = None) -> int:
        ...
