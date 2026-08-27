# MEMORY.md - Growth OS Long-Term Memory

## Project Identity

- **Name:** Growth OS
- **Version:** 0.1.0.dev0 (pre-alpha)
- **Type:** Personal growth operating system - planning, knowledge management, learning, review, execution
- **Architecture:** Hexagonal (Ports & Adapters) with strict import-linter enforcement
- **Owner:** Parsa Abed
- **Repo:** `https://github.com/abednatanziparsa-oss/growth`
- **Created:** 2026-07 (bootstrapped by Luo 🦞 over ~10 days)

## Tech Stack

- Python 3.11+, uv (package manager), hatchling (build)
- Ruff (lint + format), mypy strict, import-linter (3 contracts), pytest + hypothesis
- Typer CLI, Pydantic Settings, structlog, SQLite (~/.growth/growth.db)
- Manual DI (no framework - Container is a plain @dataclass)

## Architecture Rules (DO NOT BREAK)

1. Domain imports NOTHING external - no I/O, no framework deps
2. Application depends only on domain
3. Presentation depends only on application + kernel (not infrastructure directly)
4. Only `kernel/bootstrap.py` and `kernel/container.py` wire adapters
5. Every optional port has a Noop default - system runs offline by default
6. YAGNI: plugin registry, workflow scheduling deferred; AI backends exist behind ports but stay Noop-default (offline-first)

## Current State (2026-08-27) - v0.8 COMPLETE + Google Calendar production live

### CI: ALL GREEN ✅
- ruff lint ✅, ruff format ✅, mypy strict ✅ (89 files), import-linter ✅ (3 kept), pytest ✅ (573 passed, 1 skipped - live Todoist E2E needs token)
- Coverage: **98%** (new v0.6/v0.7/v0.8 files 100%)
- Git: 66 commits on main, synced with remote `github.com/abednatanziparsa-oss/growth`

