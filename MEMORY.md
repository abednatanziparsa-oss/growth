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

## Current State (2026-08-12) — updated end of session

### CI: ALL GREEN ✅
- ruff lint ✅, ruff format ✅, mypy strict ✅ (59 files), import-linter ✅ (3 kept), pytest ✅ (362 passed, 0 failed)
- Coverage: **98%** (1896 statements, 29 missed)
- Git: 38 commits on main, synced with remote `github.com/abednatanziparsa-oss/growth`

### What's Built (v0.1 → v0.4)
- Domain aggregates: Workspace, Project, Goal, Milestone, Task, Priority
- Domain events: WorkspaceCreated, ProjectCreated, GoalCreated, MilestoneCreated, TaskCreated, TaskCompleted
- SQLite repos: file-based (~/.growth/growth.db), 5 repositories — **95-97% coverage**
- YAML parser + HeuristicInterpreter (RawPlan → CanonicalPlan) — **100% coverage**
- TodoistProjection (canonical→provider, p1-p4 + sections) + TodoistAdapter (REAL API, mocked-tested) — **100%**
- PlanApplier: YAML → Workspace → Project → Goals → Milestones → Tasks — **100% coverage**
- CLI: `plan apply/show/stats`, `sync todoist`, `export markdown`, `knowledge attach/list/search`, `--version` — **97%**
- IdentityMap: InternalId ↔ provider resource id persistence — **100%**
- Differ: two-way + **three-way diff with conflict detection** (v0.2.1) — **96%**
- SyncEngine: project → diff → apply → persist — **98%**
- **MarkdownProjection + `export markdown`** (v0.3) — **100%**
- **Knowledge substrate** (v0.4): AttachmentRepository + KeywordSearch + **SemanticSearch** (offline n-gram embeddings, typo-tolerant) — **99%/95%**
- **Embeddings port** (v0.4): `LocalNGramEmbedder` (deterministic char n-gram hashing, 256-dim, zero deps) — **100%**
- **Reminders + scheduling engine** (v0.5, partial): Reminder aggregate + status lifecycle + `ReminderDue` event; SQLite `ReminderRepository` with recurrence JSON column + legacy migration; `RecurrenceRule` (daily/weekly/monthly, interval, until, count); `Scheduler.sweep()` fires due reminders, dispatches events, re-arms recurring series with failure isolation; CLI `reminder add --repeat/--interval/--until/--count`, `reminder list/due/fire/sweep` — all **100%**
- **Model embeddings wired into SemanticSearch** (v0.6 groundwork): `OllamaEmbedder` (httpx-based, `POST /api/embed`, L2-normalized) behind the `Embeddings` port; `SemanticSearch` accepts any embedder and falls back to `LocalNGramEmbedder` on `EmbeddingUnavailableError` (offline-first, queries never break when the server is down); wired via `GROWTH_OLLAMA_BASE_URL` / `GROWTH_OLLAMA_MODEL` (bge-m3) — **100%**
- **TodoistAdapter SDK 4.0 conformance + live E2E** (v0.2 hardening): verified every adapter call against installed todoist-api-python 4.0.0; fixed `is_completed` bug (SDK Task model has `completed_at`, not `is_completed`); E2E harness (`tests/integration/test_todoist_e2e.py`) ran against the REAL API — full round trip passed (unique project + delete-in-finally cleanup); findings: `get_tasks()` returns ACTIVE tasks only, completed-tasks window capped at 6 weeks, no-due-date tasks verifiable only via by_completion_date
- **PlanStore** (v0.4.1): raw plan persisted at apply → faithful export/sync reconstruction — **100%**
- SyncEventDispatcher: pub/sub with failure isolation — **100%**
- 10 application ports (all Protocols): AI, clock, decision, events, interpreter, knowledge, parser, projection, adapter, repo, workflow
- Noop implementations for all optional ports

### Coverage Detail (2026-08-12 end-of-session)

