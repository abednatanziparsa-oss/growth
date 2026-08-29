# Growth OS

**A personal growth operating system** â€” planning, knowledge management, learning, review, and execution in one cohesive system.

> **Status:** v0.9 - Plugin Marketplace (first v1.0 platform increment): local plugin discovery, validated manifests, install/uninstall lifecycle, startup activation with failure isolation.

---

## Quick Start

```bash
git clone https://github.com/abednatanziparsa-oss/growth
cd growth
uv sync --all-extras
uv run growth --version    # â†’ growth-os 0.1.0.dev0
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
  â†“
Parser â†’ PlanApplier â†’ SQLite DB
  â†“           â†“
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
| `growth decide next-action/blockers/sort` | Advisory recommendations (AI-enriched when `GROWTH_AI_ENABLED=true`) |
| `growth workflow register/run/list` | Declarative YAML workflows (plan review + AI improvement loop) |
| `growth plugin list/install/uninstall/info` | Install local plugins; they activate at startup (failure-isolated) |
| `growth --version` | Show installed version |

**Example YAML:**

```yaml
project_name: "Summer Study"

subjects:
  - name: "Python"
    emoji: "ðŸ"
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
domain â† application â† presentation
               â†– kernel (composition root)
infrastructure â†’ kernel
```

| Ring | Purpose |
|---|---|
| **domain/** | Pure model â€” Workspace, Project, Goal, Milestone, Task. No I/O, no framework deps. |
| **application/** | Use cases + ports (Protocols). 10 port interfaces defined. |
| **infrastructure/** | Adapters â€” SQLite repos, YAML parser, Todoist projection/adapter, config, logging. |
| **presentation/** | CLI via Typer. `growth plan apply/show/stats`. |
| **kernel/** | Composition root â€” manual DI wiring. |
| **plugins/** | Extension contract (Plugin protocol). |

Three import-linter contracts enforced in CI:
1. Domain has no outbound dependencies
2. Application depends only on domain
3. Presentation depends only on application + kernel

---

## CI Pipeline

| Check | Status |
|---|---|
| ruff (lint + format) | âœ… |
| mypy (strict mode, 81 source files) | âœ… |
| import-linter (3 hexagonal contracts) | âœ… |
| pytest (493 tests) | âœ… |
| coverage | âœ… 98% |
| Python 3.11 / 3.12 / 3.13 matrix | âœ… |

---

## Documentation

| Document | Description |
|---|---|
| [ðŸ“– Tutorial](docs/TUTORIAL.md) | Step-by-step user guide â€” **start here** |
| [ðŸ— Architecture](docs/architecture/ARCHITECTURE.md) | System design and dependency rules |
| [ðŸ—º Roadmap](docs/ROADMAP.md) | v0.1 â†’ v1.0 plan |
| [ðŸ¤ Contributing](docs/CONTRIBUTING.md) | How to contribute |
| [ðŸ¦ž Luo Handoff](docs/LUO_HANDOFF.md) | Complete project map for the next agent |
| [âš™ï¸ Dev Setup](docs/runbooks/development.md) | Dev environment and daily commands |
| [ðŸ“ ADRs](docs/adr/) | Architecture Decision Records (3) |
| [ðŸ“‹ Changelog](docs/CHANGELOG.md) | Release history |
| [ðŸŽ¨ Code Style](docs/CODE_STYLE.md) | Coding conventions and tooling rationale |

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

MIT Â© Parsa Abed
