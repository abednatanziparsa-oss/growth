# ADR 0001: Hexagonal Architecture

**Status:** Accepted
**Date:** 2026-07-17

## Context

Growth OS must support multiple input formats (YAML, Markdown, PDF, natural language)
and multiple output providers (Todoist, Markdown export, Google Calendar, Obsidian).
The MVP tightly coupled YAML parsing, Todoist API calls, and domain logic — making
it impossible to add a second provider without duplicating code.

## Decision

Adopt hexagonal (ports & adapters) architecture with strict dependency direction:

```
domain ← application ← presentation
                ↖ kernel (composition root)
infrastructure → kernel
```

- **domain/** — pure model, no I/O, no framework deps
- **application/ports/** — interfaces (Protocols) that adapters implement
- **application/** — use cases + DTOs, depends only on domain
- **infrastructure/** — adapter implementations (config, logging, parsers, providers)
- **presentation/** — CLI (Typer), future TUI/desktop
- **kernel/** — composition root, manual DI container
- **plugins/** — extension contract

Dependency direction is enforced at CI time by import-linter contracts.

## Consequences

- Every new provider = one adapter + one projection (no core changes)
- Every new input format = one parser + one interpreter (no core changes)
- No framework lock-in: DI is manual, storage is behind a repository port
- Full testability: every port has a Noop/ fake implementation
