import hashlib
from dataclasses import dataclass
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


def _split_text_recursively(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """Pure-Python recursive text splitter avoiding heavy NLP/torch dependencies."""
    if not text:
        return []

    if separators is None:
        separators = ["\n\n", "\n", " ", ""]

    separator = separators[-1]
    new_separators: List[str] = []
    for i, sep in enumerate(separators):
        if sep == "":
            separator = ""
            break
        if sep in text:
            separator = sep
            new_separators = separators[i + 1:]
            break

    splits = text.split(separator) if separator else list(text)

    chunks: List[str] = []
    current_doc: List[str] = []
    total = 0

    for s in splits:
        if not s:
            continue
        s_len = len(s)
        if s_len > chunk_size and new_separators:
            if current_doc:
                doc_str = separator.join(current_doc).strip()
                if doc_str:
                    chunks.append(doc_str)
                current_doc = []
                total = 0
            sub_chunks = _split_text_recursively(s, chunk_size, chunk_overlap, new_separators)
            chunks.extend(sub_chunks)
            continue

        sep_len = len(separator) if current_doc else 0
        if total + s_len + sep_len > chunk_size:
            if current_doc:
                doc_str = separator.join(current_doc).strip()
                if doc_str:
                    chunks.append(doc_str)
                # Slide window to respect overlap: keep last characters up to chunk_overlap
                # Recompute total accurately by re-joining instead of incremental subtraction
                while current_doc and total > chunk_overlap:
                    current_doc.pop(0)
                    total = len(separator.join(current_doc)) if current_doc else 0
                # If still over overlap due to large chunk, clear
                if total > chunk_overlap:
                    current_doc = []
                    total = 0
            current_doc.append(s)
            total = len(separator.join(current_doc)) if current_doc else s_len
        else:
            current_doc.append(s)
            total += s_len + sep_len

    if current_doc:
        doc_str = separator.join(current_doc).strip()
        if doc_str:
            chunks.append(doc_str)

    return chunks


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
        # Guard: overlap must be smaller than chunk_size
        if self.chunk_overlap >= self.chunk_size:
            self.chunk_overlap = max(0, self.chunk_size // 5)
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be >=1")

    def split_text(self, text: str) -> List[Chunk]:
        """Split text into chunks with deterministic content-addressed IDs.

        Args:
            text: The raw document text to split.

        Returns:
            A list of ``Chunk`` objects, each containing a SHA-256-based
            ``chunk_id`` and the chunk ``text``.
        """
        raw_chunks = _split_text_recursively(
            text=text,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return [
            Chunk(
                chunk_id=hashlib.sha256(c.encode("utf-8")).hexdigest()[:48],
                text=c,
            )
            for c in raw_chunks
        ]