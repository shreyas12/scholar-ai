"""Backwards-compatibility shim.

The extraction logic now lives in the pluggable processor registry
(:mod:`app.knowledge.processors`). This module re-exports the same names so
existing imports (``UnsupportedFormat``, ``SUPPORTED_EXTENSIONS``, ``extract``)
keep working.
"""

from __future__ import annotations

from ..knowledge.processors import (  # noqa: F401
    UnsupportedFormat,
    extract,
    supported_extensions,
)

SUPPORTED_EXTENSIONS = supported_extensions()
