# Deferred issues

Running list of things intentionally postponed during the recursive-building work ([recursive/design.md](recursive/design.md)). Each is a deliberate "later", not a bug.

## Flatten multi-file library into a single bundle (deferred)

The recursive builder produces a **multi-file library** — one `.mthds` file per pipe, all in the same domain (see `recursive/design.md` §2.7). We keep small files for now.

Later, consider an optional final **flatten** step that concatenates all pipes/concepts into a single `bundle.mthds` for portability and readability. It is trivial by construction: the one-pipe-per-file convention guarantees zero code collisions, so flattening is a straight union of declarations under one `domain` header (keeping a single `main_pipe`). Offer it as a delivery option; do not make it mandatory — method packages already support multi-file libraries.

## Substitutable contract conformance for signature/concrete reconciliation (deferred)

The pipelex relaxation that lets a concrete pipe satisfy a `PipeSignature` of the same code (plan: `_recursive/TODOS.md`; code in `pipelex/libraries/contract_match.py`, called from `pipelex/libraries/library_crate_factory.py`) checks contract conformance by **normalized concept identity** at merge time (bare↔qualified, native, structural multiplicity — shipped; see the Note below). It does **not** do refinement-aware substitutability.

Later, consider **true substitutability (LSP)** instead of identity match:

- *Output covariant* — the definition may produce a type that *refines* the declared output (header `Text`, definition `Summary` where `Summary refines Text`).
- *Inputs contravariant* — the definition may accept *wider* inputs than declared (header `Document`, definition `Anything`), but not narrower.
- *Multiplicity stays exact.*

Why deferred: substitutability needs the resolved concept-refinement graph, which doesn't exist at the blueprint-level merge — so it would have to move to a post-instantiation validation pass. Identity match is conservative (only rejects, never wrongly accepts), so it doesn't bite the recursive flow. Revisit if hand-authored multi-file libraries need refinement-compatible swaps. Full rationale: the "Contract conformance" section of `_recursive/TODOS.md`.

> Note: the *raw-string → normalized* upgrade of the contract check (bare↔qualified, native, structural multiplicity — identity, not refinement) has **shipped** (`_recursive/HANDOFF-recursive-followups.md` Task 2). Only the refinement-aware substitutability above stays deferred.

## Concept-name collisions across parallel workers (deferred — observe first)

Part A reconciles a pipe *signature* with its *concrete* (the C-header model), so parallel workers adding pipe **definition** files never collide on pipe codes. But **intermediate concepts** have no signature form: two sibling workers in the same fan-out layer, each expanding a controller, can independently introduce an intermediate concept with the same code in the same domain → a hard `ConceptLibraryError` at the layer's lenient validation (design.md §4.4 "Contract & collisions").

The additive model can't cheaply recover by renaming — that means editing already-written files and every reference, the very thing additive avoids. Candidate fixes (none chosen): the orchestrator **pre-allocates** concept namespaces/prefixes per worker before dispatch; workers derive concept codes deterministically from their own pipe code; or a concept-level reconciliation for byte-identical declarations.

**Deferred on purpose:** the user wants to **see the collision happen in a real recursive build first**, to design the right fix against an actual case rather than speculatively. Until then the hard `ConceptLibraryError` is the loud, safe backstop.

## Domain metadata merge under the additive model (DONE — pipelex)