### What's Built (v0.1 → v0.7)
- Domain aggregates: Workspace, Project, Goal, Milestone, Task, Priority
- Domain events: WorkspaceCreated, ProjectCreated, GoalCreated, MilestoneCreated, TaskCreated, TaskCompleted
- SQLite repos: file-based (~/.growth/growth.db), 5 repositories - **95-97% coverage**
- YAML parser + HeuristicInterpreter (RawPlan → CanonicalPlan) - **100% coverage**
- TodoistProjection (canonical→provider, p1-p4 + sections) + TodoistAdapter (REAL API, mocked-tested) - **100%**
- PlanApplier: YAML → Workspace → Project → Goals → Milestones → Tasks - **100% coverage**
- CLI: `plan apply/show/stats`, `sync todoist`, `export markdown`, `knowledge attach/list/search`, `--version` - **97%**
- IdentityMap: InternalId ↔ provider resource id persistence - **100%**
- Differ: two-way + **three-way diff with conflict detection** (v0.2.1) - **96%**
- SyncEngine: project → diff → apply → persist - **98%**
- **MarkdownProjection + `export markdown`** (v0.3) - **100%**
- **Knowledge substrate** (v0.4): AttachmentRepository + KeywordSearch + **SemanticSearch** (offline n-gram embeddings, typo-tolerant) - **99%/95%**
- **Embeddings port** (v0.4): `LocalNGramEmbedder` (deterministic char n-gram hashing, 256-dim, zero deps) - **100%**
- **Reminders + scheduling engine** (v0.5, partial): Reminder aggregate + status lifecycle + `ReminderDue` event; SQLite `ReminderRepository` with recurrence JSON column + legacy migration; `RecurrenceRule` (daily/weekly/monthly, interval, until, count); `Scheduler.sweep()` fires due reminders, dispatches events, re-arms recurring series with failure isolation; CLI `reminder add --repeat/--interval/--until/--count`, `reminder list/due/fire/sweep` - all **100%**
- **Model embeddings wired into SemanticSearch** (v0.6 groundwork): `OllamaEmbedder` (httpx-based, `POST /api/embed`, L2-normalized) behind the `Embeddings` port; `SemanticSearch` accepts any embedder and falls back to `LocalNGramEmbedder` on `EmbeddingUnavailableError` (offline-first, queries never break when the server is down); wired via `GROWTH_OLLAMA_BASE_URL` / `GROWTH_OLLAMA_MODEL` (bge-m3) - **100%**
- **TodoistAdapter SDK 4.0 conformance + live E2E** (v0.2 hardening): verified every adapter call against installed todoist-api-python 4.0.0; fixed `is_completed` bug (SDK Task model has `completed_at`, not `is_completed`); E2E harness (`tests/integration/test_todoist_e2e.py`) ran against the REAL API - full round trip passed (unique project + delete-in-finally cleanup); findings: `get_tasks()` returns ACTIVE tasks only, completed-tasks window capped at 6 weeks, no-due-date tasks verifiable only via by_completion_date
- **Google Calendar layer** (v0.5): `GoogleCalendarAdapter` (create/update/delete/list events, service-injected & mock-tested); `CalendarProjection` (pending reminder -> event, 30-min default, target in description); `CalendarSync` application use case (idempotent push via IdentityMap provider=gcal, no duplicate events, per-reminder failure isolation); `IdentityMapPort` (new application port); `run_oauth_flow` + `build_calendar_service` (installed-app OAuth, calendar.events scope); Settings `GROWTH_GOOGLE_CREDENTIALS_PATH`/`GROWTH_GOOGLE_TOKEN_PATH` (offline by default); CLI `calendar auth|push|list` - **all 100% covered**
- **ICS export - zero-auth calendar** (v0.5.1): `IcsProjection` renders EventPayloads as RFC 5545 iCalendar (CRLF endings, value escaping, 75-octet folding, stable per-reminder UIDs, UTC-normalized); `App.export_calendar_ics()` -> (text, count); CLI `calendar export-ics` (default ~/.growth/reminders.ics, imports into any calendar app, no OAuth); fixed Windows CRLF translation bug (write_text -> CR CRLF, newline='') - **all 100% covered**
- **PlanStore** (v0.4.1): raw plan persisted at apply → faithful export/sync reconstruction - **100%**
- **AI chat + interpreter** (v0.6): `LLMChat` port (`application/ports/llm.py`) + `LLMUnavailableError`; `OpenAICompatibleChat` (httpx, non-streaming, Bearer auth, injectable client, all failures → `LLMUnavailableError`); `AiInterpreter` (free-text → CanonicalPlan via prompt `growth-plan-json-v1`, tolerant JSON parse, heuristic fallback, returns `DecisionArtifact`); CLI `plan ai-apply <text> [--apply]` (dry-run default); Settings `GROWTH_LLM_BASE_URL/MODEL/API_KEY/TIMEOUT` + `GROWTH_AI_ENABLED` gate - **all 100%**
- **PDF parsing + AI summarization** (v0.6): `DocumentParser` port + `PypdfParser` (pypdf, encrypted/corrupt/missing → `DocumentParseError`); `AiDocumentSummarizer` (prompt `growth-doc-summary-v1`, 6000-char cap); `knowledge attach <pdf>` auto-extracts searchable `content_text`; `knowledge extract <file> [--summarize]`; idempotent schema migration (`content_text`/`summary`) - **all 100%**
- **Live LLM smoke test** (v0.6, 2026-08-19): 9Router local gateway + Kiro (`kr/deepseek-3.2`) - only working cloud-LLM path from Iran; GitHub Models retired (410), OpenRouter geo-blocked (403), Gemini standard keys deprecated
- **HeuristicDecisionEngine** (v0.7, 2026-08-20): real `DecisionEngine` impl (`infrastructure/decision/heuristic.py`) - queries `next_action` (highest-priority actionable task, leaf-first), `blockers` (overdue tasks), `priority_sort`; advisory-only, deterministic (no LLM), reads via `TaskRepository`; `App.decision_engine` lazy property + CLI `decide next-action|blockers|sort` - **100%**
- **DeclarativeWorkflowEngine** (v0.7, 2026-08-26): real `WorkflowEngine` (`infrastructure/workflow/engine.py`) - `register`/`run`/`dry-run` (no side effects)/`cancel` (cooperative)/`runs` history; failure isolation (stop at first error); steps wrap use cases, never raw domain/infra; port `WorkflowRunResult` extended with `errors`/`note`; wired in Container (replaces Noop) - **100%**
- **Workflow YAML loader + CLI + persistence** (v0.7, 2026-08-26): `parse_workflow_yaml` (`infrastructure/workflow/loader.py`, name/trigger/steps validation, safe-filename check); `Settings.workflows_dir` (default `~/.growth/workflows`); bootstrap `persist_workflow_yaml`/`load_workflows_dir`/`builtin_workflow_steps` (next-action, blockers, priority-sort, reminder-sweep, export-ics); CLI `workflow register|run|list` - register persists, run auto-loads the dir (cross-process); examples `daily-review.yaml` + `review-loop.yaml` - **100%**
- **CLI exit-code fix** (v0.7, 2026-08-26): `run()` discarded the typer exit code (`app(standalone_mode=False)` return ignored, always `sys.exit(0)`) - every failing command exited 0; now propagates. Verified live: failing → 1, success → 0
- **LlmDecisionEngine** (v0.8, 2026-08-27): `application/llm_decisions.py` - wraps the deterministic `DecisionEngine` with `LLMChat` enrichment: recommendation payload NEVER altered, LLM appends rationale to reasoning (`growth-decision-advice-v1`); `LLMUnavailableError` → base artifact unchanged; falsy recommendation → LLM skipped entirely; advice capped 1200 chars; `App.decision_engine` returns it over new `App.heuristic_decision_engine` property; CLI `decide` shows `[AI: model]` line - **100%**
- **PlanReviewer + PlanImprover** (v0.8, 2026-08-27): `application/plan_review.py` - `plan-review` aggregates next_action+blockers+priority_sort into one deterministic artifact (capability `plan_review`); `plan-improve` asks LLM for suggestions (`growth-plan-improve-v1`, capped 2000 chars), falls back to the review unchanged when unavailable (capability `plan_improvement`); new builtin workflow steps `plan-review`/`plan-improve`; `review-loop.yaml` example now execution → review → improvement - **100%**
- SyncEventDispatcher: pub/sub with failure isolation - **100%**
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

