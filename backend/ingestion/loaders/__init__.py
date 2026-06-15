import fitz  # PyMuPDF
import docx
import pytesseract
from PIL import Image
from abc import ABC, abstractmethod
from pathlib import Path

class BaseLoader(ABC):
    @abstractmethod
    def load(self, file_path: Path) -> str:
        """Load document content as text."""
        pass

class PDFLoader(BaseLoader):
    def load(self, file_path: Path) -> str:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text

class TextLoader(BaseLoader):
    def load(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

class DocxLoader(BaseLoader):
    def load(self, file_path: Path) -> str:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

class ImageLoader(BaseLoader):
    def load(self, file_path: Path) -> str:
        # Simple OCR using Tesseract
        try:
            image = Image.open(file_path)
            return pytesseract.image_to_string(image)
        except Exception as e:
            raise ValueError(f"OCR failed for image {file_path}: {str(e)}")

class DocumentLoader:
    def __init__(self):
        self.loaders = {
            ".pdf": PDFLoader(),
            ".txt": TextLoader(),
            ".docx": DocxLoader(),
            ".doc": DocxLoader(),
            ".png": ImageLoader(),
            ".jpg": ImageLoader(),
            ".jpeg": ImageLoader(),
        }

    def load_document(self, file_path: str) -> str:
        path = Path(file_path)
        extension = path.suffix.lower()
        loader = self.loaders.get(extension)
        if not loader:
            raise ValueError(f"Unsupported file extension: {extension}")
        return loader.load(path)
