# Development Setup

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Git

## First-Time Setup

```bash
# Clone and enter
git clone https://github.com/abednatanziparsa-oss/growth
cd growth

# Install dependencies + dev tooling
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Verify the vertical slice works
uv run growth --version
```

Expected output: `growth-os 0.1.0.dev0`

## Day-to-Day Commands

All via `make` (or directly with `uv run`):

```bash
make dev         # sync dependencies
make test        # full test suite
make unit        # unit tests only
make lint        # ruff check
make format      # ruff format + fix
make typecheck   # mypy strict
make archs       # import-linter contracts
make ci          # everything CI runs
```

## Project Structure

```
Growth/
├── src/growth/          # application source
│   ├── domain/          #   pure model (no I/O)
│   ├── application/     #   use cases + ports (Protocols)
│   ├── infrastructure/  #   adapters (config, logging, noop, ...)
│   ├── presentation/    #   CLI (Typer)
│   ├── kernel/          #   composition root (DI)
│   └── plugins/         #   extension contract
├── tests/               # test suite
│   ├── unit/            #   isolated module tests
│   ├── integration/     #   multi-module / I/O tests
│   └── contract/        #   port implementation conformance
├── docs/                # documentation
│   ├── adr/             #   architecture decision records
│   ├── architecture/    #   architecture overview
│   └── runbooks/        #   how-to guides
├── archive/v0-mvp/      # original MVP (frozen, reference only)
├── pyproject.toml       # single source of truth for all tooling
├── Makefile             # developer task runner
└── .github/workflows/   # CI pipeline
```

## Running Tests

```bash
# All tests
uv run pytest

# Unit only (no I/O, fast)
uv run pytest tests/unit -m unit

# With coverage
uv run pytest --cov --cov-report=term-missing

# Property-based (hypothesis)
uv run pytest -k "hypothesis"  # when hypothesis tests land
```

Test markers: `unit`, `integration`, `contract`.

## Architecture Enforcement

Import direction is checked at pre-commit and CI:

```bash
uv run lint-imports
```

Three contracts:
1. Domain has no outbound dependencies
2. Application depends only on domain
3. Presentation depends only on application + kernel

See `docs/adr/0001-hexagonal-architecture.md` for rationale.
