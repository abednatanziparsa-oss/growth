# Growth OS

**A personal growth operating system** — planning, knowledge management, learning, review, and execution in one cohesive system.

> **Status:** v0.1 — domain aggregates, SQLite persistence, YAML plans, and CLI. Ready for real use.

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
| `growth plan apply <file>` | Parse a YAML study plan and create workspace/project/goals/milestones/tasks |
| `growth plan show` | Display the current plan tree |
| `growth plan stats` | Show aggregate statistics (goals, milestones, tasks completed/total) |
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
| mypy (strict mode, 50 source files) | ✅ |
| import-linter (3 hexagonal contracts) | ✅ |
| pytest (25 tests) | ✅ |
| Python 3.11 / 3.12 / 3.13 matrix | ✅ |

---

## Documentation

| Document | Description |
|---|---|
| [📖 Tutorial](docs/TUTORIAL.md) | Step-by-step user guide — **start here** |
| [🏗 Architecture](docs/architecture/ARCHITECTURE.md) | System design and dependency rules |
| [🗺 Roadmap](docs/ROADMAP.md) | v0.1 → v1.0 plan |
| [🤝 Contributing](docs/CONTRIBUTING.md) | How to contribute |
| [⚙️ Development Setup](docs/runbooks/development.md) | Dev environment and day-to-day commands |
| [📝 ADRs](docs/adr/) | Architecture Decision Records (3) |

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
