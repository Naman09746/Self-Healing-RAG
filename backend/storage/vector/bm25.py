from rank_bm25 import BM25Okapi
from typing import List, Dict, Optional
import numpy as np
from backend.core.logging import get_logger

logger = get_logger(__name__)


class BM25Error(Exception):
    """Raised when BM25 indexing or retrieval encounters a fatal error."""


class BM25Retriever:
    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.corpus: List[str] = []
        self.metadata: List[Dict] = []

    def index(self, documents: List[str], metadata: Optional[List[Dict]] = None) -> None:
        """Index a list of documents.

        Args:
            documents: List of document strings to index.
            metadata: Optional list of metadata dicts, one per document.
                      If provided, must have the same length as ``documents``.

        Raises:
            BM25Error: If documents list is empty or metadata length mismatches.
        """
        if not documents:
            raise BM25Error("Cannot index empty document list")

        if metadata is not None and len(metadata) != len(documents):
            raise BM25Error(
                f"Metadata length ({len(metadata)}) does not match "
                f"documents length ({len(documents)})"
            )

        try:
            self.corpus = documents
            self.metadata = metadata or [{} for _ in documents]
            tokenized_corpus = [doc.lower().split() for doc in documents]
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info("BM25 index rebuilt", document_count=len(documents))
        except Exception as e:
            logger.error("BM25 indexing failed", error=str(e))
            raise BM25Error(f"Failed to build BM25 index: {e}") from e

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """Retrieve top k documents for a query.

        Args:
            query: Search query string.
            k: Maximum number of results to return.

        Returns:
            List of result dicts with ``content``, ``metadata``, and ``score``.
            Returns an empty list if the index is empty or the query is blank.
        """
        if not self.bm25 or not self.corpus:
            logger.debug("BM25 retrieve called but index is empty")
            return []

        if not query or not query.strip():
            logger.debug("BM25 retrieve called with empty query")
            return []

        try:
            tokenized_query = query.lower().split()
            scores = self.bm25.get_scores(tokenized_query)
            top_n = np.argsort(scores)[::-1][:k]

            results = []
            for i in top_n:
                if scores[i] > 0:
                    results.append({
                        "content": self.corpus[i],
                        "metadata": self.metadata[i],
                        "score": float(scores[i]),
                    })
            return results
        except Exception as e:
            logger.error("BM25 retrieval failed", error=str(e), query=query)
            return []

    def reset(self) -> None:
        """Clear the index and release memory."""
        self.bm25 = None
        self.corpus = []
        self.metadata = []
        logger.info("BM25 index reset")


bm25_retriever = BM25Retriever()
