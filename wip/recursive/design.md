# Recursive Method Building — Design Doc

Origin: [kick-off.md](kick-off.md). This doc turns that kick-off into a methodology and a concrete skill design.

## TL;DR

Build a `.mthds` method **top-down by stepwise refinement**, where every intermediate state is a real, validatable library (a set of same-domain `.mthds` files, one pipe per file). Start by capturing the whole job as a *single pipe signature* — the client contract (inputs, output, semantics). Then refine one signature at a time, one level down, into operators and controllers, leaving the not-yet-built parts as further signatures. Validate **leniently** (`--allow-signatures`) after each layer; the library is always valid and always resumable. Stop when no signatures remain (strict validation passes → runnable), or stop early and keep the leniently-valid scaffold.

This is an **in-place evolution of `mthds-vibe`**: its current single-pass authoring becomes recursive layer-by-layer refinement.

The capability that unlocks this shipped in pipelex (the `PipeSignature` pipe type + `--allow-signatures` lenient validation, worktree `../_recursive`). It is already reachable through `mthds-agent` today via flag passthrough — no CLI plumbing required. The one piece of tooling that must change is the PostToolUse hook (see [Required tooling changes](#required-tooling-changes)).

## Decisions taken

These were confirmed before writing (recorded here for handoff):

- **Doc scope** — methodology first, then concrete skill design (this doc).
- **Skill identity** — evolve `mthds-vibe` in place; the staged `mthds-build` stays separate.
- **Autonomy** — *optionally hybrid*: the requirements-capture step (the top signature) is interactive only when the request is ambiguous or the user signals they want to discuss; otherwise the agent commits to its read and proceeds. The recursive refinement that follows runs in **auto mode**.
- **Stop / output** — refine to runnable by default (strict validation passes, no signatures left), but support stopping early and delivering a leniently-valid scaffold.

---

## 1. Background & motivation

`mthds-vibe` today writes a complete `bundle.mthds` in **one pass**, then validates and iterates on errors (see `templates/skills/mthds-vibe/SKILL.md.j2`). That works for small methods. For non-trivial ones it asks the model to get the entire tree right at once — deep nesting, every intermediate concept, all controller wiring — and that is exactly where single-pass authoring breaks down, with errors that could be anywhere in the bundle.

`mthds-build` answers this with a heavyweight staged process: draft a plan in markdown, draft concepts, structure them via CLI, draft the flow, structure pipes — designing the *whole* architecture before any of it is a live bundle. The design lives in prose until late; the artifact isn't machine-checked until the structuring phases.

Recursive building takes a third path, enabled by a new primitive:

> A `PipeSignature` is a pipe declared by its **contract only** — `description`, `inputs`, `output`, and an optional `signature_for` hint — with no implementation. **Lenient validation** (`--allow-signatures`) accepts a bundle whose dependency graph reaches signatures: each signature dry-runs by minting a mock output of its declared type. Strict validation (the default) rejects any reachable signature; live execution of a signature always fails (`PipeSignatureNotExecutableError`).

Because a partially-designed method is now a **real bundle that validates**, design becomes a sequence of always-valid states. You commit to the contract first (the part the client actually cares about and can check against requirements), then fill in the implementation incrementally, validating each layer. Errors are localized to the layer you just added.

### Signature syntax (reference)

```toml
[pipe.summarize_doc]
type          = "PipeSignature"
description   = "Produce a summary of a document (contract only)."
inputs        = { doc = "Document" }
output        = "Summary"
signature_for = "PipeLLM"   # optional hint: the intended implementation type
```

- No implementation fields (no `prompt`, `steps`, `branch_pipe_code`, …) — the signature is purely the contract.
- `signature_for` records the intended next-level type (`PipeSequence`, `PipeLLM`, `PipeBatch`, …). It may not be `"PipeSignature"`. It is a *hint*, not a binding contract — a refinement step may override it.
- Multiplicity (`[]`, `[N]`) works on `inputs` and `output` like any pipe.

---

## 2. The methodology

### 2.1 Core idea — stepwise refinement with an always-valid artifact

The whole process is one invariant plus one operation, repeated:

- **Invariant** — at every checkpoint, the library on disk (every `.mthds` file in the domain) passes lenient validation (`--allow-signatures`).
- **Operation (a refinement step)** — replace one signature with its implementation *one level down* (overwrite that pipe's own file), then re-validate.

You never design more than one level at a time, and you never hold an invalid artifact.

### 2.2 Layer 0 — the whole job as one signature

Capture the client requirement as a single `PipeSignature` whose code is the bundle's `main_pipe`. This fixes three things that *are* the requirements:

- **Input concept(s)** — what the client provides.
- **Output concept** — what the client gets back.
- **Description** — the semantics: what the job means, in prose precise enough to implement against.

Define the **boundary concepts fully at Layer 0** — the top input and output concepts are the client-facing data contract, so specify their structure now. Intermediate concepts come later, lazily.

Validate leniently → the one-signature bundle passes. This is the foundation; getting it right matters more than anything downstream.

### 2.3 The refinement step — operator or controller

Each signature `S` on the work-list is resolved to exactly one of two shapes, one level down:

- **Operator (leaf)** — `S` is a single cognitive/IO step: one `PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, or `PipeFunc`. Replace `S`'s `type` with the operator type, fill in its fields. No new signatures. **This branch is done.**
- **Controller (composite)** — `S` needs multiple steps, iteration over a list, parallel independent sub-tasks, or branching. Replace `S`'s `type` with a controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire its sub-pipes, and declare each sub-pipe that isn't yet trivial as a **new signature** (with its own contract + `signature_for`). Introduce any intermediate concepts the wiring needs. The new signatures join the work-list.

The "operator vs controller?" decision is usually pre-answered by the `signature_for` hint the *parent* set when it created `S`. Heuristic when the hint is absent or wrong: single step → operator; multiple/iterating/branching/parallel → controller, decompose.

### 2.4 Validation cadence — lenient per layer, strict at the end

- After each layer (or each step), validate leniently:

  ```bash
  mthds-agent validate bundle mthds-wip/<dir>/bundle.mthds -L mthds-wip/<dir>/ --allow-signatures --graph
  ```

  `--graph` renders the evolving scaffold to `dry_run.html` (signatures show as mock-producing nodes), so the structure is visible at every layer. `-L` loads every `.mthds` file in the dir as one library, so cross-file references resolve (and isolates from files outside it).

- When the work-list is empty, validate **strictly** (drop `--allow-signatures`):

  ```bash
  mthds-agent validate bundle mthds-wip/<dir>/bundle.mthds -L mthds-wip/<dir>/ --graph
  ```

  Passing strict validation is the gate that says *runnable*.

### 2.5 Termination & early stop — the bundle is its own todo list

The remaining work is exactly the set of pipes with `type = "PipeSignature"`. The scaffold is self-describing: the backlog is grep-able from the artifact itself, and the design can be **paused and resumed across sessions** with no external state — pick up by expanding whatever signatures remain.

- **Refine to runnable (default)** — recurse until no signatures remain; strict validation passes; deliver a runnable method.
- **Early stop** — at any layer, stop and deliver the leniently-valid scaffold. State which signatures are unimplemented and that resuming means expanding them. This is a legitimate deliverable: a validated design skeleton.

### 2.6 Invariants & rules

- **Contract stability.** Expanding a signature must preserve its `inputs` and `output` — its parent depends on that contract. You may freely change a signature's *internals*; you may not change its surface without revising the parent too (a more expensive, propagating change — flag it when it happens).
- **`main_pipe` is the anchor.** The top signature's code and its inputs/output are frozen after Layer 0; refinement replaces its body in place but never its identity or surface. This is the client contract.
- **Concepts refine lazily.** Boundary concepts are specified at Layer 0. Intermediate concepts are introduced simple (often `refines` a native) and gain `structure` only when a downstream consumer references specific fields — at that point structure the concept. (A signature mints a mock of its declared output; if a consumer reads `$x.field`, `x`'s concept must declare `field`.)
- **Error localization.** A lenient-validation failure after a step is, by construction, in the step you just added — bounding the fix.
- **Scope.** Recursive building adds `PipeSignature` (+ `signature_for`) to vibe's emittable set. The existing scope limits (no `dict`, no `PipeStructure`, no inline `templating_style`) are orthogonal to the strategy and stay as-is for now; revisiting them is tracked in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).

### 2.7 Artifact layout — a multi-file, same-domain library

The artifact is not one growing file but a **library**: a directory of `.mthds` files that all declare the same `domain`, loaded together with `-L`. The runtime merges them into one domain, and pipes/concepts reference each other across files by bare code (`LibraryCrateFactory`, `PipeLibrary`).

- **One pipe per file.** Each pipe code lives in exactly one file (`<code>.mthds`) for its whole life. A child pipe is **born as a signature stub file** the moment its parent references it; expanding it = **overwriting that same file** with the real implementation. The caller never holds the child signature inline — it only references the child by bare code, and that reference is stable across the swap.
- **Why overwrite, not add.** Declaring the same pipe (or concept) code in two files of the loaded library is a **hard error** (`PipeLibraryError` / `ConceptLibraryError`), not last-wins. So the swap can't be "signature here + implementation there" — the code has one home, overwritten in place. (That same hard error is a free safety net against accidental duplicates.)
- **Root file.** One file (`bundle.mthds`) is the root: it carries the `domain` header, `main_pipe`, and the boundary concepts. Every other file repeats the same `domain` header; only the root's `main_pipe` counts (first-write-wins; the rest are ignored, with a warning).
- **Concept ownership.** Each concept is declared **once**, in the file of the pipe that introduces it (boundary concepts in the root; intermediate concepts in the file of the controller that spawned the step). Consumers reference it by bare code.
- **Monotonic validity.** Every unbuilt pipe is a signature, so the assembled library is leniently valid at all times; each file swap (signature → implementation) keeps it green. The PostToolUse hook validates each per-file write against the whole library (`-L <dir> --allow-signatures`) — exactly the right granularity.
- **Backlog = files.** The remaining work is `grep -l '"PipeSignature"' *.mthds`.

---

## 3. Worked example

Job: turn a research paper (a PDF `Document`) into a structured `ResearchBrief`.

**Layer 0 — the whole job as one signature.** Boundary concepts specified fully; one signature.

```toml
domain      = "research_brief"
description = "Turn a research paper into a structured brief"
main_pipe   = "build_research_brief"

[concept.ResearchBrief]
description = "A structured brief of a research paper"

[concept.ResearchBrief.structure]
key_findings           = { type = "list", item_type = "text", description = "Notable findings", required = true }
plain_language_summary = { type = "text", description = "Plain-language summary", required = true }

[pipe.build_research_brief]
type          = "PipeSignature"
description   = "Read a research paper and produce a brief: key findings + a plain-language summary."
inputs        = { paper = "Document" }
output        = "ResearchBrief"
signature_for = "PipeSequence"
```

Lenient validation passes.

**Layer 1 — expand the top signature into a sequence.** The orchestrator overwrites `bundle.mthds` (the main pipe becomes a `PipeSequence`) and creates one file per child. One child is an obvious operator and is born implemented; the rest are born as signature stub files. Intermediate concepts the sequence introduces are declared in `bundle.mthds` (the file that owns them).

Call tree:

```
build_research_brief  [PipeSequence]   Document -> ResearchBrief
├─ extract_paper       [PipeExtract]   Document -> Page[]                       ✓ operator (born implemented)
├─ find_key_findings   [signature]     Page[] -> KeyFinding[]                   → PipeLLM
├─ write_plain_summary [signature]     Page[] -> PlainSummary                   → PipeLLM
└─ assemble_brief      [signature]     KeyFinding[], PlainSummary -> ResearchBrief   → PipeCompose
```

Files (every file declares `domain = "research_brief"`):

```
research_brief/
├─ bundle.mthds              # root: main_pipe, boundary concepts, build_research_brief (PipeSequence) + KeyFinding/PlainSummary
├─ extract_paper.mthds       # PipeExtract (done)
├─ find_key_findings.mthds   # PipeSignature (stub)
├─ write_plain_summary.mthds # PipeSignature (stub)
└─ assemble_brief.mthds      # PipeSignature (stub)
```

`bundle.mthds` (root, overwritten — the main pipe is now a controller; it owns the intermediate concepts):

```toml
[pipe.build_research_brief]
type        = "PipeSequence"
description = "Read a research paper and produce a brief: key findings + a plain-language summary."
inputs      = { paper = "Document" }
output      = "ResearchBrief"
steps = [
    { pipe = "extract_paper", result = "pages" },
    { pipe = "find_key_findings", result = "findings" },
    { pipe = "write_plain_summary", result = "summary" },
    { pipe = "assemble_brief", result = "brief" },
]

[concept]
KeyFinding   = "A single notable finding from a research paper"
PlainSummary = "A plain-language summary of a research paper"
```

`find_key_findings.mthds` (its own file, born as a stub — siblings `write_plain_summary.mthds` / `assemble_brief.mthds` look the same; `extract_paper.mthds` holds the real `PipeExtract`):

```toml
domain = "research_brief"

[pipe.find_key_findings]
type          = "PipeSignature"
description   = "Identify the key findings from the extracted pages"
inputs        = { pages = "Page[]" }
output        = "KeyFinding[]"
signature_for = "PipeLLM"
```

Lenient validation of the library passes (`extract_paper` runs for real; the three stub files mint mocks).

**Layer 2 — expand the remaining signatures (fan out).** Three stub files remain, so the orchestrator fans out one worker per file. Each **overwrites its own file** in place: `find_key_findings.mthds` and `write_plain_summary.mthds` become `PipeLLM`; `assemble_brief.mthds` becomes `PipeCompose` in construct mode, assembling `ResearchBrief` from `findings` + `summary` (its construct fields map to the structure declared at Layer 0 — no concept change needed because the boundary concept was specified up-front). The workers write in parallel; nothing collides because each owns a distinct `<code>.mthds`.

No file contains a `PipeSignature` → **strict** validation of the library passes → runnable.

What this illustrates: the top contract frozen at Layer 0; a mixed layer where one child is born implemented while siblings stay signature stub files; the swap-in as an in-place file overwrite (the call tree never re-wires); intermediate concepts introduced lazily and owned by the file that introduces them; `signature_for` pre-deciding each expansion; and the lenient → strict transition as the definition of "done".

---

## 4. Skill design — evolving `mthds-vibe` in place

Same skill, same name/slot (`templates/skills/mthds-vibe/SKILL.md.j2`). The single-pass body is replaced by the recursive loop. The shared `Step 0` env-check, the deliver step, and the "never write `inputs.json`" rule carry over unchanged.

### 4.1 Step structure

- **Step 0 — Environment check.** Unchanged (`{% include 'skills/shared/preamble.md.j2' %}`). No backend/keys needed — building and validating never run the method.
- **Step 1 — Capture the top-level requirement as one signature.** Determine input concept(s), output concept, and a precise description; specify boundary concepts fully. Write the **root file** `bundle.mthds` (the `domain` header, `main_pipe`, and the fully-specified boundary concepts) with a single `PipeSignature` as the main pipe. Validate leniently. *This is the only step with optional interactivity* (see Autonomy). Announce the captured contract in one line before recursing, so the user can interject without being blocked by a question.
- **Step 2 — Refine layer by layer (auto), fanning out.** Work the signature backlog (the stub files) breadth-first by layer. For a layer with one pending signature, expand inline; for several, **fan out one `mthds-signature-expander` sub-agent per signature** (see §4.4). Each worker **overwrites its own `<code>.mthds` file** with the implementation (an operator, or a controller plus new child stub files and the concepts it owns) — no merge step. Validate the assembled library leniently (`-L <dir> --allow-signatures`); on failure, fix the offending file and re-validate. Rescan the dir for remaining stub files and repeat until none remain (or the user stopped early).
- **Step 3 — Finalize.** Run strict validation (`--graph`). Fix any whole-bundle semantic errors. Passing = runnable.
- **Step 4 — Deliver.** Same as vibe today: show the input schema (`mthds-agent inputs bundle …`, never save `inputs.json`), point to `dry_run.html`, suggest `mthds-agent run bundle … --dry-run --mock-inputs` then `/mthds-inputs`. **Early-stop variant:** if signatures remain, deliver the scaffold, list the unimplemented signatures, and explain that resuming = expanding them.

### 4.2 Autonomy model

This generalizes vibe's existing "automatic by default, interactive only if ambiguous/asked" heuristic, scoped to the foundation:

- **Requirements (Step 1)** — default: infer and proceed. Engage in discussion *only* when the request is genuinely ambiguous about inputs/output/semantics, or when the user signals they want to discuss. The top signature is cheap to state and central, so always *announce* it (non-blocking).
- **Recursion (Step 2+)** — always auto. No per-layer approval prompts. The leniently-valid checkpoints + `dry_run.html` are the review surface; the user can interrupt at any time.

### 4.3 Reference doc changes

`skills/mthds-vibe/references/vibe-cheat-sheet.md` (static asset) needs a `PipeSignature` section: the syntax above, the `signature_for` hint and its rules, the operator-vs-controller decision, and the lenient vs strict validate commands. The recursive loop itself (the layer rhythm, the invariants) lives in the SKILL body; the cheat sheet stays the syntax/field source of truth.

### 4.4 Recursion as a callable unit & parallel fan-out

The recursion is uniform — every step is the same job — so it is worth isolating as a callable unit and parallelizing across independent signatures.

**The unit — `expand-signature`.** Given one signature `S` (its frozen contract + the slice of description and concepts it touches), produce `S`'s implementation one level down: an operator (done), or a controller plus the child signatures (`signature_for`-hinted) and intermediate concepts it spawns. Contract in, contract preserved, expansion out.

**Orchestrator vs worker.** `mthds-vibe` is the **orchestrator**: it owns the library dir, the backlog, the layer loop, per-layer validation, and finalize. The **worker** is a dedicated sub-agent type (`mthds-signature-expander`) whose system prompt *is* the `expand-signature` job, with tools limited to Read + Write (scoped to the files it owns) + the validate command. It **owns one file**: the `<code>.mthds` of the signature it was handed.

**One pipe, one file — overwrite in place (the rule that unlocks fan-out).** A pipe code has a single home file. Expanding a signature = **overwriting its own `<code>.mthds`** with the implementation; if that implementation is a controller, the worker also writes the new child stub files and declares the concepts it introduces. No fragments, no merge. This works because the runtime assembles every same-domain file in the `-L` dir into one library with cross-file bare-code resolution — and because declaring a code in two files is a hard error, each swap *must* happen in place, which is exactly what keeps the call graph stable. Parallel workers never contend: each writes a distinct file, and everything still unbuilt is a signature, so the assembled library stays leniently valid throughout.

**The layer loop.**

```
pending = stub files (PipeSignature) at depth N
  one  → orchestrator expands inline
  many → fan out one mthds-signature-expander per stub file (parallel)
each worker overwrites its <code>.mthds in place (+ writes child stubs if it became a controller)
  → orchestrator lenient-validates the library (-L) as the layer checkpoint
pending = new stub files (depth N+1), found by rescanning the dir → repeat
none left → strict validate → runnable
```

Fan out only when a layer has multiple stub files; inline-expand a lone one to avoid sub-agent overhead. The orchestrator grows the backlog by **rescanning the dir** (`grep -l PipeSignature`) — the filesystem is the source of truth, so workers need not report their children.

**Contract & collisions.** A worker must preserve its target's `inputs`/`output` (its parent depends on them). Same domain = one shared namespace, so workers name the children they spawn by deriving from their own pipe code (namespacing by parent). If two siblings still collide, the duplicate-code **hard error** at validation catches it (never silent) and the orchestrator resolves the rare conflict. Each concept is declared once, in the file of the pipe that introduces it.

**Why it pays off.** Beyond speed: each worker sees only its signature's contract + referenced concepts — not the whole library — so contexts stay small and sharp, which improves expansion quality as well as parallelism. The `expand-signature` instructions are authored once and serve as both the worker's system prompt and the orchestrator's inline-path reference — one source of truth. This adds an `agents/` component to the plugin, templated like the skills to keep the multi-target build consistent.

> The fan-out here is skill-level (the orchestrator uses the Agent tool when run). The same layer loop maps cleanly onto the Workflow tool if we ever want deterministic, journaled orchestration — but that is not required for the skill.

### 4.5 Additive variant — `PipeSignature` as a header (planned)

The model above swaps a stub by **overwriting** its file. A cleaner end-state, once the runtime supports it, is **purely additive**: treat a `PipeSignature` as a C-style **forward declaration** ("header") and the concrete pipe as its **definition**. A worker then writes a *new* `<code>.mthds` definition file and never edits an existing one — the safest possible parallel-write story.

This needs one runtime change: when the library merge sees the same code declared as a signature and as a concrete pipe, the **concrete satisfies the signature** (definition wins; contracts must match) instead of raising a duplicate-code error. Plan: `_recursive/TODOS.md` (pipelex worktree, branch `feature/Support-recursive-design`).

With it:

- The orchestrator forward-declares a controller's children (signatures) when it wires them; each worker **adds** a definition file. No overwrites, so no transient signature/implementation collision even with many workers writing at once.
- Headers persist after they're satisfied, so the backlog is *not* "files that mention a signature" but **declared codes with no concrete definition yet** (`{signature codes} − {concrete codes}`) — the orchestrator computes that set each layer.
- Two concrete definitions of one code remain a hard error; concepts are unaffected (no signature form), so colliding intermediate concepts are still caught.

Until the relaxation ships, the overwrite-in-place model (§2.7, §4.4) is the working fallback — also collision-free, just not additive. Both target the same multi-file library; only the swap mechanic differs.

---

## 5. Required tooling changes

### 5.1 The PostToolUse hook conflict (must fix)

The PostToolUse hook (`templates/hooks/validate-mthds.sh.j2`) validates every `.mthds` write. Stage 3 (line 97) runs:

```bash
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/"      # strict — no --allow-signatures
```

A bundle that contains signatures fails strict validation with `SignaturesNotAllowedError`, which the hook classifies as input-domain (or unknown → default block) and **blocks the write**. Recursive building writes signature-containing bundles on every layer — so without a change, the skill fights its own hook on every save.

### 5.2 The fix — add `--allow-signatures` to the hook unconditionally

`--allow-signatures` only relaxes the signature pre-pass; it gates *nothing else*. On a bundle with no signatures, lenient and strict validation are **identical**. Therefore adding the flag to the hook's Stage 3 call is a no-op for every existing flow (vibe, build, hand-edits never contain signatures) and unblocks recursive building:

```bash
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --allow-signatures
```

The strict gate moves to where it belongs: the skill's explicit finalize step, plus `run` (which always rejects signatures via `PipeSignatureNotExecutableError`). A bundle that *should* be finished but accidentally retains a signature is still caught there. In the multi-file model the hook fires on each per-pipe file write and validates the whole assembled library (`-L $PARENT_DIR`) — exactly the granularity recursive building needs.

**Leftover-signature nudge (adopted).** Also detect leftover signatures (`grep -q '"PipeSignature"'`) and, on lenient success, emit a *non-blocking* `additionalContext` note listing them ("signatures remain — implement before running"). Costs a grep; gives the agent an in-progress reminder without blocking. Mirror in the Codex hook (§5.3).

### 5.3 Codex hook parity

The Codex hook (`mthds-agent codex hook`, logic in `mthds-js`) runs the analogous `pipeline-agent validate bundle` at its Stage 3. It needs the same change — pass `--allow-signatures` (and, optionally, the same leftover-signature note). This is a code change in `mthds-js`, paired with the shell-hook change here.

### 5.4 mthds-agent — already sufficient

`mthds-agent validate` forwards unknown flags verbatim to the pipelex CLI (`.allowUnknownOption()`), so `--allow-signatures` already reaches pipelex today; no new option needs to be defined. Optional polish: expose/document it explicitly in `mthds-agent` and in the `mthds-agent-guide` shared reference, and consider a small `mthds-agent list signatures` helper (the backlog view). Not required for the feature.

---

## 6. Decisions (resolved)

- **Naming/connotation.** Keep the `mthds-vibe` name — it still fits a layer-by-layer process. Update only the skill `description` to reflect top-down, valid-at-every-step refinement.
- **Scope limits.** Keep vibe's current limits (`dict`, `PipeStructure`, inline `templating_style`) as-is for this work. Revisiting them is tracked separately in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).
- **Delivery format / file layout.** The builder produces a **multi-file, same-domain library** (one pipe per file; §2.7). Keep small files for now. An optional final *flatten into one `bundle.mthds`* is deferred — tracked in [`../deferred-issues.md`](../deferred-issues.md).
- **Runtime relaxation (signature = header).** To make parallel fan-out purely additive, the pipelex library merge will reconcile a `PipeSignature` with a concrete pipe of the same code (definition wins; contracts must match) instead of erroring (§4.5). Plan: `_recursive/TODOS.md` (worktree branch `feature/Support-recursive-design`). Optional — the overwrite-in-place model works today without it.
- **`mthds-build` relationship.** Build stays separate. It *could* later adopt the same signature-driven loop (its markdown drafts replaced by a live leniently-valid bundle). Out of scope here.
- **Version floor.** Lenient validation requires pipelex ≥ `0.31.0` (the `../_recursive` release that added `PipeSignature` + `--allow-signatures`). `min_mthds_version` (`targets/defaults.toml`) tracks the **mthds-agent** version (currently `0.9.0`), not pipelex — so the bump is to *the mthds-agent version that ships/requires pipelex ≥ 0.31.0*, not the literal `0.31.0`. Determine that mthds-agent version and bump via `/bump-mthds-version`. **Open:** confirm the exact mthds-agent version.
- **`additionalContext` nudge** (§5.2) — **adopt it.** On lenient success with signatures present, emit the non-blocking leftover-signature reminder.

---

## 7. Implementation plan

*Parallel track (pipelex, optional — enables the additive variant §4.5): implement the signature/concrete reconciliation in the library merge per `_recursive/TODOS.md`. Separate repo; can land anytime. The steps below use the overwrite-in-place fallback until it ships.*

1. **Unblock signatures in the hook.** Add `--allow-signatures` to `templates/hooks/validate-mthds.sh.j2` Stage 3; `make build`. This is foundational and independent of the skill rewrite.
   - **Checkpoint** — with the hook lenient, a hand-written signature-containing bundle can be saved without being blocked, while a signature-free bundle still validates exactly as before. Verify via the `internal-tools` integration suite (`make build && make agent-test`), which is the safety net for the hook/install system.
2. **Document the primitive.** Add the `PipeSignature` / `signature_for` / lenient-vs-strict section to `skills/mthds-vibe/references/vibe-cheat-sheet.md` and the `mthds-agent-guide` shared reference.
3. **Author the `expand-signature` instructions + worker agent.** Write the uniform expansion job once; ship it as the `mthds-signature-expander` sub-agent (new `agents/` plugin component, templated like the skills) and as the orchestrator's inline-path reference. Tools limited to Read + Write (its own file) + validate; the worker writes its `<code>.mthds` (and any child stubs) — no fragments, no merge (§4.4).
4. **Rewrite the skill (orchestrator).** Replace the single-pass body of `templates/skills/mthds-vibe/SKILL.md.j2` with the Step 0–4 recursive flow, the autonomy model, and the Step 2 fan-out + file-per-pipe loop. Update the skill `description`. `make build` + `/reload-plugins` to dogfood.
5. **Codex parity.** Mirror §5.2/§5.3 in the `mthds-js` Codex hook.
6. **Validate end-to-end.** `make build && make check`; run the `internal-tools` integration tests; dogfood the recursive flow on a real multi-layer method (e.g. the §3 example), exercising both inline and fan-out layers, and confirm lenient-per-layer → strict-at-end behaves as designed.
   - **Checkpoint** — recursive `mthds-vibe` produces a runnable method through layered refinement (fanning out workers on multi-signature layers), every intermediate save passes the (now-lenient) hook, and the final strict gate holds. Ready to ship.
