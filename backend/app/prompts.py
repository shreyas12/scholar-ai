"""Prompt versioning (SA-009 / PLAN §10).

Prompts are never hardcoded. They live as markdown files under ``prompts/`` named
``<name>_v<N>.md``. This loader resolves the latest (or a pinned) version and
returns a :class:`Prompt` that carries its ``version`` string, so every LLM call
can stamp *which* prompt produced a result. When grading/extraction prompts change
later, recorded events explain why scores moved.

Usage::

    p = load_prompt("grading")            # newest version
    text = p.render(question=q, answer=a) # {question}/{answer} placeholders
    record = {"prompt_version": p.version, ...}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import get_settings

_FILE_RE = re.compile(r"^(?P<name>.+)_v(?P<version>\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str  # e.g. "grading_v2"
    template: str

    def render(self, **kwargs: object) -> str:
        """Fill ``{placeholder}`` fields. Literal braces must be doubled."""
        return self.template.format(**kwargs)


def _prompts_dir() -> Path:
    return get_settings().prompts_dir


def _discover(name: str) -> dict[int, Path]:
    """Map version-number -> file for a given prompt name."""
    versions: dict[int, Path] = {}
    for path in _prompts_dir().glob(f"{name}_v*.md"):
        m = _FILE_RE.match(path.name)
        if m and m.group("name") == name:
            versions[int(m.group("version"))] = path
    return versions


@lru_cache
def load_prompt(name: str, version: int | None = None) -> Prompt:
    """Load a prompt by name. ``version=None`` selects the highest version.

    Raises ``FileNotFoundError`` if the name (or pinned version) is missing.
    """
    versions = _discover(name)
    if not versions:
        raise FileNotFoundError(
            f"No prompt files found for {name!r} in {_prompts_dir()}"
        )
    chosen = max(versions) if version is None else version
    if chosen not in versions:
        raise FileNotFoundError(f"Prompt {name!r} has no version {chosen}")
    text = versions[chosen].read_text(encoding="utf-8").strip()
    return Prompt(name=name, version=f"{name}_v{chosen}", template=text)


def list_prompts() -> dict[str, list[int]]:
    """All prompt names -> sorted available versions (for diagnostics)."""
    out: dict[str, list[int]] = {}
    for path in _prompts_dir().glob("*_v*.md"):
        m = _FILE_RE.match(path.name)
        if m:
            out.setdefault(m.group("name"), []).append(int(m.group("version")))
    return {k: sorted(v) for k, v in sorted(out.items())}
