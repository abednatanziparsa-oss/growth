# Code Style

Growth OS follows a strict-but-pragmatic style enforced by tooling.

## Single Source of Truth

All tooling configuration lives in `pyproject.toml`. No `.flake8`, `.isort.cfg`, `setup.cfg`, or `tox.ini`.

## Ruff (linting + formatting + import sorting)

Ruff replaces flake8, isort, and black as a single tool.

### Rule families

| Family | Purpose |
|---|---|
| E, W | pycodestyle errors and warnings |
| F | Pyflakes (unused imports, undefined names) |
| I | isort (import sorting) |
| N | pep8-naming conventions |
| UP | pyupgrade (modern Python syntax) |
| B | flake8-bugbear (likely bugs) |
| C4 | flake8-comprehensions |
| SIM | flake8-simplify |
| RET | flake8-return |
| ARG | flake8-unused-arguments |
| PTH | flake8-use-pathlib (prefer pathlib) |
| ERA | eradicate (no commented-out code) |
| PL | Pylint subset |
| RUF | Ruff-specific rules |

### Pragmatic exclusions

| Rule | Reason |
|---|---|
| E501 | Line length handled by formatter, not linter |
| PLR0913 | Too-many-arguments; DI sometimes requires several params |
| PLR2004 | Magic-value-in-comparison; noisy in tests |
| B008 | Function-call-in-default-argument; Typer uses this idiom |
| RET505 | Unnecessary-else-after-return; readability preference |
| SIM108 | If-else-to-expression; ternaries aren't always clearer |
| PLC0105 | TypeVar naming; E is clearer than E_co in Protocols |

### Per-file ignores

- `tests/**` — S101 (asserts), ARG001/ARG002 (fixtures), PLR2004 (magic values)
- `src/growth/infrastructure/noop/**` — ARG001/ARG002 (stub signatures)

## MyPy (static typing)

- Strict mode on inner rings (domain, application)
- Relaxed on tests and noop stubs
- All public functions require type annotations
- No implicit re-exports (`no_implicit_reexport = true`)
- yaml has `import-untyped` suppressed (types-PyYAML optional)

## Conventions

### Imports

- `from __future__ import annotations` in every module
- Standard library → third-party → first-party (`growth.*`)
- First-party group: `known-first-party = ["growth"]`
- Single-line imports combined where they fit (`combine-as-imports = true`)

### Data classes

- Use `@dataclass(frozen=True, slots=True)` for value objects and DTOs
- Use `@dataclass(kw_only=True, slots=True)` for entities with many fields
- DTOs are always frozen; domain entities may be mutable
- Never put behaviour in DTOs

### Protocols (ports)

- All ports are `Protocol` (PEP 544) with `@runtime_checkable`
- Implementations live in `growth.infrastructure`
- Bootstrap ships Noop implementations for all optional ports
- Use cases accept ports by constructor injection; never import infrastructure directly

### Error hierarchy

- `GrowthError` (application.errors) — root of all Growth errors
- `DomainError` (domain.errors) — domain invariant violations
- `ApplicationError` (application.errors) — use-case-level failures
  - `ValidationError`, `PortError`, `SyncError`, `ConflictDetectedError`, `ProviderUnavailableError`
- `EntityNotFoundError` (application.ports.repository) — persistence lookup failures

### Docstrings

- Google-style with Args/Returns/Raises sections
- First line: one-line summary
- All public modules, classes, and functions require docstrings
- Use backtick-quoted references to types (``InternalId``)

### File conventions

- All files end with a trailing newline (enforced by pre-commit)
- UTF-8 encoding, LF line endings (`line-ending = "lf"`)
- Double quotes for strings (`quote-style = "double"`)

## Tools Quick Reference

```bash
make lint        # ruff check
make format      # ruff format + ruff check --fix
make typecheck   # mypy src/growth
make archs       # import-linter contract check
make ci          # lint + typecheck + archs + test
make test        # full test suite
make unit        # unit tests only
```
