# ADR 0003: Toolchain

**Status:** Accepted
**Date:** 2026-07-17

## Context

The bootstrap phase required choosing a Python toolchain: package manager, linter,
formatter, type checker, and architecture enforcement. Multiple options existed for
each role.

## Decision

| Tool | Choice | Rationale |
|---|---|---|
| Package manager | uv | Fast, single-file lock (uv.lock), PEP 621 native |
| Linter + formatter | ruff (single tool) | Replaces flake8 + isort + black; 10-100x faster |
| Type checker | mypy (strict mode) | Mature, strict on inner rings |
| Architecture enforcement | import-linter | Checks dependency direction in CI |
| Test runner | pytest + hypothesis | Standard; property-based for domain invariants |
| Pre-commit | Standard hooks + ruff + mypy + import-linter | Catches issues before push |

Single-source-of-truth: all tool config lives in `pyproject.toml`.

## Consequences

- One file (`pyproject.toml`) configures everything
- `make ci` mirrors GitHub Actions exactly
- 3 Python versions in CI matrix (3.11, 3.12, 3.13)
- Ruff's single-tool approach eliminates version conflicts between linters
