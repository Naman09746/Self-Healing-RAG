from pathlib import Path
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


class DocumentLoader:
    """Production document loader supporting PDF (fitz), TXT, MD, JSON, and common formats."""

    def load_document(self, file_path: str) -> str:
        """Load and extract text from a file based on its extension."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        ext = path.suffix.lower()
        logger.info("Loading document", file_path=file_path, extension=ext)

        if ext == ".pdf":
            return self._load_pdf(path)
        elif ext in {".txt", ".md", ".markdown", ".rst"}:
            return self._load_text(path)
        elif ext == ".json":
            return self._load_json(path)
        else:
            # Attempt plain text read as fallback
            return self._load_text(path)

    def _load_pdf(self, path: Path) -> str:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text:
                    text_parts.append(text)
            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error("Failed to parse PDF with PyMuPDF", error=str(e), path=str(path))
            raise RuntimeError(f"Could not extract text from PDF {path}: {e}") from e

    def _load_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="replace")

    def _load_json(self, path: Path) -> str:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2)
        return str(data)
