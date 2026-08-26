# Growth OS Roadmap

## v0.1 — Planning Core
- Domain aggregates: Workspace, Project, Goal, Milestone, Task
- SQLite repositories via `growth.infrastructure.storage`
- YAML parser + HeuristicInterpreter
- Todoist adapter + TodoistProjection (evolved from MVP code)
- Real `growth plan apply` CLI

## v0.2 — Sync Engine
- Three-way diff (intended → projected → remote)
- IdentityMap (InternalId ↔ provider resource id)
- Conflict detection + resolution per field
- `growth sync` CLI

## v0.3 — Markdown Export
- Markdown adapter (file-system, not API)
- `Projection` writes working-copy Markdown files
- `growth export` CLI

## v0.4 — Knowledge Substrate
- Attachment storage (files, URLs, notes)
- Embedding generation (local-only by default)
- Full-text + semantic search
- Knowledge-aware interpretation (parsers read knowledge assets)

## v0.5 — Reminders & Scheduling
- Schedule calculation (due dates, recurrence)
- Notification layer (desktop, push)
- Google Calendar adapter + projection

## v0.6 — AI Integration
- LLMChat port + OpenAI-compatible backend (9Router + Kiro primary from Iran)
- Ollama backend (local, offline-first) via the Embeddings port
- PDF parser (pypdf) + AI-assisted document summarization
- AI-assisted plan interpretation (`plan ai-apply`)

## v0.7 — Decision & Workflow Engines — Complete ✅
- DecisionEngine: next-action, blockers, priority sorting ✅
- WorkflowEngine: declarative YAML workflows, dry-run, cancelable, persisted (`~/.growth/workflows`) ✅
- Review loop: execution → review shipped as `examples/workflows/review-loop.yaml`; planning/improvement advisory (LLM-assisted later) ✅

## v1.0 — Platform
- Plugin marketplace
- Desktop app (PySide6)
- GraphQL API
- Multi-user spaces

## Current Status

| Phase | Status |
|---|---|
| v0.1 – v0.5 | ✅ Complete (planning, sync, export, knowledge, reminders + Google Calendar + ICS) |
| v0.6 | ✅ Complete — LLM chat + AI interpreter + PDF parser + live smoke test (9Router + Kiro, `kr/deepseek-3.2`) |
| v0.7 | ✅ Complete — heuristic Decision Engine + declarative Workflow Engine (dry-run, cancelable, persisted) + review-loop example |
| v1.0 | ⏳ Not started |
