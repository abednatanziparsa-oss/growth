# Growth - Placement Exam

A small Python tool that builds the **"Growth - Placement Exam"** project in
your Todoist account from a single YAML study plan: project, subject
sections, one parent task per chapter, and standard subtasks (Study /
Exercises / Sample Questions / Mistakes / Review) under each chapter.

It is intentionally focused — it does exactly one job, with a dry-run mode
and a CSV backup so you're never locked in.

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy the example environment file and add your Todoist API token
cp .env.example .env
#   then edit .env and paste your token from
#   Todoist -> Settings -> Integrations -> Developer

# 3. Preview what would be created (no network calls)
python -m placement_exam.main --dry-run

# 4. When the preview looks right, push to Todoist
python -m placement_exam.main
```

You need **Python 3.11+** and a Todoist account.

---

## How it works

```
config/placement_exam.yaml   <- you edit this (the source of truth)
            │
            ▼
   placement_exam.main       <- validates + drives the client
            │
            ├──► DryRunClient      (with --dry-run: prints only)
            └──► TodoistClient     (real: calls the Todoist REST API)
```

Both clients expose the same three methods (`add_project`, `add_section`,
`add_task`), so the orchestration logic is identical in preview and real
mode.

### What gets created in Todoist

```
Growth - Placement Exam
├── 📘 Mathematics
│   ├── ⚠ Sets                         (P1, weak)
│   │   ├── Study Concepts
│   │   ├── Textbook Exercises
│   │   ├── Sample Questions
│   │   ├── Mistakes Analysis
│   │   └── Review
│   ├── ⚠ Trigonometry                 (P1, weak)
│   │   └── ...
│   └── Functions                      (P1, normal)
│       └── ...
├── 📐 Geometry
├── ⚛ Physics
├── 🧪 Chemistry
├── 🔄 Mistake Fix                     (empty section)
└── ✅ Final Review                    (empty section)
```

Weak chapters are prefixed with `⚠` and forced to **P1** priority so they
bubble up in Today / Upcoming views.

---

## Editing your study plan

Open `config/placement_exam.yaml`. Each subject becomes a section; each
chapter becomes a parent task with the five standard subtasks under it.

```yaml
subjects:
  - name: "Mathematics"
    emoji: "📘"
    priority: 4              # 4=P1, 3=P2, 2=P3, 1=P4
    chapters:
      - name: "Sets"
        weak: true           # weak -> forced to P1, gets a ⚠ prefix
      - name: "Functions"    # normal chapter
```

- **`priority`** follows Todoist: `4` = Highest (P1) → `1` = Lowest (P4).
- **`weak: true`** overrides the subject priority and marks the chapter.
- Empty `chapters: []` is fine — the section is still created.

---

## CLI reference

```bash
# Preview only (no API calls, no token needed)
python -m placement_exam.main --dry-run

# Real run — creates everything in Todoist
python -m placement_exam.main

# Use a different plan file
python -m placement_exam.main --config path/to/other.yaml

# Only project + sections (no tasks) — useful for a fresh re-structure
python -m placement_exam.main --structure-only

# Also write a CSV backup you can import manually into Todoist
python -m placement_exam.main --csv
python -m placement_exam.main --csv custom/path.csv
```

The CSV export is Todoist-importable (Template → Import CSV in the Todoist
web app). It's a fallback for when the API is unavailable.

---

## Project layout

```
placement_exam/
├── __init__.py
├── main.py              # CLI + orchestration + CSV export
├── models.py            # dataclasses: StudyPlan, Subject, Chapter
├── plan_loader.py       # YAML loading + validation
├── dry_run.py           # simulated client (prints, no network)
└── todoist_client.py    # real Todoist SDK wrapper
config/
└── placement_exam.yaml  # ← edit this
requirements.txt
.env.example             # ← copy to .env and add your token
```

---

## Troubleshooting

**`Todoist API token is empty`**
You ran without `--dry-run` and no token was found. Either export
`TODOIST_API_TOKEN` in your shell, or create a `.env` file (see
`.env.example`).

**`Failed to create ... : ...`**
The API returned an error. Common causes: invalid token, rate limited, or
network issue. Partially created items stay in Todoist — re-run with
`--structure-only` first to confirm the project shell exists, then decide
what to clean up manually.

**Duplicate run**
The tool does **not** de-duplicate. If you run it twice, you'll get two
projects. Delete the old one in Todoist first, or rename
`project_name` in the YAML.

---

## Scope (what this tool does *not* do)

By design, to stay focused before the exam:

- ❌ No automatic due dates (add them in Todoist after creation).
- ❌ No daily scheduler / recurring tasks.
- ❌ No Obsidian or Hermes Agent integration (postponed per Growth.md).
- ❌ No automated tests yet (MVP first; tests after the exam).

These are tracked as future work in `ROADMAP.md`.
