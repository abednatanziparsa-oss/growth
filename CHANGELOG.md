# Changelog

All notable changes to Growth OS.

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
