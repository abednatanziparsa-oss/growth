# Changelog

All notable changes to Growth OS.

## [0.6.0] — 2026-08-19

### Added
- **LLMChat port** (`application/ports/llm.py`) + `LLMUnavailableError`
- **OpenAICompatibleChat** — httpx-based, non-streaming, Bearer auth; all failures map to `LLMUnavailableError`
- **AiInterpreter** — free-text → CanonicalPlan via prompt `growth-plan-json-v1`, heuristic fallback on LLM failure
- **CLI `growth plan ai-apply <text> [--apply]`** — dry-run default, shows DecisionArtifact (model, reasoning)
- **DocumentParser port + PypdfParser** (pypdf) — encrypted/corrupt → `DocumentParseError`
- **AiDocumentSummarizer** — LLM Markdown summary via prompt `growth-doc-summary-v1`
- **`knowledge attach <pdf>`** auto-extracts searchable text; `knowledge extract <file> [--summarize]`
- **Settings** `GROWTH_LLM_BASE_URL/MODEL/API_KEY/TIMEOUT` + `GROWTH_AI_ENABLED` gate (offline-first default)
- **Live provider verification (Iran)**: 9Router + Kiro (`kr/deepseek-3.2`) works; GitHub Models retired, OpenRouter geo-blocked, Gemini standard keys deprecated

## [0.5.0] — 2026-08-13

### Added
- Reminders + scheduling: `Reminder` aggregate, `RecurrenceRule` (daily/weekly/monthly), `Scheduler.sweep()`, CLI `reminder add/list/due/fire/sweep`
- Google Calendar: `GoogleCalendarAdapter`, idempotent `CalendarSync.push` via IdentityMap, CLI `calendar auth/push/list`
- ICS export (RFC 5545, zero-auth) — CLI `calendar export-ics`
- Console-safe CLI output (Windows cp1252 emoji crash fix)

## [0.4.0] — 2026-08-12

### Added
- Knowledge substrate: `AttachmentRepository`, keyword search, `SemanticSearch` (offline n-gram embeddings, typo-tolerant)
- `Embeddings` port + `LocalNGramEmbedder` (256-dim, zero deps) + `OllamaEmbedder` (v0.6 groundwork)
- `PlanStore` — raw plan persisted for faithful export/sync reconstruction

## [0.3.0] — 2026-08-12

### Added
- `MarkdownProjection` + CLI `export markdown`

## [0.2.0] — 2026-08-10

### Added
- Real `TodoistAdapter` (SDK 4.0), `IdentityMap`, three-way `Differ` with conflict detection, `SyncEngine`, CLI `sync todoist`

## [0.1.0] — 2026-07-27

### Added
- **Domain aggregates**: Workspace, Project, Goal, Milestone, Task, Priority
- **Domain events**: WorkspaceCreated, ProjectCreated, GoalCreated, MilestoneCreated, TaskCreated, TaskCompleted
- **SQLite repositories**: file-based persistence at `~/.growth/growth.db`
- **YAML parser**: reads MVP-format study plans
- **Heuristic interpreter**: lifts RawPlan → CanonicalPlan
- **Todoist projection**: maps canonical plans to provider-shaped snapshots
- **Todoist adapter**: dry-run provider adapter (API integration in v0.2)
- **PlanApplier use case**: full YAML → Workspace → Project → Goals → Milestones → Tasks pipeline
- **CLI commands**: `growth plan apply`, `growth plan show`, `growth plan stats`
- **Unit tests**: InternalId, SpaceId, domain errors, all 5 aggregates
- **Integration tests**: SQLite repository CRUD for Workspace, Project, Task
- **Smoke test**: `growth --version` vertical slice
- **Documentation**: README, Tutorial, Architecture, Roadmap, Contributing, 3 ADRs, Development Runbook
- **CI pipeline**: ruff, mypy strict, import-linter, pytest on Python 3.11–3.13

### Bootstrap (pre-v0.1)
- Hexagonal skeleton with all ports (Protocols) and Noop implementations
- Pydantic Settings, structlog logging, SyncEventDispatcher
- Manual DI container, composition root (`build_app`)
- Import-linter contracts (3) enforcing hexagonal dependency direction
- Pre-commit hooks (ruff, mypy on inner rings, import-linter, standard hooks)
- Archived MVP: `archive/v0-mvp/`