| File | Coverage |
|---|---|
| `plan_store.py` (new) | 100% |
| `embeddings/local.py` (new) | 100% |
| `storage/semantic_search.py` (new) | 95% |
| `storage/reminder_repos.py` (new) | 100% |
| `domain/reminders/recurrence.py` (new) | 100% |
| `scheduler.py` (new) | 100% |
| `plan_applier.py` | 100% |
| `projections/markdown.py` | 100% |
| `projections/todoist.py` | 100% (fixed private-attr bug) |
| `adapters/todoist.py` | 100% (mocked) |
| `sync/differ.py` | 96% |
| `sync/engine.py` | 98% |
| `storage/planning_repos.py` | 95% |
| `storage/knowledge_repos.py` | 99% |
| `kernel/bootstrap.py` | 100% |
| `cli/app.py` | 97% |
| ports (incl. `knowledge.py`) | 100% |
| **Total** | **98%** |

### What's NOT Yet Built (v0.5 -> v1.0)
- v0.5 completion: **Google Calendar projection + real scheduler dispatch** <- **next** (needs OAuth creds)
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
3. **Export/sync legacy fallback** — DBs created before PlanStore (v0.4.1) export header-only plans; re-run `plan apply` to persist the raw plan.

## Communication Notes

- Parsa prefers Persian for conversation, English for code
- Address directly, no filler pleasantries
- Project directory: `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth`
- Use `uv run` for all Python commands
- **Status tables after turns:** When working on long multi-step coding tasks, end each turn with a Persian summary table (✅ انجام شده / 🔄 در حال انجام / ⏳ باقی‌مانده) showing what was completed, what's in progress, and what remains. This keeps Parsa oriented during long sessions without needing to scroll back.
- **Resume work continuously (2026-08-12):** Parsa wants work to run end-to-end without piecemeal stops — do NOT ask "should I start?" between steps; pick up where the last session left off and push to completion (test → CI green → commit → push) in the same turn. Ask only when genuinely blocked on a decision.

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

**Remaining for v0.2 (as of 2026-08-12):**
- Real Todoist API end-to-end test (needs live token) — everything else shipped in v0.2.1/v0.3/v0.4 + this session's test sweep

---

## Session Log (2026-08-12)

### v0.3/v0.4 Test Sweep + Bugfixes — COMPLETE ✅

Parsa: «کار رو از سر بگیر همیشه» — no more piecemeal stops; resume and finish.

**Delivered:**
1. [x] Unit tests for MarkdownProjection + TodoistProjection (0% → **100%**) ✅
2. [x] Unit tests for TodoistAdapter with mocked API (0% → **100%**) ✅
3. [x] Differ branch tests: section moves, three-way conflict/merge/external-create/recreate (79% → **96%**) ✅
4. [x] SyncEngine tests: root_id persistence, identity-map classification (67% → **98%**) ✅
5. [x] CLI tests: export/knowledge/sync commands + `--version` (46% → **97%**) ✅
6. [x] Bootstrap tests (44% → **100%**) + event dispatcher tests (48% → **100%**) ✅
7. [x] Settings/logging/domain-id tests; ports/knowledge.py now covered (was 0%) ✅
8. [x] **BUGFIX: TodoistProjection read legacy private attrs** (`_project_name`/`_raw_payload`) → `growth sync todoist` produced empty snapshots. Now reads public `project_name`/`raw_payload`. ✅
9. [x] **BUGFIX: export/sync rebuilt plans with empty subjects** → header-only Markdown, no-op sync. Added **PlanStore** (raw plan persisted at apply time, `plans` table) + `App.plan_store` + CLI `_current_plan()` with legacy fallback. ✅
10. [x] `ruff format` on 14 files; CI green; **coverage 67% → 98%** (256 tests) ✅

**CI: ALL GREEN** — ruff ✅, mypy strict ✅ (59 files), import-linter ✅ (3 contracts), pytest 256/256 ✅, coverage **98%**.

**Next:**
- v0.5 completion: Google Calendar projection (needs OAuth creds) <- **next**
- Real Todoist end-to-end test (needs live token)

---

