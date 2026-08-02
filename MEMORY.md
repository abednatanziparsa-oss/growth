# MEMORY.md — Growth OS Long-Term Memory

## Project Identity

- **Name:** Growth OS
- **Version:** 0.1.0.dev0 (pre-alpha)
- **Type:** Personal growth operating system — planning, knowledge management, learning, review, execution
- **Architecture:** Hexagonal (Ports & Adapters) with strict import-linter enforcement
- **Owner:** Parsa Abed
- **Repo:** `https://github.com/abednatanziparsa-oss/placement-exam-todoist` (⚠️ needs rename to `growth` — blocked by token scope)
- **Created:** 2026-07 (bootstrapped by Luo 🦞 over ~10 days)

## Tech Stack

- Python 3.11+, uv (package manager), hatchling (build)
- Ruff (lint + format), mypy strict, import-linter (3 contracts), pytest + hypothesis
- Typer CLI, Pydantic Settings, structlog, SQLite (~/.growth/growth.db)
- Manual DI (no framework — Container is a plain @dataclass)

## Architecture Rules (DO NOT BREAK)

1. Domain imports NOTHING external — no I/O, no framework deps
2. Application depends only on domain
3. Presentation depends only on application + kernel (not infrastructure directly)
4. Only `kernel/bootstrap.py` and `kernel/container.py` wire adapters
5. Every optional port has a Noop default — system runs offline by default
6. YAGNI: plugin registry, real adapters, workflow scheduling, AI backends deferred

## Current State (2026-08-02)

### CI: ALL GREEN ✅
- ruff lint ✅, ruff format ✅, mypy strict ✅ (50 files), import-linter ✅ (3 kept), pytest ✅ (25 passed)
- Coverage: 46% (770 statements, 368 missed)
- Git: 15 commits on main, synced with remote, working tree clean

### What's Built (v0.1)
- Domain aggregates: Workspace, Project, Goal, Milestone, Task, Priority
- Domain events: WorkspaceCreated, ProjectCreated, GoalCreated, MilestoneCreated, TaskCreated, TaskCompleted
- SQLite repos: file-based (~/.growth/growth.db), 5 repositories
- YAML parser + HeuristicInterpreter (RawPlan → CanonicalPlan)
- Todoist projection (canonical→provider) + Todoist adapter (DRY-RUN ONLY)
- PlanApplier: YAML → Workspace → Project → Goals → Milestones → Tasks
- CLI: `growth plan apply/show/stats` + `--version`
- 10 application ports (all Protocols): AI, clock, decision, events, interpreter, parser, projection, adapter, repo, workflow
- Noop implementations for all optional ports

### What's NOT Yet Built (v0.2 → v1.0)
- Sync engine: three-way diff, IdentityMap, real Todoist API (v0.2)
- Markdown export (v0.3)
- Knowledge substrate: attachments, embeddings, search (v0.4)
- Reminders, scheduling, Google Calendar (v0.5)
- AI integration: Ollama/OpenAI/Anthropic, PDF parser (v0.6)
- DecisionEngine, WorkflowEngine (v0.7)
- Platform: plugin marketplace, desktop app, GraphQL (v1.0)

### Test Coverage Gaps (priority targets)
- `plan_applier.py`: 21% — critical pipeline, needs integration tests
- `cli/app.py`: 24% — only user surface, needs integration tests
- `HeuristicInterpreter`: 0% — critical conversion, needs unit tests
- `YamlParser`: 0% — critical parsing, needs unit tests
- `planning_repos.py`: 51% — needs edge case coverage (duplicate, missing parent, cascade)
- `TodoistProjection`: 0%, `TodoistAdapter`: 0% — need both unit + integration

## Decisions Made

1. **Hexagonal strict** — import-linter enforces. Non-negotiable.
2. **Manual DI** — no framework. Explicit > implicit. Container as plain dataclass.
3. **Noop defaults** — AI/decision/workflow are advisory-only. System runs offline.
4. **Single tool** — ruff replaces flake8 + isort + black. One pyproject.toml.
5. **File-based SQLite** — ~/.growth/growth.db, auto-created on first build_app().
6. **Dry-run Todoist** — adapter is stub. Real API deferred to v0.2.
7. **Archive frozen** — `archive/v0-mvp/` is read-only, never modified.
8. **Coverage target** — measure on src/growth, omit noop/ and __init__.py.

## Known Issues

1. **Git remote name** — still `placement-exam-todoist` (MVP era). Rename to `growth` blocked by token scope (no delete_repo). Parsa must rename from GitHub Settings.
2. **Token scopes limited** — no `workflow`, no `delete_repo`. CI workflow push to new repo blocked.
3. **`growth` empty repo** — exists on GitHub (created by mistake during rename attempt). Needs deletion from GitHub UI by Parsa.
4. **types-PyYAML** — not installed. mypy config suppresses import-untyped for yaml files.
5. **Coverage 46%** — acceptable for v0.1 but needs to reach 70%+ before v0.2.

## Communication Notes

- Parsa prefers Persian for conversation, English for code
- Address directly, no filler pleasantries
- Project directory: `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth`
- Use `uv run` for all Python commands

## Priority Roadmap (2026-08-02)

### Phase 0: Critical (today)
- [x] Push code to remote ✅
- [ ] Rename repo from `placement-exam-todoist` to `growth` (blocked — needs manual GitHub action)
- [ ] Delete empty `growth` repo on GitHub (blocked — needs manual GitHub action)
- [ ] MEMORY.md created ✅

### Phase 1: Consolidate v0.1 (this week)
- [ ] Integration tests for plan_applier.py (21% → 80%+)
- [ ] Integration tests for CLI (24% → 70%+)
- [ ] Coverage for planning_repos.py (51% → 80%+)
- [ ] Unit tests for HeuristicInterpreter and YamlParser (0% → 90%+)
- [ ] Sync .env.example with actual .env

### Phase 2: v0.2 Sync Engine (2-3 weeks)
- [ ] Real Todoist adapter (todoist-api-python)
- [ ] IdentityMap (InternalId ↔ Todoist resource ID)
- [ ] Three-way diff engine
- [ ] Conflict detection + resolution
- [ ] `growth sync` CLI
- [ ] Integration test with sandbox Todoist project
