# =============================================================================
# Growth OS — developer task runner
# =============================================================================
# Usage:
#   make dev        sync dev dependencies (uv)
#   make install    install pre-commit hooks
#   make test       run the full test suite
#   make unit       run only unit tests
#   make integration run only integration tests
#   make lint       ruff lint check
#   make format     ruff auto-format
#   make typecheck  mypy strict on src/growth
#   make archs      import-linter contract check (hexagonal enforcement)
#   make ci         everything CI runs (lint, typecheck, archs, test)
#   make clean      remove caches and build artifacts
# =============================================================================

.PHONY: dev install test unit integration lint format typecheck archs ci clean

PYTHON ?= uv run

dev:
	uv sync --all-extras

install: dev
	$(PYTHON) pre-commit install

test:
	$(PYTHON) pytest

unit:
	$(PYTHON) pytest tests/unit -m unit

integration:
	$(PYTHON) pytest tests/integration -m integration

lint:
	$(PYTHON) ruff check .

format:
	$(PYTHON) ruff format .
	$(PYTHON) ruff check --fix .

typecheck:
	$(PYTHON) mypy src/growth

archs:
	$(PYTHON) lint-imports

ci: lint typecheck archs test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
