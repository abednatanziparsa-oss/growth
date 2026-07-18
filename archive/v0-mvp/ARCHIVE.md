# Archived: v0 MVP — Placement Exam Todoist Synchronizer

This directory contains the **original MVP** that the Growth OS project grew
out of. It is preserved here for reference and for the legacy YAML schema
(which the v0.1 planner will learn to read back during the migration phase).

**Status:** Frozen. Do not edit. Do not depend on from new code.

**Original purpose:** A small, focused Python tool that built the
"Growth - Placement Exam" project in Todoist from a single YAML study plan:
project, subject sections, one parent task per chapter, and standard
subtasks (Study / Exercises / Sample Questions / Mistakes / Review) under
each chapter.

**What this MVP proved** (and what informed the new architecture):
- The vertical slice is valuable: YAML → plan → Todoist.
- The duck-typed `DryRunClient` / `TodoistClient` interface validated the
  adapter pattern.
- Its core weakness — domain model shaped like Todoist (priorities 1–4,
  emoji section names, `build_plan` interleaved with API calls) — is exactly
  what the new architecture exists to correct.

**Why it was archived rather than kept:**
Keeping two layouts at the repository root (the old `placement_exam/`
package and the new `src/growth/` package) would confuse tooling, tests,
and future contributors. The v0.1 phase rebuilds this behavior through
the clean hexagonal architecture from scratch.

**Contents:**
- `placement_exam/` — the original Python package (5 modules)
- `config/placement_exam.yaml` — the original study plan (source of truth)
- `requirements.txt`, `.env.example` — original environment
- `README.md`, `PROJECT_RULES.md` — original docs
- `docs/archive/` — the original aspirational architecture/roadmap docs

For the current architecture, see `/docs/architecture/ARCHITECTURE.md`.
For the roadmap, see `/ROADMAP.md`.
