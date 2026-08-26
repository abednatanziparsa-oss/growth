# Growth OS

**A personal growth operating system** — planning, knowledge management, learning, review, and execution in one cohesive system.

> **Status:** v0.7 — Decision & Workflow Engines: heuristic next-action/blockers/sorting, declarative YAML workflows (dry-run, cancelable, persisted), review-loop example.

---

## Quick Start

```bash
git clone https://github.com/abednatanziparsa-oss/growth
cd growth
uv sync --all-extras
uv run growth --version    # → growth-os 0.1.0.dev0
```

### Your first plan (30 seconds)

```bash
# Use the sample study plan from the archived MVP
uv run growth plan apply archive/v0-mvp/config/placement_exam.yaml

# See what was created
uv run growth plan show
uv run growth plan stats
```

---

## What It Does

Growth OS converts structured YAML study plans into a full task tree:

```
Your YAML
  ↓
Parser → PlanApplier → SQLite DB
  ↓           ↓
Interpreter  Projection (Todoist, Markdown, ...)
```

| Command | What it does |
|---|---|
| `growth plan apply <file>` | Parse a YAML plan and create workspace/project/goals/milestones/tasks |
| `growth plan ai-apply <text>` | Turn free-text into a structured plan via LLM (dry-run by default) |
| `growth plan show` / `stats` | Display the current plan tree / aggregate statistics |
| `growth sync todoist` | Two-way sync with Todoist (three-way diff + conflict detection) |
| `growth export markdown` | Export the current plan as Markdown |
| `growth knowledge attach/list/search` | Store, list, and search notes/files (keyword + semantic) |
| `growth knowledge extract <file>` | Parse a PDF and optionally AI-summarize it |
| `growth reminder add/list/due/sweep` | Create and manage reminders (recurring, scheduled) |
| `growth calendar auth/push/list/export-ics` | Push reminders to Google Calendar or export `.ics` |
| `growth --version` | Show installed version |

**Example YAML:**

```yaml
project_name: "Summer Study"

subjects:
  - name: "Python"
    emoji: "🐍"
    priority: "high"
    chapters:
      - name: "Async Programming"
        weak: true
      - name: "Type Hints"

standard_subtasks:
  - "Read Documentation"
  - "Write Examples"
  - "Build Mini-Project"
```

---

## Architecture

Growth OS follows **hexagonal (ports & adapters)** architecture with strict dependency enforcement:

```
domain ← application ← presentation
               ↖ kernel (composition root)
infrastructure → kernel
```

| Ring | Purpose |
|---|---|
| **domain/** | Pure model — Workspace, Project, Goal, Milestone, Task. No I/O, no framework deps. |
| **application/** | Use cases + ports (Protocols). 10 port interfaces defined. |
| **infrastructure/** | Adapters — SQLite repos, YAML parser, Todoist projection/adapter, config, logging. |
| **presentation/** | CLI via Typer. `growth plan apply/show/stats`. |
| **kernel/** | Composition root — manual DI wiring. |
| **plugins/** | Extension contract (Plugin protocol). |

Three import-linter contracts enforced in CI:
1. Domain has no outbound dependencies
2. Application depends only on domain
3. Presentation depends only on application + kernel

---

## CI Pipeline

| Check | Status |
|---|---|
| ruff (lint + format) | ✅ |
| mypy (strict mode, 81 source files) | ✅ |
| import-linter (3 hexagonal contracts) | ✅ |
| pytest (493 tests) | ✅ |
| coverage | ✅ 98% |
| Python 3.11 / 3.12 / 3.13 matrix | ✅ |

---

## Documentation

| Document | Description |
|---|---|
| [📖 Tutorial](docs/TUTORIAL.md) | Step-by-step user guide — **start here** |
| [🏗 Architecture](docs/architecture/ARCHITECTURE.md) | System design and dependency rules |
| [🗺 Roadmap](docs/ROADMAP.md) | v0.1 → v1.0 plan |
| [🤝 Contributing](docs/CONTRIBUTING.md) | How to contribute |
| [🦞 Luo Handoff](docs/LUO_HANDOFF.md) | Complete project map for the next agent |
| [⚙️ Dev Setup](docs/runbooks/development.md) | Dev environment and daily commands |
| [📝 ADRs](docs/adr/) | Architecture Decision Records (3) |
| [📋 Changelog](docs/CHANGELOG.md) | Release history |
| [🎨 Code Style](docs/CODE_STYLE.md) | Coding conventions and tooling rationale |

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Linting + Formatting | [ruff](https://docs.astral.sh/ruff/) (single tool) |
| Type checking | [mypy](https://mypy-lang.org/) (strict mode) |
| Architecture enforcement | [import-linter](https://github.com/seddonym/import-linter) |
| Testing | pytest + hypothesis |
| CLI framework | [Typer](https://typer.tiangolo.com/) |
| Config / Settings | Pydantic + python-dotenv |
| Logging | structlog |
| Storage | SQLite (file-based, ~/.growth/growth.db) |

---

## License

MIT © Parsa Abed