### What's NOT Yet Built (v1.0)
- Google Calendar production: **DONE 2026-08-26** ✅ - app published (In production) + fresh token under production rules (no 7-day expiry)
- LLM-assisted decisions + planning/improvement workflow steps: **DONE 2026-08-27** ✅ (v0.8)
- Platform: plugin marketplace, desktop app (PySide6), GraphQL API, multi-user spaces (v1.0)

## Decisions Made

1. **Hexagonal strict** - import-linter enforces. Non-negotiable.
2. **Manual DI** - no framework. Explicit > implicit. Container as plain dataclass.
3. **Noop defaults** - AI/decision/workflow are advisory-only. System runs offline.
4. **Single tool** - ruff replaces flake8 + isort + black. One pyproject.toml.
5. **File-based SQLite** - ~/.growth/growth.db, auto-created on first build_app().
6. **Dry-run Todoist** - adapter is stub. Real API deferred to v0.2.
7. **Archive frozen** - `archive/v0-mvp/` is read-only, never modified.
8. **Coverage target** - measure on src/growth, omit noop/ and __init__.py.
9. **CanonicalPlan unfrozen** - changed from frozen=True to kw_only mutable dataclass so interpreters can populate `project_name` and `raw_payload` without monkey-patching private attrs.
10. **LLM provider = 9Router + Kiro** - only working cloud-LLM path from Iran (verified 2026-08-19). OpenAI/Anthropic/Groq don't serve Iran; GitHub Models retired; OpenRouter geo-blocks; Gemini standard keys deprecated. Primary model `kr/deepseek-3.2`. Offline-first stays: `GROWTH_AI_ENABLED=false` default.
11. **DecisionEngine is deterministic** - heuristic (no LLM), reproducible and free; LLM-assisted decisions (later) wrap this core. Recommendation payloads are plain dicts, not domain objects.
12. **httplib2 must run with `proxy_info=None`** - empty proxy env vars (`HTTP_PROXY=`/`HTTPS_PROXY=`/`ALL_PROXY=`, set by the OpenClaw runtime) make httplib2 0.32 connect to a broken proxy and time out (`WinError 10060`). `build_calendar_service` now passes `Http(timeout=30, proxy_info=None)`. Lesson: when Google API calls time out but curl/sockets work, suspect httplib2 + proxy env.
13. **`uv run --offline` after pyproject.toml changes** - any pyproject edit makes uv re-resolve the build and fetch `hatchling` from pypi.org, which is unreachable from Iran (os error 10061). Use `uv run --offline <cmd>` (works from cache).
14. **LLM enriches, never decides (v0.8)** - the decision recommendation payload is always the deterministic heuristic output; the LLM may only append rationale to `reasoning` and set `model`/`prompt_version`. Keep `plan-review` reproducible (no LLM); only `plan-improve` and the decide-CLI advice path call the model.
15. **Test factories are hermetic by default** - `SharedDbAppFactory` uses `Settings(_env_file=None)`; the dev `.env` (live AI config, tokens) must never leak into integration tests. Env vars set via `monkeypatch.setenv` still apply.

