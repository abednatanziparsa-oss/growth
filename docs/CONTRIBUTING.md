# Contributing to Growth OS

## Architecture Principles

Growth OS follows hexagonal architecture with strict dependency direction.
Before contributing, read:
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- [ADR 0001](docs/adr/0001-hexagonal-architecture.md)
- [ADR 0002](docs/adr/0002-knowledge-centric-architecture.md)

Key rules:
- Domain code never imports from other rings
- Application code never imports infrastructure
- All optional ports have Noop implementations
- AI/Decision/Workflow engines are advisory only
- DI is manual (kernel/container.py)

## Development Workflow

1. Create a branch: `git checkout -b feat/short-description`
2. Make changes following [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
3. Run `make ci` locally — it must pass
4. Commit with conventional commit messages: `feat(...):`, `fix(...):`, `test(...):`, `chore(...):`, `docs(...):`
5. Push and open a PR

## Code Style

See `pyproject.toml` for complete tooling configuration.

- Ruff handles linting + formatting + import sorting (single tool)
- mypy strict on domain and application
- No commented-out code (ERA rule)
- Use pathlib, not os.path (PTH rule)
- DTOs are frozen dataclasses; domain entities may have behaviour

## Testing

- Write tests next to the code they exercise
- Mark with `unit`, `integration`, or `contract`
- Use hypothesis for property-based domain invariant tests
- Noop implementations are not tested (they are testing infrastructure)
- Prefer testability: inject ports, don't call datetime.now() directly

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): short description
fix(scope): short description
test(scope): short description
docs(scope): short description
chore(scope): short description
```

## Questions?

Open an issue or discussion on GitHub.