Non-root definition files carry only `domain = "<same_domain>"` (membership), omitting `description`/`system_prompt`. The old domain-metadata merge was first-write-wins + warn-on-difference, so an omitted field read as a conflicting empty value: it emitted a spurious "different descriptions" warning per sibling per validation (at two layers), and was load-order-dependent (an empty-description sibling merged before the root discarded the root's real description). `main_pipe` was **not** affected (it never propagates to the runtime `Domain`).

**Shipped** on `feature/Support-recursive-design` (commit `aadf86d5`): a shared `merge_domain_metadata_field` helper, wired from both `LibraryCrateFactory.make_from_blueprints` and `DomainLibrary.add_domain`, merges order-independently and treats an omitted field as "no opinion" (warns only on two genuinely different non-empty values). Non-root files can now carry only `domain = "..."` with no warnings, and the root's header always wins. Full record: `_recursive/HANDOFF-domain-metadata-merge.md`.

## Fan-out / parallel signature expansion + the `agents/` plugin component (deferred to follow-up)

Decided during the eng review of [recursive/design.md](recursive/design.md) (2026-06-07, decision D1). The recursive builder's parallel fan-out — the dedicated `mthds-signature-expander` worker spawned per pending signature on a multi-signature layer (design.md §4.4) — is **deferred to a follow-up PR**. v1 runs the layer loop **inline/serial on both targets** (Claude and Codex); correctness is identical, only per-layer parallelism and per-signature context isolation are dropped.

What's deferred with it (the whole of the original Phase 3):

- The `mthds-signature-expander` worker agent (`templates/agents/mthds-signature-expander.md.j2`) and the `expand-signature` shared partial (`templates/skills/shared/expand-signature.md.j2`) — in v1 the expansion instructions live **inline** in the skill's Step 2 (single consumer; a shared partial would be premature abstraction).
- The build-system support for a new `agents/` component class: `scripts/gen_skill_docs.py` (`AGENT_TEMPLATES` + a per-platform gate mirroring `HOOK_TEMPLATES_BY_PLATFORM`), `scripts/check.py` (a no-`agents/`-in-Codex guard), and the freshness/orphan scanning for `agents/`.
- The **open auto-discovery question**: does Claude Code auto-discover a plugin's `agents/` directory, or is a `plugin.json`/manifest field required? This is unanswered and is one reason the fan-out chunk was pulled out of v1.

Why deferred: it is the single most novel/risky piece of the project (a component class the build system has never emitted), it carries the unanswered auto-discovery question, and the design itself already gates it behind `{% if platform != "codex" %}` — so re-introducing it later is a localized template change. Ship the correct recursive loop first; add parallelism as a fast-follow once real builds show whether per-signature context isolation matters.

When fan-out lands, also re-introduce the parallel-worker concept-collision handling (the section above) — serial v1 prevents collisions up front (check-before-introduce; design.md §4.4 / decision D5), which does not cover concurrent siblings.

## Codex hook leftover-signature nudge (deferred to follow-up)

The Claude bash hook emits a **non-blocking** `additionalContext` nudge on a lenient-valid save that still has unimplemented signatures, listing the `pending_signatures` (Phase 1.2). The Codex hook (`mthds-agent codex hook` in `mthds-js/src/agent/commands/codex-hook.ts`) ships only `--allow-signatures` for v1 (Phase 5.1) — **no equivalent nudge**.

Why deferred: the Codex hook only inspects validate output **on failure** and reads errors as **markdown on stderr**, which `classifyStage3Result()` greps. Adding a success-path `pending_signatures` note means reading the **success** envelope, which requires `--format json` — and on the pipelex CLI `--format` *inherits into* `--error-format` unless `--error-format markdown` is also pinned, so it re-opens the exact error-format coupling the Claude side had to solve (the two-stream pinning, mthds-plugins CLAUDE.md §"`--format` vs `--error-format`"). For v1 it's not worth that risk: the orchestrator skill tracks `pending_signatures` itself, so the nudge is redundant guidance, not a correctness gate.

When picked up: mirror the Claude approach — pass `--allow-signatures --format json --error-format markdown` in `runPipelexValidate`, parse `pending_signatures` from the JSON success stdout, and emit a non-blocking `additionalContext` listing them (no `decision`). The `classifyStage3Result()` markdown-on-stderr path stays unchanged because `--error-format markdown` is pinned. Extend `codex-hook.test.ts` (the DI `runPipelexValidate` mock would need to return stdout too).

## Related

- [revisit-vibe-scope-limits.md](revisit-vibe-scope-limits.md) — deferred decision on lifting vibe's `dict` / `PipeStructure` scope limits.
- [recursive/eval-harness.md](recursive/eval-harness.md) — deferred skill-behavior eval harness (decision D7); v1 ships dogfood-only.
