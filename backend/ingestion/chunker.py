import hashlib
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Optional
from backend.core.config import settings


@dataclass(slots=True)
class Chunk:
    """A single document chunk with a deterministic content-addressed ID.

    The ``chunk_id`` is a SHA-256 hash of the text content, truncated to 48
    hex characters. This makes chunk IDs:
    - **Deterministic**: Same text always produces the same ID.
    - **Content-addressed**: The ID is derived purely from the chunk text.
    - **Idempotent**: Re-ingesting the same content yields the same ID,
      enabling upsert semantics downstream.
    """

    chunk_id: str
    text: str


class Chunker:
    """Splits documents into chunks with deterministic, content-addressed IDs.

    Usage::

        chunker = Chunker()
        chunks: List[Chunk] = chunker.split_text("long document text...")
        for chunk in chunks:
            print(chunk.chunk_id, chunk.text[:50])
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def split_text(self, text: str) -> List[Chunk]:
        """Split text into chunks with deterministic content-addressed IDs.

        Args:
            text: The raw document text to split.

        Returns:
            A list of ``Chunk`` objects, each containing a SHA-256-based
            ``chunk_id`` and the chunk ``text``.
        """
        raw_chunks = self.splitter.split_text(text)
        return [
            Chunk(
                chunk_id=hashlib.sha256(c.encode("utf-8")).hexdigest()[:48],
                text=c,
            )
            for c in raw_chunks
        ]