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

## Related

- [revisit-vibe-scope-limits.md](revisit-vibe-scope-limits.md) — deferred decision on lifting vibe's `dict` / `PipeStructure` scope limits.
