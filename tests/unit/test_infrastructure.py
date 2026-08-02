"""Unit tests for infrastructure components — parsers, interpreters, projections."""

from __future__ import annotations

import pytest

from growth.application.dtos import RawPlan
from growth.application.ports.interpreter import InterpretationError
from growth.application.ports.parser import ParserError
from growth.domain.shared import DEFAULT_SPACE_ID, InternalId
from growth.infrastructure.interpreters.heuristic import HeuristicInterpreter
from growth.infrastructure.parsers.yaml_parser import YamlParser

# ============================================================================
# YamlParser
# ============================================================================


class TestYamlParser:
    def test_supports_yaml_content_types(self) -> None:
        parser = YamlParser()
        assert parser.supports("yaml")
        assert parser.supports("text/yaml")
        assert parser.supports("application/x-yaml")
        assert not parser.supports("json")

    def test_parse_valid_yaml_string(self) -> None:
        parser = YamlParser()
        source = """
project_name: "Test Plan"
subjects: []
standard_subtasks:
  - "Read"
"""
        result = parser.parse(source, "yaml")
        assert result.source_format == "yaml"
        assert result.payload["project_name"] == "Test Plan"
        assert len(result.payload["standard_subtasks"]) == 1
        assert result.source_ref is None

    def test_parse_valid_yaml_bytes(self) -> None:
        parser = YamlParser()
        source = b"project_name: Bytes Plan\nsubjects: []\n"
        result = parser.parse(source, "yaml")
        assert result.payload["project_name"] == "Bytes Plan"

    def test_accepts_empty_content_type(self) -> None:
        parser = YamlParser()
        result = parser.parse("project_name: OK\nsubjects: []\n")
        assert result.payload["project_name"] == "OK"

    def test_reject_invalid_yaml(self) -> None:
        parser = YamlParser()
        with pytest.raises(ParserError, match="Failed to parse YAML"):
            parser.parse("{invalid: [yaml: here}", "yaml")

    def test_reject_non_mapping_root(self) -> None:
        parser = YamlParser()
        with pytest.raises(ParserError, match="YAML root must be a mapping"):
            parser.parse("- list\n- not\n- mapping", "yaml")

    def test_parse_preserves_nested_structures(self) -> None:
        parser = YamlParser()
        source = """
project_name: "Nested"
subjects:
  - name: "Math"
    emoji: "📘"
    priority: 4
    chapters:
      - name: "Algebra"
        weak: true
"""
        result = parser.parse(source, "yaml")
        subjects = result.payload["subjects"]
        assert len(subjects) == 1
        assert subjects[0]["chapters"][0]["name"] == "Algebra"
        assert subjects[0]["chapters"][0]["weak"] is True

    def test_parse_empty_payload(self) -> None:
        parser = YamlParser()
        source = "{}"
        result = parser.parse(source, "yaml")
        assert result.payload == {}


# ============================================================================
# HeuristicInterpreter
# ============================================================================


class TestHeuristicInterpreter:
    def test_interpret_valid_plan(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(
            source_format="yaml",
            payload={
                "project_name": "Test Plan",
                "subjects": [],
                "standard_subtasks": [],
            },
        )
        result = interpreter.interpret(raw)
        assert result.id is not None
        assert isinstance(result.id, InternalId)
        assert result.space_id == DEFAULT_SPACE_ID

    def test_default_project_name_when_missing(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(source_format="yaml", payload={"subjects": []})
        result = interpreter.interpret(raw)
        assert result.project_name == "Untitled Plan"

    def test_reject_empty_project_name(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(source_format="yaml", payload={"project_name": "   "})
        with pytest.raises(InterpretationError, match="missing a valid 'project_name'"):
            interpreter.interpret(raw)

    def test_reject_non_string_project_name(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(source_format="yaml", payload={"project_name": 42})
        with pytest.raises(InterpretationError, match="missing a valid 'project_name'"):
            interpreter.interpret(raw)

    def test_custom_space_id(self) -> None:
        interpreter = HeuristicInterpreter()
        custom_space = InternalId()
        raw = RawPlan(
            source_format="yaml",
            payload={"project_name": "Custom Space Plan", "subjects": []},
        )
        result = interpreter.interpret(raw, space_id=custom_space)
        assert result.space_id == custom_space

    def test_attaches_raw_payload(self) -> None:
        interpreter = HeuristicInterpreter()
        payload = {"project_name": "Attach Test", "subjects": [], "extra_key": 123}
        raw = RawPlan(source_format="yaml", payload=payload)
        result = interpreter.interpret(raw)
        assert result.raw_payload == payload

    def test_attaches_project_name(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(source_format="yaml", payload={"project_name": "My Project"})
        result = interpreter.interpret(raw)
        assert result.project_name == "My Project"

    def test_complex_mvp_plan(self) -> None:
        interpreter = HeuristicInterpreter()
        raw = RawPlan(
            source_format="yaml",
            payload={
                "project_name": "Growth - Placement Exam",
                "subjects": [
                    {
                        "name": "Mathematics",
                        "emoji": "📘",
                        "priority": 4,
                        "chapters": [
                            {"name": "Sets", "weak": True},
                            {"name": "Polynomials"},
                        ],
                    }
                ],
                "standard_subtasks": ["Study", "Practice"],
                "extra_sections": ["Mistake Fix"],
            },
        )
        result = interpreter.interpret(raw)
        assert result.id is not None
        assert result.project_name == "Growth - Placement Exam"