## Known Issues

1. **GitHub Actions expressions: single quotes ONLY** (2026-08-27, RESOLVED after 40+ dead runs) - `if: matrix.python-version == "3.11"` (double quotes) is a parse error at GitHub's expression layer: the run dies in 0s as `startup_failure` with ZERO jobs, workflow name shows as the file path, and no annotation is exposed via the check-runs API for this repo. gh's "workflow file issue" hint is a guess. Diagnosed by 14-smoke-workflow bisection: triggers/concurrency/matrix/needs/name-CI/setup-uv all innocent; the double-quoted `if` was the sole killer. Two stacked bugs had silenced CI since commit #1 (also: matrix was mis-indented under fail-fast). Rule: always single-quote string literals in `if:` expressions.
2. **pytest unraisable noise on Python 3.13.x** - `AttributeError('pathlib._local.PurePosixPath' has no '_tail_cached')` during GC of Path objects from earlier tests fails `error`-treated warnings on 3.13 (CI) but not 3.11/3.12. Mitigated with `ignore::pytest.PytestUnraisableExceptionWarning` in pyproject filterwarnings (environment artifact, not a leak).
2. **types-PyYAML** - not installed. mypy config suppresses import-untyped for yaml files.
3. **Export/sync legacy fallback** - DBs created before PlanStore (v0.4.1) export header-only plans; re-run `plan apply` to persist the raw plan.

## Communication Notes

- Parsa prefers Persian for conversation, English for code
- Address directly, no filler pleasantries
- Project directory: `C:\Users\Notebook\OneDrive\Desktop\Projects\Growth`
- Use `uv run` for all Python commands
- **Status tables after turns:** When working on long multi-step coding tasks, end each turn with a Persian summary table (✅ انجام شده / 🔄 در حال انجام / ⏳ باقی‌مانده) showing what was completed, what's in progress, and what remains. This keeps Parsa oriented during long sessions without needing to scroll back.
- **Resume work continuously (2026-08-12):** Parsa wants work to run end-to-end without piecemeal stops - do NOT ask "should I start?" between steps; pick up where the last session left off and push to completion (test → CI green → commit → push) in the same turn. Ask only when genuinely blocked on a decision.

## Session Log (2026-08-27) — v0.8 LLM-assisted decisions + review loop + CI resurrection ✅

