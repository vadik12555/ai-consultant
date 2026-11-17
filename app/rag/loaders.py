from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def load_text(path: Path) -> str:
    """Достаёт обычный текст из файла. Абзацы разделяются пустой строкой."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        return "\n\n".join(p.text for p in DocxDocument(str(path)).paragraphs if p.text.strip())
    raise ValueError(f"Неподдерживаемый формат: {path.name}")


def list_documents(docs_dir: Path) -> list[Path]:
    return sorted(
        p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
