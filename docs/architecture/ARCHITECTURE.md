# Growth OS Architecture

## Overview

Growth OS follows **hexagonal (ports & adapters)** architecture with six rings.

```
             ┌─────────────┐
             │ presentation │  ← CLI (Typer), future TUI/desktop
             └──────┬──────┘
                    │ depends on
             ┌──────▼──────┐
             │ application  │  ← use cases, ports (Protocols), DTOs
             └──────┬──────┘
                    │ depends on
             ┌──────▼──────┐
             │   domain     │  ← pure model, no I/O, no framework deps
             └─────────────┘

             ┌──────────────┐
             │infrastructure│  ← adapters: config, parsers, providers, storage
             └──────┬───────┘
                    │ wired by
             ┌──────▼───────┐
             │    kernel    │  ← composition root, manual DI container
             └──────┬───────┘
                    │ exposes
             ┌──────▼───────┐
             │ presentation │
             └──────────────┘
```

## Ring Responsibilities

### Domain (`growth.domain`)
Pure business logic. No I/O, no framework dependencies, no imports outside
the standard library. Bootstrap scope: `InternalId`, `SpaceId`, domain error
hierarchy. Aggregate roots (Workspace, Project, Goal, Milestone, Task) land
in v0.1.

### Application (`growth.application`)
The hexagon's seam. Defines **ports** (interfaces that adapters implement)
and **use cases** (orchestration logic). Depends only on domain.
Bootstrap scope: all ports defined as Protocols, DTO shells, app error hierarchy.

Ports defined:
- `Clock` — wall-clock time abstraction
- `AiServices`, `TaskGenerator`, `DifficultyEstimator` — AI capabilities (off by default)
- `DecisionEngine` — advisory recommendation engine
- `WorkflowEngine` — declarative, cancelable automation
- `EventDispatcher` — in-process pub/sub
- `Parser` + `Interpreter` — two-stage ingestion pipeline
- `Projection` — pure canonical-to-provider transformation
- `ProviderAdapter` — external API integration
- `Repository[T]` — generic persistence port

### Infrastructure (`growth.infrastructure`)
Adapter implementations. Depends on application ports. Current implementations:
- `config/` — Pydantic Settings (GROWTH_ env prefix)
- `logging/` — structlog (console + optional file)
- `events/` — SyncEventDispatcher (in-process, failure-isolated)
- `noop/` — Noop implementations of all optional ports

### Presentation (`growth.presentation`)
User-facing surfaces. Currently: CLI via Typer. Future: TUI (Textual),
desktop (PySide6). May only call application use cases and kernel — never
infrastructure directly.

### Kernel (`growth.kernel`)
Composition root. `build_app()` → `Container.from_settings()` wires all
adapters into ports. This is the **only** place concrete adapter classes
are constructed.

### Plugins (`growth.plugins`)
Extension contract. Currently: `Plugin` protocol only (YAGNI). Registry,
discovery, and lifecycle management deferred until at least two real plugins
exist.

## Dependency Enforcement

import-linter contracts (checked in CI) enforce:
1. Domain imports nothing outside domain
2. Application imports only domain
3. Presentation imports only application + kernel (not infrastructure directly)

## Design Rules

- All ports are `Protocol` (PEP 544), `@runtime_checkable`
- All optional ports have Noop implementations
- AI/Decision/Workflow engines are advisory only — never mutate state directly
- Timestamps are UTC; rendering to local timezone at projection boundaries only
- DI is manual (no framework) — explicit over implicit