- [x] `LlmDecisionEngine` (`application/llm_decisions.py`) + `PlanReviewer`/`PlanImprover` (`application/plan_review.py`) — both **100% covered** ✅
- [x] Bootstrap: `App.decision_engine` → LLM-wrapped over new `App.heuristic_decision_engine`; builtin steps + `plan-review`/`plan-improve`; CLI `decide` shows `[AI: model]` ✅
- [x] heuristic `_context` → `context` (port conformance, ruff ARG002 per-file ignore added)
- [x] `SharedDbAppFactory` hermetic (`Settings(_env_file=None)`) — dev .env had `GROWTH_AI_ENABLED=true` and would have hit the LLM from decide tests ✅
- [x] CI: 573 passed / 1 skipped, 98% (new files 100%), mypy 89 files, import-linter 3/3, ruff clean; pushed `bd37813` ✅
- [x] Live-verified with REAL 9Router + Kiro (`kr/deepseek-3.2`, running as of 23:54): `decide next-action` shows `[AI: kr/deepseek-3.2]` + advice; plan-review/plan-improve workflow ok ✅
- [x] **CI RESURRECTED** — GitHub Actions had NEVER run (0s startup failures since commit #1, ~45 runs): gh token was missing `workflow` scope (Parsa ran `gh auth refresh -s workflow`), then 14-smoke bisection isolated the double-quoted `if` expression; real pipeline restored `7f4a9b2`+`33289ef`; **first GREEN run 33117201856 (1m35s, py3.11/3.12/3.13)** — py313 needed the unraisable-warning ignore ✅
- [x] Docs: README v0.8 + decide/workflow command rows, CHANGELOG 0.8.0, ROADMAP v0.8 ✅

## Session Log (2026-08-26) — MEMORY fix + v0.7 complete + calendar bugfix ✅

- [x] MEMORY.md updated directly (Hermes policy: explicit user ask = ordinary file edit); committed `3d29ec7` with `git push 2>$null` → EXIT 0 (lesson applied) ✅
- [x] **v0.7 WorkflowEngine** shipped in 5 commits: `ccfffce` (engine core), `c234a8a` (YAML loader + CLI), `026cc4d` (CLI exit-code fix), `6efe145` (persistence + auto-load + list), `4d21ed5` (close-out: review-loop example + status docs) ✅
- [x] Live CLI verified: `workflow run daily-review` → ok (3 steps), `workflow run review-loop` → ok (5 steps), cross-process persistence works ✅
- [x] **Google Calendar production + bugfix**: app was already In production; fresh token issued (no expiry); `calendar list` failed with WinError 10060 → root cause: httplib2 0.32 + empty proxy env vars → fix `Http(proxy_info=None)` in `build_calendar_service` (commit `2e8d429`); live verified `calendar list` → EXIT 0 ✅
- [x] CI at close: 547 passed, coverage 98%, mypy 86 files, import-linter 3/3, 65 commits ✅

---

## Session Log (2026-08-20) - v0.7 DecisionEngine (part 1) ✅

- [x] `HeuristicDecisionEngine` (`infrastructure/decision/heuristic.py`) - real `DecisionEngine` impl: `next_action` (leaf-first, priority→due→effort→title), `blockers` (overdue), `priority_sort`; advisory-only, deterministic, reads via `TaskRepository` ✅
- [x] `App.decision_engine` lazy property + CLI `growth decide next-action|blockers|sort` ✅
- [x] 16 unit + 5 integration tests; CI: 514 passed, coverage 98%, mypy 83 files, import-linter 3/3; pushed `248cb48` ✅

---

## Session Log (2026-08-19) - v0.6 close-out ✅

- [x] Live LLM smoke test via 9Router + Kiro (`kr/deepseek-3.2`): `plan ai-apply` lifted free-text → 3 subjects/3 chapters; `knowledge extract --summarize` produced AI summary ✅
- [x] Provider field test: GitHub Models retired (410), OpenRouter geo-blocked Iran (403), Gemini standard keys deprecated → 9Router + Kiro is the only working path ✅
- [x] Close-out: README status → v0.6, CHANGELOG v0.2-v0.6, ROADMAP v0.6 → ✅ Complete, .gitignore cleanup (`.agents/`, `.obsidian/`, `.obsidian-mcp/`, `exports/`, `Growth.md`, `config/mcporter.json`), untracked `config/mcporter.json` (stays local) ✅
- CI: 493 passed, 1 skipped, coverage 98%, 81 files, 57 commits; pushed `9075986` ✅

---

## Session Log (2026-08-16) - v0.6 AI Integration (part 1) ✅

- [x] `LLMChat` port + `LLMUnavailableError`; `OpenAICompatibleChat` (httpx, Bearer auth, injectable MockTransport) ✅
- [x] `AiInterpreter` - free-text → prompt `growth-plan-json-v1` → JSON → CanonicalPlan; tolerant JSON parse; heuristic fallback; `DecisionArtifact` ✅
- [x] `PlanApplier.apply_payload()` refactor; CLI `plan ai-apply <text> [--apply]` (dry-run default) ✅
- [x] `DocumentParser` port + `PypdfParser` (pypdf via Aliyun mirror); `AiDocumentSummarizer`; `knowledge attach <pdf>` + `knowledge extract <file> [--summarize]`; schema migration (`content_text`/`summary`) ✅
- [x] Settings `GROWTH_LLM_*` + `GROWTH_AI_ENABLED` gate; container wiring ✅
- CI: 493 passed, 1 skipped, coverage 98%, 81 files ✅

---

## Session Log (2026-08-10)

### v0.2 Sync Engine - COMPLETE ✅

**Delivered:**
1. [x] Installed `todoist-api-python` ✅
2. [x] Replaced `TodoistAdapter` stub with real API adapter ✅
3. [x] IdentityMap (InternalId ↔ Todoist resource ID) ✅
4. [x] Differ - two-way snapshot diff → ChangeSet ✅
5. [x] SyncEngine - orchestrates project → diff → apply → persist ✅
6. [x] CLI: `growth sync todoist --dry-run` ✅
7. [x] Kernel bootstrap: App now wires IdentityMap + init_sync_state ✅
8. [x] Architecture: import-linter passes (3 contracts kept) ✅
9. [x] .env: renamed TODOIST_API_TOKEN → GROWTH_TODOIST_API_TOKEN ✅

**CI: ALL GREEN** - ruff ✅, mypy strict ✅ (54 files), import-linter ✅, pytest 87/87 ✅

**Remaining for v0.2 (as of 2026-08-12):**
- Real Todoist API end-to-end test (needs live token) - everything else shipped in v0.2.1/v0.3/v0.4 + this session's test sweep

---

## Session Log (2026-08-12)

### v0.3/v0.4 Test Sweep + Bugfixes - COMPLETE ✅

Parsa: «کار رو از سر بگیر همیشه» - no more piecemeal stops; resume and finish.

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

**CI: ALL GREEN** - ruff ✅, mypy strict ✅ (59 files), import-linter ✅ (3 contracts), pytest 256/256 ✅, coverage **98%**.

**Next:**
- v0.5 completion: Google Calendar projection (needs OAuth creds) <- **next**
- Real Todoist end-to-end test (needs live token)

---

## Session Log (2026-08-12) - v0.4 completion
## Session Log (2026-08-12) - Todoist SDK 4.0 hardening
## Session Log (2026-08-13) - OllamaEmbedder (v0.6 groundwork)

- [x] `infrastructure/embeddings/ollama.py`: httpx-based Ollama client, L2 normalized, all failure paths typed (`EmbeddingUnavailableError`) ✅
- [x] `SemanticSearch` now takes any `Embeddings` impl + offline fallback on `EmbeddingUnavailableError`; bootstrap wires Ollama when configured; 4 new tests; CI: 362 passed, coverage 98% ✅
## Session Log (2026-08-13) - Google Calendar LIVE ✅✅✅

- [x] Parsa: new Google Auth Platform UI - no heavy verification needed (leave domain/website fields empty; test user under Audience; scopes under Data Access; Desktop client under Clients) ✅
- [x] credentials.json copied to ~/.growth; GROWTH_GOOGLE_* paths added to .env (gitignored) ✅
- [x] OAuth consent flow completed (browser) → token.json saved ✅
- [x] **LIVE E2E**: `reminder add` (Persian title) → `calendar push` → event created in real Google Calendar; `calendar list` shows it with Tehran tz ✅
- [x] **BUGFIX: file_cache warning** - build(cache=None) still attempts oauth2client file-cache import; no-op cache object skips it; CLI output now clean ✅
- [x] 43 commits; CI: 420 passed, coverage 98%, import-linter 3/3; pushed `0a8ff98`/`4bc2cc8` ✅


## Session Log (2026-08-13) - ICS export (zero-auth calendar alternative)

- [x] Parsa: Google Cloud Console verification too heavy → built `IcsProjection` (RFC 5545): CRLF, escaping, folding, stable UIDs ✅
- [x] `App.export_calendar_ics()` + CLI `calendar export-ics`; imports into any calendar app without OAuth ✅
- [x] **BUGFIX: Windows CRLF translation** - `Path.write_text` wrote CR CR LF (corrupts .ics); `newline=''` + raw-bytes regression test ✅
- [x] 19 new tests; CI: 420 passed, coverage 98%, import-linter 3/3; pushed `ef04e56` ✅


## Session Log (2026-08-13) - Google Calendar layer (v0.5 code complete)

- [x] `infrastructure/adapters/calendar.py`: `GoogleCalendarAdapter` (service injected, narrow CRUD), `run_oauth_flow`, `build_calendar_service`, `ProviderUnavailableError` mapping ✅
- [x] `infrastructure/projections/calendar.py`: `CalendarProjection` - reminder → event payload (due_at start, +30 min, target in description) ✅
- [x] `application/calendar_sync.py`: `CalendarSync.push` - idempotent via IdentityMap provider=gcal (create → update, no dupes), skips past-due, failure isolation; new `IdentityMapPort` keeps application ring hexagonal (import-linter caught the first draft's infra import - fixed) ✅
- [x] CLI `calendar auth|push|list` + bootstrap `calendar_adapter`/`calendar_sync`/`authorize_calendar` ✅
- [x] Deps: google-api-python-client 2.198, google-auth-oauthlib 1.4 ✅
- [x] 39 new tests (projection, adapter w/ fakes, sync idempotency, CLI, bootstrap, console-safety entry point); CI: 401 passed, coverage 98%, import-linter 3/3; pushed `2f0ce45` ✅


## Session Log (2026-08-13) - console safety + cron dispatch

- [x] **BUGFIX: CLI emoji crash on Windows cp1252** - live `growth reminder sweep`/`plan show` crashed with UnicodeEncodeError (emoji in output AND in plan titles from user YAML data). Hardcoded CLI emoji → ASCII tokens; `run()` reconfigures stdout/stderr with `errors=replace` ✅
- [x] **Real scheduler dispatch**: cron job `Growth reminder sweep (daily)` (08:00 Asia/Tehran, session-bound) runs `growth reminder sweep` every day; announce-to-webchat delivery doesn't resolve (no configured channel), so the job is bound to the main session instead ✅
- CI: 362 passed, coverage 98% ✅

- [x] Settings `ollama_base_url` (None = offline) + `ollama_model` (bge-m3); bootstrap wires `App.ollama_embedder` when configured ✅
- [x] 11 new tests (port conformance, normalization, zero-vector, failures, env overrides, wiring); CI: 358 passed, coverage 98% ✅


- [x] Verified TodoistAdapter against installed SDK 4.0.0 (add_task/update_task/complete_task/get_tasks iterator all match) ✅
- [x] **BUGFIX: `is_completed` AttributeError** - SDK 4.x Task has `completed_at`, not `is_completed`; adapter now maps `completed_at is not None` + test covers done/open states ✅
- [x] E2E harness `tests/integration/test_todoist_e2e.py` (skipped w/o token; unique project + finally-cleanup) ✅
- [x] Lint cleanup for ruff 0.15 (zip strict, PLC0415, F841, B017, ARG005) ✅
- CI: 347 passed, coverage 98% ✅
- [x] **Live E2E PASSED** (Parsa supplied a real token via chat; env-var only, never persisted): create project/section/task → fetch → update+complete → verify via completed-tasks endpoint → delete cleanup. Documented API quirks (active-only get_tasks, 6-week window cap, by_completion_date for dateless tasks) ✅

### Semantic Search - COMPLETE ✅ (v0.4 done)

Parsa: «ادامه بده» - resumed immediately after the test sweep; no stop.

**Delivered:**
1. [x] **Embeddings port** (`application/ports/embeddings.py`) - seam for model-backed embedders in v0.6 ✅
2. [x] **LocalNGramEmbedder** (`infrastructure/embeddings/local.py`) - deterministic md5 char n-gram (2-4) hashing, 256-dim L2-normalized, sign trick; zero deps, offline ✅
3. [x] **SemanticSearch** (`infrastructure/storage/semantic_search.py`) - implements `KnowledgeSearch` port; cosine similarity + exact-keyword boost; MIN_SIM_SCORE=10 filters hash-collision noise (measured: noise ~0.07 sim vs real matches 0.47+); typo-tolerant (`roadmapp` → finds `roadmap`) ✅
4. [x] `App.semantic_search` wired in bootstrap; CLI `knowledge search --semantic` + unavailable-path error ✅
5. [x] Tests: embedder determinism/L2/typo, cosine, SemanticSearch ranking/space/limit/snippet, CLI flag (256 → **278 tests**) ✅

**CI: ALL GREEN** - ruff ✅, mypy strict ✅, import-linter ✅ (3 contracts), pytest 278/278 ✅, coverage **98%**.

**v0.4 = COMPLETE ✅** - knowledge substrate ships: attachments (content-addressed dedup) + keyword search + offline semantic search.

---

## Session Log (2026-08-02)

### Completed This Session

**Phase 0:**
- [x] Push code to remote ✅
- [x] Rename repo `placement-exam-todoist` → `growth` ✅ (Parsa did manually)
- [x] Delete empty `growth` repo on GitHub ✅ (Parsa did manually)
- [x] MEMORY.md created and populated ✅

**Phase 1:**
- [x] Integration tests for `plan_applier.py` (21% → **100%**) ✅ - 11 tests
- [x] Integration tests for CLI (24% → **97%**) ✅ - 11 tests
- [x] Coverage for `planning_repos.py` (51% → **97%**) ✅ - 24 new edge-case tests
- [x] Unit tests for `HeuristicInterpreter` (0% → **100%**) ✅ - 8 tests
- [x] Unit tests for `YamlParser` (0% → **100%**) ✅ - 8 tests
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
