# ADR 0002: Knowledge-Centric Architecture

**Status:** Accepted
**Date:** 2026-07-17

## Context

The initial architecture positioned Growth as a "planner" — a tool that schedules
tasks. The architecture review identified this as too narrow: a personal growth
operating system needs a knowledge layer (attachments, notes, embeddings) as its
foundation, with planning and execution as consumers of that knowledge.

## Decision

Reposition the conceptual model around **three linked domains**:

1. **Knowledge** — raw inputs, attachments, embeddings, search
2. **Planning** — structured plans, goals, milestones, tasks
3. **Execution** — provider synchronization, reminders, status tracking

Knowledge is the canonical home of information. Planning references knowledge
assets. Execution projects plans onto providers.

The Decision Engine and Workflow Engine are **advisory only** — they produce
recommendations and trigger flows, but never mutate state directly. This
prevents them from becoming god objects.

## Consequences

- Knowledge substrate (v0.4–0.6) is foundational, not optional
- AI integration (v0.6) becomes a knowledge consumer, not an autonomous agent
- Decision Engine produces audit artifacts (DecisionArtifact) for every recommendation
- Workflow Engine is declarative and cancelable, not hidden automation
