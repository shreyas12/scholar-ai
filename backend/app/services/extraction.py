"""Text extraction (SA-021, simple v0).

Extracts plain text from the supported formats. This is the *simple* extractor
that unblocks chat; the full structure-preserving pipeline (Stage 1, SA-040)
replaces it in Phase 3.

Returns a list of "segments", each a ``{"page": int | None, "text": str}``. PDFs
yield one segment per page (so chunks can carry page numbers); other formats yield
a single page-less segment.
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt", ".docx"}


class UnsupportedFormat(Exception):
    pass


def extract(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext in {".md", ".markdown", ".txt"}:
        return [{"page": None, "text": path.read_text(encoding="utf-8", errors="replace")}]
    raise UnsupportedFormat(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    segments: list[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            segments.append({"page": i, "text": text})
    return segments


def _extract_docx(path: Path) -> list[dict]:
    import docx

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [{"page": None, "text": text}]
