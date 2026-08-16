"""pypdf-based document parser (v0.6).

The first ``DocumentParser`` implementation: PDF text extraction via
pypdf. Deliberately narrow — pages to text, joined with blank lines —
and deterministic: no OCR, no layout inference, no network.

Failure mapping: every pypdf failure mode (missing file, corrupt PDF,
encrypted PDF, unreadable page) becomes ``DocumentParseError`` so
callers can degrade gracefully (store the attachment anyway, skip the
text enrichment).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from growth.application.ports.document_parser import (
    DocumentParseError,
    ExtractedDocument,
)

__all__ = ["PypdfParser"]

#: Exceptions pypdf can raise while opening or walking pages of a
#: malformed/truncated/odd PDF. Mapped to ``DocumentParseError``.
_OPEN_FAILURES: tuple[type[Exception], ...] = (PdfReadError, OSError, ValueError)
_PAGE_FAILURES: tuple[type[Exception], ...] = (PdfReadError, ValueError, KeyError)


class PypdfParser:
    """Extract text from PDF files using pypdf."""

    def extract(self, source: Path) -> ExtractedDocument:
        """Extract text from ``source``.

        Raises:
            DocumentParseError: If the file cannot be opened, is
                encrypted (no password support at bootstrap), or any
                page fails to parse.
        """
        try:
            reader = PdfReader(str(source))
        except _OPEN_FAILURES as exc:
            raise DocumentParseError(f"cannot open {source.name}: {exc}") from exc

        if reader.is_encrypted:
            raise DocumentParseError(
                f"{source.name} is encrypted; password-protected PDFs "
                "are not supported yet"
            )

        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except _PAGE_FAILURES as exc:
                raise DocumentParseError(
                    f"cannot extract text from {source.name}: {exc}"
                ) from exc

        text = "\n\n".join(p.strip() for p in pages if p.strip())
        return ExtractedDocument(
            title=source.name,
            text=text,
            page_count=len(reader.pages),
            format="pdf",
        )
