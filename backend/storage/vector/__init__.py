"""Vector store package — pluggable backends."""

from backend.storage.vector.base import VectorStore  # noqa: F401
from backend.storage.vector.factory import get_vector_store  # noqa: F401
