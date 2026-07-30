# Luo Handoff — 2026-07-30

**Agent:** Luo 🦞
**Project:** Growth OS
**Human:** Parsa
**Session span:** 2026-07-21 → 2026-07-30

---

## What We Built

Growth OS — a personal growth operating system with hexagonal architecture, Python 3.11+, uv, ruff, mypy strict, import-linter, and Typer CLI.

### Current Version: v0.1

Fully functional: parse YAML study plans → create domain aggregates → persist to SQLite → display via CLI.

---

## Repository State

| Thing | Value |
|---|---|
| Path | `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth` |
| Branch | `main` |
| Remote | `https://github.com/abednatanziparsa-oss/placement-exam-todoist` |
| Commits | 13, all clean |
| Working tree | clean ✅ |
| Python | 3.11.15 |
| Package manager | uv |

> **⚠️ Git push failed** — credential store (`wincredman`) can't authenticate in non-interactive context. Parsa needs to push manually (SSH or PAT).

### CI Status (local)

```
ruff check     ✅ All passed
ruff format    ✅ 58 files formatted
mypy strict   ✅ 50 files, zero issues
import-linter ✅ 3 contracts kept, 0 broken
pytest        ✅ 25 tests passed
```

---

## Architecture Map

```
src/growth/
├── domain/                    # Pure model — no I/O, no framework deps
│   ├── __init__.py            # Re-exports: InternalId, SpaceId, DomainError, aggregates
│   ├── shared.py              # InternalId (UUID wrapper), SpaceId, DEFAULT_SPACE_ID
│   ├── errors.py              # DomainError, InvalidPriorityError, InvalidTaskTreeError
│   └── planning/              # v0.1 aggregates
│       ├── __init__.py        # Workspace, Project, Goal, Milestone, Task, Priority
│       └── events/            # Domain events (ProjectCreated, TaskCreated, TaskCompleted…)
│
├── application/               # Use cases + ports — depends only on domain
│   ├── errors.py              # GrowthError → ApplicationError → ValidationError, SyncError…
│   ├── dtos.py                # RawPlan, CanonicalPlan, ProviderSnapshot, ChangeSet, DecisionArtifact
│   ├── plan_applier.py        # PlanApplier: YAML → Workspace → Project → Goals → Milestones → Tasks
│   └── ports/                 # All interfaces (Protocols)
│       ├── ai_services.py     # AiServices, TaskGenerator, DifficultyEstimator
│       ├── clock.py           # Clock (wall-clock abstraction)
│       ├── decision.py        # DecisionEngine (advisory-only)
│       ├── event_dispatcher.py# Event, EventHandler, EventDispatcher
│       ├── interpreter.py     # Interpreter (RawPlan → CanonicalPlan)
│       ├── parser.py          # Parser (bytes → RawPlan)
│       ├── projection.py      # Projection (CanonicalPlan → ProviderSnapshot)
│       ├── provider_adapter.py# ProviderAdapter (fetch_current, apply ChangeSet)
│       ├── repository.py      # Repository[T], EntityNotFoundError
│       └── workflow.py        # WorkflowEngine, WorkflowDefinition
│
├── infrastructure/            # Adapters — wires into ports via kernel
│   ├── config/
│   │   └── settings.py        # Pydantic Settings, GROWTH_ env prefix, Environment enum
│   ├── logging/
│   │   └── setup.py           # structlog (console + optional file), idempotent
│   ├── events/
│   │   └── sync_dispatcher.py # In-process pub/sub, failure-isolated
│   ├── noop/                  # Noop implementations of all optional ports
│   │   ├── ai.py              # NoopAiServices, NoopTaskGenerator, NoopDifficultyEstimator
│   │   ├── clock.py           # SystemClock (real wall clock)
│   │   ├── decision.py        # NoopDecisionEngine
│   │   └── workflow.py        # NoopWorkflowEngine
│   ├── storage/               # SQLite repositories (v0.1)
│   │   └── planning_repos.py  # WorkspaceRepo, ProjectRepo, GoalRepo, MilestoneRepo, TaskRepo
│   ├── parsers/               # Format-specific parsers (v0.1)
│   │   └── yaml_parser.py     # YamlParser (yaml → RawPlan)
│   ├── interpreters/          # Interpreters (v0.1)
│   │   └── heuristic.py       # HeuristicInterpreter (RawPlan → CanonicalPlan)
│   ├── projections/           # Provider projections (v0.1)
│   │   └── todoist.py         # TodoistProjection
│   └── adapters/              # Provider adapters (v0.1)
│       └── todoist.py         # TodoistAdapter (dry-run only; real API in v0.2)
│
├── kernel/                    # Composition root — ONLY place that wires adapters
│   ├── bootstrap.py           # build_app() → App with repos + container
│   ├── container.py           # Container (manual DI dataclass)
│   └── __init__.py
│
├── plugins/                   # Extension contract
│   └── __init__.py            # Plugin protocol (registry/discovery deferred: YAGNI)
│
└── presentation/              # User-facing surfaces
    └── cli/
        └── app.py             # Typer CLI: growth plan apply/show/stats + --version
```

