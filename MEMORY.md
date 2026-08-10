# MEMORY.md — Growth OS Long-Term Memory

## Project Identity

- **Name:** Growth OS
- **Version:** 0.1.0.dev0 (pre-alpha)
- **Type:** Personal growth operating system — planning, knowledge management, learning, review, execution
- **Architecture:** Hexagonal (Ports & Adapters) with strict import-linter enforcement
- **Owner:** Parsa Abed
- **Repo:** `https://github.com/abednatanziparsa-oss/growth`
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

## Current State (2026-08-10) — updated end of session

### CI: ALL GREEN ✅
- ruff lint ✅, ruff format ✅, mypy strict ✅ (54 files), import-linter ✅ (3 kept), pytest ✅ (87 passed, 0 failed)
- Coverage: **81%** (771 statements, 135 missed)
- Git: 20 commits on main, synced with remote `github.com/abednatanziparsa-oss/growth`

### What's Built (v0.1 → v0.2)
- Domain aggregates: Workspace, Project, Goal, Milestone, Task, Priority
- Domain events: WorkspaceCreated, ProjectCreated, GoalCreated, MilestoneCreated, TaskCreated, TaskCompleted
- SQLite repos: file-based (~/.growth/growth.db), 5 repositories — **97% coverage**
- YAML parser + HeuristicInterpreter (RawPlan → CanonicalPlan) — **100% coverage**
- Todoist projection (canonical→provider) + TodoistAdapter (REAL API, dry-run flag)
- PlanApplier: YAML → Workspace → Project → Goals → Milestones → Tasks — **100% coverage**
- CLI: `growth plan apply/show/stats` + `growth sync todoist --dry-run` + `--version` — **97% coverage**
- IdentityMap: InternalId ↔ provider resource id persistence in SQLite
- Differ: two-way snapshot diff producing ChangeSet
- SyncEngine: orchestrate project → diff → apply → persist
- 10 application ports (all Protocols): AI, clock, decision, events, interpreter, parser, projection, adapter, repo, workflow
- Noop implementations for all optional ports

### Coverage Detail (2026-08-02 end-of-session)

| File | Coverage |
|---|---|
| `dtos.py` | 100% |
| `plan_applier.py` | 100% |
| `ports/interpreter.py` | 100% |
| `ports/parser.py` | 100% |
| `planning_repos.py` | 97% |
| `cli/app.py` | 97% |
| `kernel/container.py` | 100% |
| `yaml_parser.py` | 100% |
| `heuristic.py` | 100% |
| `TodoistProjection` + `TodoistAdapter` | 0% (dry-run, v0.2) |
| **Total** | **81%** |

### What's NOT Yet Built (v0.2 → v1.0)
- Sync engine: three-way diff, IdentityMap, real Todoist API (v0.2) ← **next**
- Markdown export (v0.3)
- Knowledge substrate: attachments, embeddings, search (v0.4)
- Reminders, scheduling, Google Calendar (v0.5)
- AI integration: Ollama/OpenAI/Anthropic, PDF parser (v0.6)
- DecisionEngine, WorkflowEngine (v0.7)
- Platform: plugin marketplace, desktop app, GraphQL (v1.0)

## Decisions Made

1. **Hexagonal strict** — import-linter enforces. Non-negotiable.
2. **Manual DI** — no framework. Explicit > implicit. Container as plain dataclass.
3. **Noop defaults** — AI/decision/workflow are advisory-only. System runs offline.
4. **Single tool** — ruff replaces flake8 + isort + black. One pyproject.toml.
5. **File-based SQLite** — ~/.growth/growth.db, auto-created on first build_app().
6. **Dry-run Todoist** — adapter is stub. Real API deferred to v0.2.
7. **Archive frozen** — `archive/v0-mvp/` is read-only, never modified.
8. **Coverage target** — measure on src/growth, omit noop/ and __init__.py.
9. **CanonicalPlan unfrozen** — changed from frozen=True to kw_only mutable dataclass so interpreters can populate `project_name` and `raw_payload` without monkey-patching private attrs.

## Known Issues

1. **Token scopes limited** — `gh` token has `gist, read:org, repo` but no `workflow` or `delete_repo`. CI workflow push to a new repo would fail; rename/delete must be done from GitHub UI.
2. **types-PyYAML** — not installed. mypy config suppresses import-untyped for yaml files.
3. **Todoist adapter is stub** — real API integration deferred to v0.2.

## Communication Notes

- Parsa prefers Persian for conversation, English for code
- Address directly, no filler pleasantries
- Project directory: `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth`
- Use `uv run` for all Python commands

## Session Log (2026-08-10)

### v0.2 Sync Engine — COMPLETE ✅

**Delivered:**
1. [x] Installed `todoist-api-python` ✅
2. [x] Replaced `TodoistAdapter` stub with real API adapter ✅
3. [x] IdentityMap (InternalId ↔ Todoist resource ID) ✅
4. [x] Differ — two-way snapshot diff → ChangeSet ✅
5. [x] SyncEngine — orchestrates project → diff → apply → persist ✅
6. [x] CLI: `growth sync todoist --dry-run` ✅
7. [x] Kernel bootstrap: App now wires IdentityMap + init_sync_state ✅
8. [x] Architecture: import-linter passes (3 contracts kept) ✅
9. [x] .env: renamed TODOIST_API_TOKEN → GROWTH_TODOIST_API_TOKEN ✅

**CI: ALL GREEN** — ruff ✅, mypy strict ✅ (54 files), import-linter ✅, pytest 87/87 ✅

**Remaining for v0.2:**
- Tests for IdentityMap, Differ, SyncEngine (0% coverage → need tests)
- Three-way conflict detection (currently two-way diff)
- Real Todoist API end-to-end test (needs live token)

---

## Session Log (2026-08-02)

### Completed This Session

**Phase 0:**
- [x] Push code to remote ✅
- [x] Rename repo `placement-exam-todoist` → `growth` ✅ (Parsa did manually)
- [x] Delete empty `growth` repo on GitHub ✅ (Parsa did manually)
- [x] MEMORY.md created and populated ✅

**Phase 1:**
- [x] Integration tests for `plan_applier.py` (21% → **100%**) ✅ — 11 tests
- [x] Integration tests for CLI (24% → **97%**) ✅ — 11 tests
- [x] Coverage for `planning_repos.py` (51% → **97%**) ✅ — 24 new edge-case tests
- [x] Unit tests for `HeuristicInterpreter` (0% → **100%**) ✅ — 8 tests
- [x] Unit tests for `YamlParser` (0% → **100%**) ✅ — 8 tests
- [x] Sync `.env.example` with actual .env ✅
- [x] Fixed CanonicalPlan frozen dataclass bug (was `frozen=True`, couldn't set attrs) ✅

**Overall:** 25 → **87 tests**, coverage 46% → **81%**, 5 new commits pushed.

### Next Session: v0.2 Sync Engine
1. Install `todoist-api-python`
2. Replace `TodoistAdapter` stub with real API adapter
3. IdentityMap (InternalId ↔ Todoist resource ID)
4. Fetch current state from Todoist
5. Three-way diff engine
6. `growth sync` CLI
