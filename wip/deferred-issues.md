# Deferred issues

Running list of things intentionally postponed during the recursive-building work ([recursive/design.md](recursive/design.md)). Each is a deliberate "later", not a bug.

## Flatten multi-file library into a single bundle (deferred)

The recursive builder produces a **multi-file library** — one `.mthds` file per pipe, all in the same domain (see `recursive/design.md` §2.7). We keep small files for now.

Later, consider an optional final **flatten** step that concatenates all pipes/concepts into a single `bundle.mthds` for portability and readability. It is trivial by construction: the one-pipe-per-file convention guarantees zero code collisions, so flattening is a straight union of declarations under one `domain` header (keeping a single `main_pipe`). Offer it as a delivery option; do not make it mandatory — method packages already support multi-file libraries.

## Substitutable contract conformance for signature/concrete reconciliation (deferred)

The pipelex relaxation that lets a concrete pipe satisfy a `PipeSignature` of the same code (plan: `_recursive/TODOS.md`; code in `pipelex/libraries/library_crate_factory.py`) checks contract conformance with **exact string match** at merge time for v1.

Later, consider **true substitutability (LSP)** instead of exact match:

- *Output covariant* — the definition may produce a type that *refines* the declared output (header `Text`, definition `Summary` where `Summary refines Text`).
- *Inputs contravariant* — the definition may accept *wider* inputs than declared (header `Document`, definition `Anything`), but not narrower.
- *Multiplicity stays exact.*

Why deferred: substitutability needs the resolved concept-refinement graph, which doesn't exist at the blueprint-level merge — so it would have to move to a post-instantiation validation pass. Exact match is conservative (only rejects, never wrongly accepts) and machine-generated builds emit identical spelling, so it doesn't bite the recursive flow. Revisit if hand-authored multi-file libraries need refinement-compatible swaps. Full rationale: the "Contract conformance" section of `_recursive/TODOS.md`.

## Related

- [revisit-vibe-scope-limits.md](revisit-vibe-scope-limits.md) — deferred decision on lifting vibe's `dict` / `PipeStructure` scope limits.
