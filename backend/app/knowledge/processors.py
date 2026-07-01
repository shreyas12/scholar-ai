"""Pluggable document processors (SA-132).

A ``DocumentProcessor`` knows how to turn one file format into a list of text
*segments* (``{"page": int | None, "text": str}``). Processors register themselves
by extension, so new sources (Arxiv, HTML, YouTube transcripts…) can be added later
with **no changes to the pipeline** — just a new processor + ``register()``.

This is the Slice-A home for what used to live in ``services/extraction.py`` (now a
thin compatibility shim over this registry).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class UnsupportedFormat(Exception):
    pass


@runtime_checkable
class DocumentProcessor(Protocol):
    extensions: tuple[str, ...]

    def extract(self, path: Path) -> list[dict]: ...


_REGISTRY: dict[str, DocumentProcessor] = {}


def register(processor: DocumentProcessor) -> DocumentProcessor:
    for ext in processor.extensions:
        _REGISTRY[ext.lower()] = processor
    return processor


def get_processor(ext: str) -> DocumentProcessor:
    processor = _REGISTRY.get(ext.lower())
    if processor is None:
        raise UnsupportedFormat(f"Unsupported file type: {ext}")
    return processor


def supported_extensions() -> set[str]:
    return set(_REGISTRY.keys())


def extract(path: Path) -> list[dict]:
    return get_processor(path.suffix).extract(path)


# --- Built-in processors -----------------------------------------------------

class TextProcessor:
    extensions = (".txt", ".md", ".markdown")

    def extract(self, path: Path) -> list[dict]:
        return [{"page": None, "text": path.read_text(encoding="utf-8", errors="replace")}]


class PdfProcessor:
    extensions = (".pdf",)

    def extract(self, path: Path) -> list[dict]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        segments: list[dict] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                segments.append({"page": i, "text": text})
        return segments


class DocxProcessor:
    extensions = (".docx",)

    def extract(self, path: Path) -> list[dict]:
        import docx

        document = docx.Document(str(path))
        text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
        return [{"page": None, "text": text}]


register(TextProcessor())
register(PdfProcessor())
register(DocxProcessor())
