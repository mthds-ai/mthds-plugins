# Skill-behavior eval harness for `mthds-vibe` (deferred design doc)

Status: **deferred** — captured during the eng review of [design.md](design.md) (2026-06-07, decision D7). Not part of the recursive-building v1; build separately. v1 ships dogfood-only (see [TODOS.md](../../TODOS.md) Phase 6.3).

## Problem

The recursive rewrite of `mthds-vibe` (design.md Phase 4) is a large LLM-prompt change. The plugin has **no automated skill-behavior tests** today — the `internal-tools` Docker suite tests the hook/install system, not what a skill actually produces. So a prompt regression in the skill (a layer that stops fanning the backlog correctly, a lazy-concept rule that structures too eagerly, a contract-mismatch recovery that edits the header instead of the definition) would only surface when a human notices a bad build.

## What an eval would do

Exercise the recursive loop end-to-end against a small set of **golden methods** and score the result:

- **Seed golden case:** the §3 `research_brief` example (Document → ResearchBrief, one inline operator layer + one multi-signature layer). It is already fully specified in design.md §3, so the expected call tree, the lenient-per-layer transitions, and the final strict-pass are known.
- **Scoring dimensions (sketch):** does the final library pass strict validation (runnable)? does every intermediate save pass lenient validation? does the call tree match the expected shape? are boundary concepts specified at Layer 0 and intermediate concepts introduced lazily? did contract-mismatch recovery conform the definition (not the header)?
- **Regression guard:** re-run on every edit to `templates/skills/mthds-vibe/SKILL.md.j2` so skill-prompt changes are safe to ship.

## Why deferred (not built now)

The plugin has no eval infrastructure. A harness + golden-method corpus + scoring rubric is its own project, disproportionate to bolt onto the recursive-building PR. Capturing the gap here (with the seed case) is the right-sized move; building it is separate work.

## Open questions for the eval design

- Harness shape: a pytest-driven runner that spawns the skill via the Agent/Claude SDK, or a lighter golden-transcript diff?
- Scoring: deterministic structural checks (call tree, validation transitions) vs an LLM-judge for the fuzzy quality dimensions — or both.
- Corpus: how many golden methods, and across what shapes (deep-sequence, wide-batch, branching `PipeCondition`)?
- CI cost: skill evals invoke a model; gate on cost/cadence (every PR vs nightly).

## Related

- [design.md](design.md) — the recursive-building design (§3 worked example = the seed case; §4 the skill being evaluated).
- [TODOS.md](../../TODOS.md) Phase 6.3 — the v1 dogfood checklist this eval would eventually automate.
