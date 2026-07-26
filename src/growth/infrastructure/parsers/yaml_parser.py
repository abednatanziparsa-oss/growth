"""YAML parser — extracts a RawPlan from YAML study plans.

Supports the YAML format established by the MVP (subjects, chapters, subtasks).
The format is format-neutral at the parser level — the interpreter lifts it
into a CanonicalPlan.

Content type: ``"yaml"``
"""

from __future__ import annotations

import yaml

from growth.application.dtos import RawPlan
from growth.application.ports.parser import ParserError

__all__ = ["YamlParser"]


class YamlParser:
    """Parse YAML study plan files into RawPlan IR."""

    def supports(self, content_type: str) -> bool:
        return content_type in ("yaml", "text/yaml", "application/x-yaml")

    def parse(self, source: bytes | str, content_type: str = "") -> RawPlan:  # noqa: ARG002
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        try:
            payload = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise ParserError(f"Failed to parse YAML: {exc}") from exc

        if not isinstance(payload, dict):
            raise ParserError("YAML root must be a mapping (dict)")

        return RawPlan(
            source_format="yaml",
            payload=payload,
            source_ref=None,
        )