### Import-linter Contracts (3)

1. **Domain has no outbound dependencies** — KEPT
2. **Application depends only on domain** — KEPT
3. **Presentation depends on application + kernel (not infrastructure directly)** — KEPT (allow_indirect_imports=true)

---

## What's Done (vs Bootstrap Prompt)

| # | Task | Status |
|---|---|---|
| 1 | Error hierarchy fix | ✅ DomainError stays in domain; GrowthError in application |
| 2 | Kernel (settings, container, bootstrap) | ✅ Settings → Container → build_app → App |
| 3 | CLI entrypoint | ✅ growth plan apply/show/stats + --version/--help |
| 4 | Noop infrastructure | ✅ Full noop suite (AI, decision, workflow, clock, events) |
| 5 | Plugin protocol | ✅ Consistent with Container TYPE_CHECKING |
| 6 | Domain aggregates | ✅ v0.1: Workspace, Project, Goal, Milestone, Task, Priority |
| 7 | SQLite repos | ✅ File-based (~/.growth/growth.db), CRUD + list_by_parent |
| 8 | YAML parser + interpreter | ✅ YamlParser + HeuristicInterpreter |
| 9 | Todoist projection + adapter | ✅ Projection (canonical→provider), Adapter (dry-run) |
| 10 | PlanApplier use case | ✅ Full YAML→tree pipeline |
| 11 | Test suite | ✅ 25 tests (domain unit + planning unit + storage integration + smoke) |
| 12 | CI green | ✅ ruff + mypy + import-linter + pytest all pass |
| 13 | Documentation | ✅ README, TUTORIAL, CODE_STYLE, CONTRIBUTING, CHANGELOG, ROADMAP, 3 ADRs, ARCHITECTURE, dev runbook |

---

## Commands

```bash
# Development
make dev           # uv sync --all-extras
make ci            # ruff + mypy + import-linter + pytest
make test          # pytest only

# CLI (run from project root)
uv run growth --version        # → growth-os 0.1.0.dev0
uv run growth --help
uv run growth plan apply <file>.yaml
uv run growth plan show
uv run growth plan stats
```

---

## Key Design Decisions

1. **Hexagonal strict** — domain imports nothing external; application imports only domain; import-linter enforces.
2. **Manual DI** — no framework. Container is a plain @dataclass. Explicit over implicit.
3. **Noop defaults** — every optional port has a Noop. System runs offline by default. AI/decision/workflow are advisory-only.
4. **Single tool** — ruff replaces flake8 + isort + black. One pyproject.toml for everything.
5. **YAGNI** — Plugin registry, real adapters, workflow scheduling, and AI backends deferred until needed.
6. **File-based SQLite** — `~/.growth/growth.db`, created on first `build_app()` call.
7. **yaml import-untyped** — types-PyYAML not available in Parsa's environment; suppressed in mypy config with per-file disable_error_code.

---

## Known Issues

### Git push
- **Problem:** GitHub credential (`wincredman`) fails in non-interactive shell
- **Solution:** Parsa runs one of:
  ```powershell
  # Option A: SSH
  git remote set-url origin git@github.com:abednatanziparsa-oss/placement-exam-todoist.git
  git push origin main

  # Option B: PAT
  git remote set-url origin https://TOKEN@github.com/abednatanziparsa-oss/placement-exam-todoist.git
  git push origin main
  ```
  Or just push from GitHub Desktop / VS Code / terminal.

### Repo name
- Current remote name is `placement-exam-todoist` (from MVP era). Rename to `growth` in GitHub Settings for cleaner branding.

### yaml stubs
- `types-PyYAML` failed to install (network). mypy config suppresses `import-untyped` for yaml-importing files. CI on GitHub can install types-PyYAML.

---

## What Comes Next (v0.2 → v1.0)

| Phase | What | Dependencies |
|---|---|---|
| **v0.2** | Sync engine: three-way diff, IdentityMap, real Todoist API | todoist-api-python |
| **v0.3** | Markdown adapter, export | — |
| **v0.4** | Knowledge substrate: attachments, embeddings, search | — |
| **v0.5** | Reminders, scheduling, Google Calendar | — |
| **v0.6** | AI integration: Ollama/OpenAI/Anthropic, PDF parser | ollama, openai, anthropic |
| **v0.7** | DecisionEngine, WorkflowEngine (declarative, cancelable) | — |
| **v1.0** | Plugin marketplace, desktop app, GraphQL | — |

---

## For the Next Agent

1. Read `AGENTS.md` and `SOUL.md` first — they define workspace rules.
2. Never touch `archive/v0-mvp/` — it's frozen.
3. All ports are Protocols — implement new features as adapters, never modify domain.
4. Run `make ci` before committing. If it fails, fix it.
5. Phases are designed to be sequential — each builds on the previous.
6. Parsa's name is Parsa. Address him directly. He prefers English for code, Persian for conversation.
7. The project directory is `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth`.
8. Use `uv run` for all Python commands from the project root.
9. Git remote is origin, branch is main. 13 commits ahead of remote (needs push).

---

*Luo signed off 2026-07-30. Parsa, it's been great building this with you. 🦞*
