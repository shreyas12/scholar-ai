"""Structured extraction helpers (SA-040) + hierarchical sectioning (SA-042).

Turns raw text into typed *blocks* (heading / paragraph / list) carrying a level
and page, then groups them into *sections* under their heading path. A section like
"Vector Search › ANN › HNSW" stays together instead of being split arbitrarily.

Block:   {"type": "heading"|"paragraph"|"list", "level": int, "text": str, "page": int|None}
Section: {"heading_path": [str, ...], "page": int|None, "text": str}
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^([-*+]|\d+[.)])\s+(.*)$")


def _para(text: str, page: int | None) -> dict:
    return {"type": "paragraph", "level": 0, "text": text.strip(), "page": page}


def parse_markdown(text: str, page: int | None = None) -> list[dict]:
    blocks: list[dict] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            joined = " ".join(buf).strip()
            if joined:
                blocks.append(_para(joined, page))
            buf.clear()

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush()
            continue
        h = _HEADING_RE.match(line)
        if h:
            flush()
            blocks.append(
                {"type": "heading", "level": len(h.group(1)), "text": h.group(2).strip(), "page": page}
            )
            continue
        lst = _LIST_RE.match(line)
        if lst:
            flush()
            blocks.append({"type": "list", "level": 0, "text": lst.group(2).strip(), "page": page})
            continue
        buf.append(line)
    flush()
    return blocks


def _looks_like_heading(lines: list[str], joined: str) -> bool:
    return (
        len(lines) == 1
        and len(joined) <= 80
        and len(joined.split()) <= 12
        and joined[-1] not in ".?!:;,"
    )


def parse_plain(text: str, page: int | None = None) -> list[dict]:
    """Plain-text/PDF-page parsing: paragraphs on blank lines, heuristic headings.

    Joining wrapped lines within a paragraph also repairs simple line-wrapping and
    hyphenation (SA-041 overlaps here).
    """
    blocks: list[dict] = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue
        # repair hyphenated line breaks before joining ("exam-\nple" -> "example")
        merged: list[str] = []
        for ln in lines:
            if merged and merged[-1].endswith("-"):
                merged[-1] = merged[-1][:-1] + ln
            else:
                merged.append(ln)
        joined = " ".join(merged).strip()
        if _looks_like_heading(merged, joined):
            blocks.append({"type": "heading", "level": 1, "text": joined, "page": page})
        else:
            blocks.append(_para(joined, page))
    return blocks


def build_sections(blocks: list[dict]) -> list[dict]:
    """Group blocks into sections under their heading path (SA-042)."""
    sections: list[dict] = []
    stack: list[tuple[int, str]] = []  # (heading level, text)
    body: list[str] = []
    body_page: int | None = None

    def flush() -> None:
        nonlocal body, body_page
        text = " ".join(body).strip()
        if text:
            sections.append(
                {"heading_path": [h for _, h in stack], "page": body_page, "text": text}
            )
        body = []
        body_page = None

    for b in blocks:
        if b["type"] == "heading":
            flush()
            while stack and stack[-1][0] >= b["level"]:
                stack.pop()
            stack.append((b["level"], b["text"]))
        else:
            if not body:
                body_page = b["page"]
            body.append(b["text"])
    flush()
    return sections
