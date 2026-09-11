import hashlib
import re
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


def _split_code_block_smartly(code_block: str, chunk_size: int) -> List[str]:
    """Bisect oversized code block line-by-line while injecting fences at split points."""
    lines = code_block.split("\n")
    header = lines[0] if lines else "```"
    if not header.startswith("```"):
        header = "```"
    
    # Body lines (excluding first line and last line ```)
    body_lines = lines[1:-1] if len(lines) >= 2 and lines[-1].strip() == "```" else lines[1:]

    slices: List[str] = []
    cur_lines: List[str] = []
    cur_overhead = len(header) + len("\n```") + 2  # newline overhead

    for line in body_lines:
        line_len = len(line) + 1
        if cur_lines and (cur_overhead + sum(len(l) + 1 for l in cur_lines) + line_len > chunk_size):
            slice_content = "\n".join(cur_lines)
            slices.append(f"{header}\n{slice_content}\n```")
            cur_lines = [line]
        else:
            cur_lines.append(line)

    if cur_lines:
        slice_content = "\n".join(cur_lines)
        slices.append(f"{header}\n{slice_content}\n```")

    return slices or [code_block]


def _split_markdown_aware(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split markdown text while preserving code block and JSON fence integrity."""
    if not text:
        return []
    
    if "```" not in text:
        return _split_text_recursively(text, chunk_size, chunk_overlap)

    pattern = re.compile(r'(```[\s\S]*?```)')
    parts = pattern.split(text)

    atomic_units: List[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("```") and part.endswith("```") and len(part) >= 6:
            if len(part) <= chunk_size:
                atomic_units.append(part)
            else:
                # Oversized code block -> smart line bisection with injected fences
                atomic_units.extend(_split_code_block_smartly(part, chunk_size))
        else:
            trimmed = part.strip()
            if not trimmed:
                continue
            if len(trimmed) <= chunk_size:
                atomic_units.append(trimmed)
            else:
                atomic_units.extend(_split_text_recursively(trimmed, chunk_size, chunk_overlap))

    # Pack atomic units into chunks
    packed_chunks: List[str] = []
    cur_pack: List[str] = []
    cur_pack_len = 0

    for unit in atomic_units:
        unit_len = len(unit)
        sep_len = 2 if cur_pack else 0
        if cur_pack and (cur_pack_len + sep_len + unit_len > chunk_size):
            packed_chunks.append("\n\n".join(cur_pack))
            cur_pack = [unit]
            cur_pack_len = unit_len
        else:
            cur_pack.append(unit)
            cur_pack_len += sep_len + unit_len

    if cur_pack:
        packed_chunks.append("\n\n".join(cur_pack))

    return packed_chunks


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
        raw_chunks = _split_markdown_aware(
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