## Session Log (2026-08-12) — v0.4 completion
## Session Log (2026-08-12) — Todoist SDK 4.0 hardening
## Session Log (2026-08-13) — OllamaEmbedder (v0.6 groundwork)

- [x] `infrastructure/embeddings/ollama.py`: httpx-based Ollama client, L2 normalized, all failure paths typed (`EmbeddingUnavailableError`) ✅
- [x] `SemanticSearch` now takes any `Embeddings` impl + offline fallback on `EmbeddingUnavailableError`; bootstrap wires Ollama when configured; 4 new tests; CI: 362 passed, coverage 98% ✅
## Session Log (2026-08-13) — console safety + cron dispatch

- [x] **BUGFIX: CLI emoji crash on Windows cp1252** — live `growth reminder sweep`/`plan show` crashed with UnicodeEncodeError (emoji in output AND in plan titles from user YAML data). Hardcoded CLI emoji → ASCII tokens; `run()` reconfigures stdout/stderr with `errors=replace` ✅
- [x] **Real scheduler dispatch**: cron job `Growth reminder sweep (daily)` (08:00 Asia/Tehran, session-bound) runs `growth reminder sweep` every day; announce-to-webchat delivery doesn't resolve (no configured channel), so the job is bound to the main session instead ✅
- CI: 362 passed, coverage 98% ✅

- [x] Settings `ollama_base_url` (None = offline) + `ollama_model` (bge-m3); bootstrap wires `App.ollama_embedder` when configured ✅
- [x] 11 new tests (port conformance, normalization, zero-vector, failures, env overrides, wiring); CI: 358 passed, coverage 98% ✅


- [x] Verified TodoistAdapter against installed SDK 4.0.0 (add_task/update_task/complete_task/get_tasks iterator all match) ✅
- [x] **BUGFIX: `is_completed` AttributeError** — SDK 4.x Task has `completed_at`, not `is_completed`; adapter now maps `completed_at is not None` + test covers done/open states ✅
- [x] E2E harness `tests/integration/test_todoist_e2e.py` (skipped w/o token; unique project + finally-cleanup) ✅
- [x] Lint cleanup for ruff 0.15 (zip strict, PLC0415, F841, B017, ARG005) ✅
- CI: 347 passed, coverage 98% ✅
- [x] **Live E2E PASSED** (Parsa supplied a real token via chat; env-var only, never persisted): create project/section/task → fetch → update+complete → verify via completed-tasks endpoint → delete cleanup. Documented API quirks (active-only get_tasks, 6-week window cap, by_completion_date for dateless tasks) ✅

### Semantic Search — COMPLETE ✅ (v0.4 done)

Parsa: «ادامه بده» — resumed immediately after the test sweep; no stop.

**Delivered:**
1. [x] **Embeddings port** (`application/ports/embeddings.py`) — seam for model-backed embedders in v0.6 ✅
2. [x] **LocalNGramEmbedder** (`infrastructure/embeddings/local.py`) — deterministic md5 char n-gram (2-4) hashing, 256-dim L2-normalized, sign trick; zero deps, offline ✅
3. [x] **SemanticSearch** (`infrastructure/storage/semantic_search.py`) — implements `KnowledgeSearch` port; cosine similarity + exact-keyword boost; MIN_SIM_SCORE=10 filters hash-collision noise (measured: noise ~0.07 sim vs real matches 0.47+); typo-tolerant (`roadmapp` → finds `roadmap`) ✅
4. [x] `App.semantic_search` wired in bootstrap; CLI `knowledge search --semantic` + unavailable-path error ✅
5. [x] Tests: embedder determinism/L2/typo, cosine, SemanticSearch ranking/space/limit/snippet, CLI flag (256 → **278 tests**) ✅

**CI: ALL GREEN** — ruff ✅, mypy strict ✅, import-linter ✅ (3 contracts), pytest 278/278 ✅, coverage **98%**.

**v0.4 = COMPLETE ✅** — knowledge substrate ships: attachments (content-addressed dedup) + keyword search + offline semantic search.

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
