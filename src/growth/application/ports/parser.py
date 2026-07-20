"""Parser port — the Extract stage of the ingestion pipeline.

A ``Parser`` reads bytes/text in a specific format and produces a
``RawPlan`` IR. The two-stage pipeline (Extract → Interpret) means
parsers know nothing about plans; interpreters (see ``interpreter.py``)
know nothing about formats. This is the architectural firewall that lets
PDF, Markdown, and natural language share downstream logic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from growth.application.dtos import RawPlan

__all__ = ["Parser", "ParserError"]


class ParserError(Exception):
    """Raised when a parser cannot extract content from its input.

    Distinct from ``ValidationError``: this means the bytes could not be
    parsed at all (e.g., a corrupt PDF), not that the parsed content was
    semantically invalid.
    """


@runtime_checkable
class Parser(Protocol):
    """Extract a ``RawPlan`` from raw input.

    Implementations: ``YamlParser``, ``MarkdownParser``, ``PdfParser``,
    etc. Each declares the content types it supports via ``supports``.
    """

    def supports(self, content_type: str) -> bool:
        """Return ``True`` if this parser handles the given content type.

        Content types are MIME-ish identifiers: ``"yaml"``, ``"markdown"``,
        ``"json"``, ``"pdf"``, ``"image"``, ``"text"``. The ParserRegistry
        (v0.4) queries each registered parser to find a match.
        """
        ...

    def parse(self, source: bytes | str, content_type: str) -> RawPlan:
        """Parse ``source`` into a ``RawPlan`` IR.

        Args:
            source: Raw bytes (binary formats) or text (text formats).
            content_type: The format hint (must satisfy ``supports``).

        Returns:
            A ``RawPlan`` ready for an interpreter.

        Raises:
            ParserError: If the input cannot be parsed.
        """
        ...
