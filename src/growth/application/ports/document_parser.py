"""Document parsing port — extract text from local files (v0.6).

The knowledge substrate (v0.4) stores attachments by reference only.
v0.6 adds the ability to *read* documents (PDFs first) so their text
becomes searchable and AI-assistable (summaries, plan lifting).

Convention: implementations raise ``DocumentParseError`` for any
failure (missing file, corrupt or encrypted input, unsupported
format). Callers treat this as a signal to skip content extraction —
attachment metadata is still stored; only the text enrichment is lost.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = ["DocumentParseError", "DocumentParser", "ExtractedDocument"]


class DocumentParseError(Exception):
    """Raised when a document cannot be parsed."""


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """Text content lifted from a document file."""

    title: str
    """Human-readable title (usually the file name)."""

    text: str
    """Full extracted text; pages joined with blank lines."""

    page_count: int
    """Number of pages in the source document."""

    format: str
    """Source format, e.g. ``"pdf"``."""


@runtime_checkable
class DocumentParser(Protocol):
    """Parse a document file into plain text."""

    def extract(self, source: Path) -> ExtractedDocument:
        """Extract text from ``source``.

        Args:
            source: Path to the document on disk.

        Returns:
            The extracted text with page count and title.

        Raises:
            DocumentParseError: If the file is missing, unreadable,
                encrypted, corrupt, or in an unsupported format.
        """
        ...
