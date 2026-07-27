# Growth OS Tutorial

A step-by-step guide to using Growth OS v0.1.

## 1. Installation

```bash
git clone https://github.com/abednatanziparsa-oss/growth
cd growth
uv sync --all-extras
```

Verify it works:

```bash
uv run growth --version
# → growth-os 0.1.0.dev0
```

## 2. Your First Plan

Growth OS reads YAML study plans and creates a structured task tree.
Create a file called `my_plan.yaml`:

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
        weak: false
  - name: "Rust"
    emoji: "🦀"
    priority: "medium"
    chapters:
      - name: "Ownership"
        weak: true
      - name: "Traits"
        weak: false

standard_subtasks:
  - "Read Documentation"
  - "Write Examples"
  - "Build Mini-Project"

extra_sections:
  - "Final Review"
```

## 3. Apply the Plan

```bash
uv run growth plan apply my_plan.yaml
```

Output:
```
[OK] Applied: Summer Study Workspace
   Projects: 1
   Goals: 2
   Milestones: 4
   Tasks: 4
```

## 4. View Your Plan

```bash
uv run growth plan show
```

Output:
```
📁 Summer Study Workspace
  📦 Summer Study
    🎯 🐍 Python (high)
      📌 Async Programming
      📌 Type Hints
    🎯 🦀 Rust (medium)
      📌 Ownership
      📌 Traits

  📋 Tasks (4 top-level):
    ⬜ Async Programming
    ⬜ Type Hints
    ⬜ Ownership
    ⬜ Traits
```

## 5. Check Statistics

```bash
uv run growth plan stats
```

Output:
```
Workspaces:  1
Projects:    1
Goals:       2
Milestones:  4
Tasks:       4 (0 completed)
```

## 6. How It Works

When you run `growth plan apply`, Growth OS:

1. **Parses** the YAML file
2. **Creates** a Workspace and Project
3. **Creates** a Goal per subject (with emoji + priority)
4. **Creates** a Milestone per chapter
5. **Creates** a parent Task per chapter + subtasks per template

Everything is stored in a local SQLite database at `~/.growth/growth.db`.

## 7. Plan Schema Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `project_name` | string | yes | Display name for the project |
| `subjects` | list | yes | Subject categories |
| `subjects[].name` | string | yes | Subject name |
| `subjects[].emoji` | string | no | Emoji prefix (e.g. "🐍") |
| `subjects[].priority` | string | no | `urgent` / `high` / `medium` / `low` |
| `subjects[].chapters` | list | no | Chapters within the subject |
| `subjects[].chapters[].name` | string | yes | Chapter title |
| `subjects[].chapters[].weak` | bool | no | If true, priority = `high` |
| `standard_subtasks` | list | no | Subtask templates for each chapter |
| `extra_sections` | list | no | Additional goal titles |

## 8. Architecture Tour

See [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for the full design.
Quick overview:

```
Your YAML → Parser (YamlParser) → PlanApplier (use case) → SQLite DB
                  ↓
           Interpreter (HeuristicInterpreter)
                  ↓                ↓
        Projection (Todoist)   Adapter (TodoistAdapter)
```

## 9. What's Next

- **v0.2**: Sync engine (push plans to Todoist)
- **v0.3**: Markdown export
- **v0.4**: Knowledge substrate (notes, attachments, search)
- **v0.6**: AI integration (Ollama/OpenAI/Anthropic)

See [ROADMAP.md](docs/ROADMAP.md) for the full plan.

## 10. Development

```bash
make test         # run all tests
make typecheck    # mypy strict
make lint         # ruff check
make ci           # full CI pipeline
```

Run tests: `uv run pytest tests/ -v`
