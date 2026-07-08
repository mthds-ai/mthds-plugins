# Recursive Method Building — Design Doc

Origin: [kick-off.md](kick-off.md). This doc turns that kick-off into a methodology and a concrete skill design.

## TL;DR

Build a `.mthds` method **top-down by stepwise refinement**, where every intermediate state is a real, validatable library (a set of same-domain `.mthds` files, built additively — one definition per file). Start by capturing the whole job as a *single pipe signature* — the client contract (inputs, output, semantics). Then refine one signature at a time, one level down, into operators and controllers, leaving the not-yet-built parts as further signatures. Validate **leniently** (`--allow-signatures`) after each layer; the library is always valid and always resumable. Stop when no signatures remain (strict validation passes → runnable), or stop early and keep the leniently-valid scaffold.

This is an **in-place evolution of `mthds-recursive`**: its current single-pass authoring becomes recursive layer-by-layer refinement.

The capability that unlocks this shipped in pipelex (the `PipeSignature` pipe type + `--allow-signatures` lenient validation, worktree `../_recursive`); the merge-time **signature/concrete reconciliation + library-level concept resolution** that make the build *additive* (§4.5), the **normalized header↔definition contract check** (concept identity, not raw string), and the **`pending_signatures`** list on validate (backing the hook nudge) have all since shipped on the same worktree branch. It is already reachable through `mthds-agent` today via flag passthrough — no CLI plumbing required. The one piece of tooling that must change is the PostToolUse hook (see [Required tooling changes](#required-tooling-changes)).

## Decisions taken

These were confirmed before writing (recorded here for handoff):

- **Doc scope** — methodology first, then concrete skill design (this doc).
- **Skill identity** — evolve `mthds-recursive` in place; the staged `mthds-build` stays separate.
- **Autonomy** — *optionally hybrid*: the requirements-capture step (the top signature) is interactive only when the request is ambiguous or the user signals they want to discuss; otherwise the agent commits to its read and proceeds. The recursive refinement that follows runs in **auto mode**.
- **Stop / output** — refine to runnable by default (strict validation passes, no signatures left), but support stopping early and delivering a leniently-valid scaffold.
- **v1 scope (post-review, 2026-06-07)** — the eng review reduced v1: **fan-out is deferred to a follow-up** (decision D1). v1 runs the layer loop **inline/serial on both targets**; correctness is identical, only parallelism + per-signature context isolation are dropped. The `agents/` worker, the `expand-signature` shared partial, and the build-system `agents/` support all move to the follow-up. The fan-out design below (§4.4, §6, §7 item 3) is retained as the follow-up's spec, annotated where it would otherwise read as v1. Full decision set: the **GSTACK REVIEW REPORT** at the end of this doc.

---

## 1. Background & motivation

`mthds-recursive` today writes a complete `bundle.mthds` in **one pass**, then validates and iterates on errors (see `templates/skills/mthds-recursive/SKILL.md.j2`). That works for small methods. For non-trivial ones it asks the model to get the entire tree right at once — deep nesting, every intermediate concept, all controller wiring — and that is exactly where single-pass authoring breaks down, with errors that could be anywhere in the bundle.

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
- **Operation (a refinement step)** — supply one signature's implementation *one level down* by **adding a definition file** that reconciles with it (never overwriting), then re-validate.

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

- **Operator (leaf)** — `S` is a single cognitive/IO step: one `PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, or `PipeFunc`. **Define `S` in its own `<S>.mthds` file** with the operator type (its `inputs`/`output` repeating the header exactly), fill in its fields. No new signatures. **This branch is done.**
- **Controller (composite)** — `S` needs multiple steps, iteration over a list, parallel independent sub-tasks, or branching. **Define `S` in its own `<S>.mthds` file** as a controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire its sub-pipes, **forward-declare** each sub-pipe that isn't yet trivial as a **new signature** header (with its own contract + `signature_for`), and introduce any intermediate concepts the wiring needs. The new signatures join the work-list.

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

The remaining work is exactly the set of declared signatures with no concrete definition yet — `{signature codes} − {concrete codes}`. The scaffold is self-describing: the backlog is computable from the assembled library itself, and the design can be **paused and resumed across sessions** with no external state — pick up by defining whatever signatures are still unsatisfied.

- **Refine to runnable (default)** — recurse until every signature has a concrete definition; strict validation passes; deliver a runnable method.
- **Early stop** — at any layer, stop and deliver the leniently-valid scaffold. State which signatures are unimplemented and that resuming means expanding them. This is a legitimate deliverable: a validated design skeleton.

### 2.6 Invariants & rules

- **Contract stability.** A definition must preserve its header's `inputs` and `output` **contract** — matched by **concept identity** (bare↔qualified and native spellings are equivalent, multiplicity structural), not byte-string; the parent depends on that contract. You may freely choose a signature's *internals*; you may not change its surface without revising the parent too (a more expensive, propagating change — flag it when it happens).
- **`main_pipe` is the anchor.** The top signature's code and its inputs/output are frozen after Layer 0; refinement supplies its body as a separate definition file (reconciled with the frozen header) but never changes its identity or surface. This is the client contract.
- **A concept's shape is fixed at introduction (not deferrable across files).** Boundary concepts are specified at Layer 0. An intermediate concept is declared **once**, in the file of the controller that introduces it, and the additive model never lets a later file add structure (a second declaration is a hard "declared in two different bundle files" error). Decide its shape from the consumers that controller wires: **structured** if any downstream consumer field-reads it (`$x.field` / construct `from = "x.field"`) — a field-read on a simple concept fails even under lenient validation (dry-run "cannot resolve path") — and **simple** (often `refines` a native) only if it is consumed whole (`@x`). When a *sibling* field-reads a concept, hoist that concept to the common parent controller that wires both producer and consumer and structure it there. (Empirically confirmed in the 6.3 dogfood; "lazy structuring" earlier framed this as deferrable, which the additive model does not support. True cross-file refinement would be a pipelex feature, out of v1 scope.)
- **Error localization.** A lenient-validation failure after a step is, by construction, in the step you just added — bounding the fix.
- **Scope.** Recursive building adds `PipeSignature` (+ `signature_for`) to vibe's emittable set. The existing scope limits (no `dict`, no `PipeStructure`, no inline `templating_style`) are orthogonal to the strategy and stay as-is for now; revisiting them is tracked in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).

### 2.7 Artifact layout — a multi-file, same-domain library (additive)

The artifact is not one growing file but a **library**: a directory of `.mthds` files that all declare the same `domain`, loaded together with `-L`. The runtime merges them into one domain, and pipes/concepts reference each other across files by bare code (`LibraryCrateFactory`, `PipeLibrary`).

Construction is **additive**: a `PipeSignature` is a C-style **forward declaration** ("header") and the concrete pipe is its **definition**. Expanding a signature **adds a new definition file**; no existing file is ever rewritten. (The earlier overwrite-in-place model is retired — see §4.5 for why, and why it never actually worked for the common case.)

- **Header + definition, one concrete per file.** A child pipe is **forward-declared as a `PipeSignature` header** inline in the file of the parent that wires it — the moment the parent references it. Expanding it = **adding a separate `<code>.mthds` file** holding the concrete definition. At merge, the header and the definition reconcile (the **concrete wins**), so the same code legitimately appears as a header in one file and a concrete in another. Each pipe has **at most one concrete definition file**; the caller only ever references the child by bare code, and both that reference and the header are stable across the expansion.
- **Why additive works (and what's still a hard error).** Two *concrete* pipes with the same code remain a **hard error** (`PipeLibraryError`), as do two signatures with mismatched contracts — a free safety net against accidental duplicates. Two signatures with *matching* contracts (e.g. a shared sub-pipe forward-declared by two parents) instead **collapse to one**; the survivor is picked deterministically from blueprint content, so its `description`/`signature_for` is arbitrary among the matching headers but independent of load order (once the concrete lands it wins anyway). What changed: a signature + a concrete of the same code now **reconcile** instead of colliding (Part A). And concept references resolve against the **merged** library, not per file (Part B), so a pipe in one file can reference by bare code a concept declared in a sibling file. Concepts have **no signature form**, so a concept declared twice is still a `ConceptLibraryError` — colliding intermediate concepts are still caught.
- **Contract must match (by concept identity).** A header and its definition must declare the **same `inputs` and `output` contract**, compared by **concept identity** at merge — bare `Brief` ≡ `thisdomain.Brief`, `Text` ≡ `native.Text`, multiplicity compared structurally — so bare-vs-qualified spelling differences reconcile fine. What still must hold: both sides declare `inputs`/`output` **explicitly** — pipes do **not** infer `inputs` from prompt sigils, so a header listing `inputs` and a definition omitting them is still a mismatch. Genuinely different concepts, or differing multiplicity, still error. (A definition output that merely *refines* the header's stays deferred — see §4.5.)
- **Root file.** One file (`bundle.mthds`) is the root: it carries the `domain` header, the `main_pipe` directive, and the boundary concepts — plus the top pipe's `PipeSignature` header (Layer 0). It is written once and **persists**; the concrete main pipe is added in its own `<main_pipe>.mthds` file like any other definition (`main_pipe` is a reference, not the implementation). Every other file carries **only** `domain = "<same_domain>"` for membership — it omits `description`, `system_prompt`, and `main_pipe`, which live in the root. The runtime merges domain metadata order-independently and treats an omitted field as no-opinion, so siblings emit no warnings and the root's header always wins regardless of load order (shipped — see [`../deferred-issues.md`](../deferred-issues.md)).
- **Concept ownership.** Each concept is declared **once**, in the file of the pipe that introduces it (boundary concepts in the root; intermediate concepts in the definition file of the controller that spawned the step). Consumers reference it by bare code across files.
- **Monotonic validity.** Every unbuilt pipe is a reachable signature, so the assembled library is leniently valid at all times; each *added* definition file keeps it green (the header it satisfies stays put, reconciled). The PostToolUse hook validates each per-file write against the whole library (`-L <dir> --allow-signatures`) — exactly the right granularity.
- **Backlog = unsatisfied headers.** Because headers persist, the remaining work is not "files that mention a signature" but **declared signature codes with no concrete definition yet**: `{signature codes} − {concrete codes}`, recomputed from the assembled library each layer.

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

**Layer 1 — expand the top signature into a sequence.** The orchestrator **adds** `build_research_brief.mthds` — the concrete `PipeSequence` that reconciles with the header in `bundle.mthds` (the root file is *not* touched). In that same definition file it **forward-declares each child as a `PipeSignature` header** (inline, where the steps are wired) and declares the intermediate concepts the sequence introduces. One child is an obvious operator, so its definition file is added right away; the rest stay headers only, each awaiting its own definition file.

Call tree:

```
build_research_brief  [PipeSequence]   Document -> ResearchBrief
├─ extract_paper       [PipeExtract]   Document -> Page[]                       ✓ operator (defined now)
├─ find_key_findings   [signature]     Page[] -> KeyFinding[]                   → PipeLLM
├─ write_plain_summary [signature]     Page[] -> PlainSummary                   → PipeLLM
└─ assemble_brief      [signature]     KeyFinding[], PlainSummary -> ResearchBrief   → PipeCompose
```

Files (every file declares `domain = "research_brief"`):

```
research_brief/
├─ bundle.mthds                # root (persists): main_pipe, boundary concept ResearchBrief, build_research_brief HEADER
├─ build_research_brief.mthds  # added: PipeSequence (def) + the four child headers + KeyFinding/PlainSummary
└─ extract_paper.mthds         # added: PipeExtract (the obvious operator, defined now)
```

(`find_key_findings` / `write_plain_summary` / `assemble_brief` exist only as headers inside `build_research_brief.mthds` — no definition file yet.)

`bundle.mthds` (root — **unchanged** from Layer 0; the header persists and is later satisfied by the added definition):

```toml
[pipe.build_research_brief]
type          = "PipeSignature"
description   = "Read a research paper and produce a brief: key findings + a plain-language summary."
inputs        = { paper = "Document" }
output        = "ResearchBrief"
signature_for = "PipeSequence"
```

`build_research_brief.mthds` (added — the concrete sequence; its `inputs`/`output` match the header exactly so it reconciles; it forward-declares its children and owns the intermediate concepts):

```toml
domain = "research_brief"

[concept]
KeyFinding   = "A single notable finding from a research paper"
PlainSummary = "A plain-language summary of a research paper"

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

# Children forward-declared as headers — definitions are added as separate files.
[pipe.extract_paper]
type          = "PipeSignature"
description   = "Extract the pages of the research paper"
inputs        = { paper = "Document" }
output        = "Page[]"
signature_for = "PipeExtract"

[pipe.find_key_findings]
type          = "PipeSignature"
description   = "Identify the key findings from the extracted pages"
inputs        = { pages = "Page[]" }
output        = "KeyFinding[]"
signature_for = "PipeLLM"

[pipe.write_plain_summary]
type          = "PipeSignature"
description   = "Write a plain-language summary from the extracted pages"
inputs        = { pages = "Page[]" }
output        = "PlainSummary"
signature_for = "PipeLLM"

[pipe.assemble_brief]
type          = "PipeSignature"
description   = "Assemble the final brief from findings and summary"
inputs        = { findings = "KeyFinding[]", summary = "PlainSummary" }
output        = "ResearchBrief"
signature_for = "PipeCompose"
```

`extract_paper.mthds` is added in the same layer — the operator is obvious, so its concrete `PipeExtract` (same `paper -> Page[]` contract) is written immediately, reconciling with its header above.

Lenient validation of the library passes (`build_research_brief` and `extract_paper` are concrete and reconcile with their headers; the three still-header children mint mocks).

**Layer 2 — define the remaining signatures (fan out).** Three headers still have no definition (`find_key_findings`, `write_plain_summary`, `assemble_brief`), so the orchestrator fans out one worker per header. Each **adds its own definition file** — never touching an existing one: `find_key_findings.mthds` and `write_plain_summary.mthds` hold a `PipeLLM`; `assemble_brief.mthds` holds a `PipeCompose` in construct mode, assembling `ResearchBrief` from `findings` + `summary` (its construct fields map to the structure declared at Layer 0 — no concept change needed because the boundary concept was specified up-front). Each definition repeats its header's exact `inputs`/`output`, so it reconciles. The workers write in parallel; nothing collides because each adds a distinct `<code>.mthds` and the headers they satisfy live (untouched) in `build_research_brief.mthds`.

Every declared signature code now has a concrete definition → the backlog `{signatures} − {concretes}` is empty → **strict** validation of the library passes → runnable.

What this illustrates: the top contract frozen at Layer 0; a mixed layer where one child is defined immediately while siblings stay headers; expansion as **adding a definition file** that reconciles with a persistent header (the call tree never re-wires, and no file is ever overwritten); intermediate concepts introduced lazily and owned by the file that introduces them; the header/definition contract matched by concept identity; `signature_for` pre-deciding each expansion; and the lenient → strict transition (empty backlog) as the definition of "done".

---

## 4. Skill design — evolving `mthds-recursive` in place

Same skill, same name/slot (`templates/skills/mthds-recursive/SKILL.md.j2`). The single-pass body is replaced by the recursive loop. The shared `Step 0` env-check, the deliver step, and the "never write `inputs.json`" rule carry over unchanged.

### 4.1 Step structure

- **Step 0 — Environment check.** Unchanged (`{% include 'skills/shared/preamble.md.j2' %}`). No backend/keys needed — building and validating never run the method.
- **Step 1 — Capture the top-level requirement as one signature.** Determine input concept(s), output concept, and a precise description; specify boundary concepts fully. Write the **root file** `bundle.mthds` (the `domain` header, `main_pipe`, and the fully-specified boundary concepts) with a single `PipeSignature` as the main pipe. Validate leniently. *This is the only step with optional interactivity* (see Autonomy). Announce the captured contract in one line before recursing, so the user can interject without being blocked by a question.
- **Step 2 — Refine layer by layer (auto), fanning out.** Work the signature backlog — the headers with no definition yet (`{signature codes} − {concrete codes}`) — breadth-first by layer. For a layer with one pending signature, expand inline; for several, **fan out one `mthds-signature-expander` sub-agent per signature** (see §4.4). Each worker **adds a new `<code>.mthds` definition file** (an operator, or a controller that also forward-declares its child headers and declares the concepts it owns) — never overwriting an existing file, no merge step. Validate the assembled library leniently (`-L <dir> --allow-signatures`); on failure, fix the offending file and re-validate — **except** an intermediate-concept name collision between parallel siblings, which is not locally fixable additively: **stop and surface it** rather than auto-recovering (see §4.4). Recompute the backlog from the assembled library and repeat until it is empty (or the user stopped early).
- **Step 3 — Finalize.** Run strict validation (`--graph`). Fix any whole-bundle semantic errors. Passing = runnable.
- **Step 4 — Deliver.** Same as vibe today: show the input schema (`mthds-agent inputs bundle …`, never save `inputs.json`), point to `dry_run.html`, suggest `mthds-agent run bundle … --dry-run --mock-inputs` then `/mthds-inputs`. **Early-stop variant:** if signatures remain, deliver the scaffold, list the unimplemented signatures, and explain that resuming = expanding them.

### 4.2 Autonomy model

This generalizes vibe's existing "automatic by default, interactive only if ambiguous/asked" heuristic, scoped to the foundation:

- **Requirements (Step 1)** — default: infer and proceed. Engage in discussion *only* when the request is genuinely ambiguous about inputs/output/semantics, or when the user signals they want to discuss. The top signature is cheap to state and central, so always *announce* it (non-blocking).
- **Recursion (Step 2+)** — always auto. No per-layer approval prompts. The leniently-valid checkpoints + `dry_run.html` are the review surface; the user can interrupt at any time.

### 4.3 Reference doc changes

`skills/mthds-recursive/references/recursive-cheat-sheet.md` (static asset) needs a `PipeSignature` section: the syntax above, the `signature_for` hint and its rules, the operator-vs-controller decision, and the lenient vs strict validate commands. The recursive loop itself (the layer rhythm, the invariants) lives in the SKILL body; the cheat sheet stays the syntax/field source of truth.

### 4.4 Recursion as a callable unit & parallel fan-out

The recursion is uniform — every step is the same job — so it is worth isolating as a callable unit and parallelizing across independent signatures.

**The unit — `expand-signature`.** Given one signature `S` (its frozen contract + the slice of description and concepts it touches), produce `S`'s implementation one level down: an operator (done), or a controller plus the child signatures (`signature_for`-hinted) and intermediate concepts it spawns. Contract in, contract preserved, expansion out.

**Orchestrator vs worker.** `mthds-recursive` is the **orchestrator**: it owns the library dir, the backlog, the layer loop, per-layer validation, and finalize. The **worker** is a dedicated sub-agent type (`mthds-signature-expander`) whose system prompt *is* the `expand-signature` job, with tools limited to Read + Write (scoped to the one file it adds) + the validate command. It **adds one file**: the `<code>.mthds` *definition* for the signature it was handed — it never edits an existing file.

**Header + definition — additive writes (the rule that unlocks fan-out).** Expanding a signature = **adding a new `<code>.mthds` definition file** holding the concrete pipe; if that implementation is a controller, the same file also forward-declares its child headers and declares the concepts it introduces. No existing file is ever overwritten, no fragments, no merge. This works because the runtime assembles every same-domain file in the `-L` dir into one library with cross-file bare-code resolution, and because a header and a concrete of the same code **reconcile** (the concrete wins; contracts must match) rather than colliding. The header — declared by the parent that wired the child — persists and keeps the call graph stable. Parallel workers never contend: each adds a distinct definition file, and every code still without a concrete is a reachable signature, so the assembled library stays leniently valid throughout.

**The layer loop.**

```
backlog = {signature codes} − {concrete codes} at depth N
  one  → orchestrator expands inline
  many → fan out one mthds-signature-expander per code (parallel)
each worker ADDS its <code>.mthds definition file
  (+ forward-declares child headers & owns new concepts if it became a controller)
  → orchestrator lenient-validates the library (-L) as the layer checkpoint
backlog = {signature codes} − {concrete codes} at depth N+1, recomputed from the library → repeat
empty → strict validate → runnable
```

Fan out only when a layer has multiple pending codes; inline-expand a lone one to avoid sub-agent overhead. The orchestrator recomputes the backlog from the **assembled library** each layer (declared signatures minus concrete definitions) — the library is the source of truth, so workers need not report their children.

In practice the backlog each round is just the flat **`pending_signatures`** set from validate — there is no depth to compute. Expanding the *whole* current pending set per round walks the tree breadth-first by construction (a layer's children only become pending once their parent is expanded), so "depth N / N+1" in the loop above is the *conceptual* layer, not a filter the orchestrator derives. Don't try to reconstruct a depth tree from `pending_signatures`; just drain the set round by round until it's empty.

**Contract & collisions.** A worker must declare its target's `inputs`/`output` **explicitly** in the definition (pipes don't infer `inputs` from prompt sigils — see §4.5), matched by **concept identity** (bare↔qualified/native equivalent, multiplicity structural — spelling need not be byte-identical), so the definition reconciles with the header. Same domain = one shared namespace, so workers name the children they spawn by deriving from their own pipe code (namespacing by parent). Two *concrete* definitions of one code, or a definition whose contract diverges from its header, are a **hard error** at validation (never silent). Each concept is declared once, in the file of the pipe that introduces it; workers derive the concepts they introduce from their own pipe code to avoid sibling clashes — but that is a convention, not a guarantee. How the orchestrator should robustly prevent or resolve **intermediate-concept name collisions** between parallel siblings (concepts have no header form, so Part A does not cover them) is an open question, **deferred until observed in a real build** — see [`../deferred-issues.md`](../deferred-issues.md). **Serial v1 (decision D5):** because v1 has no parallel workers, the orchestrator sees the whole assembled library at all times, so it **prevents** collisions up front — *before introducing a new intermediate concept, it checks the concept isn't already declared in the library/pending set and derives a unique code* (namespacing by the parent pipe code). The hard `ConceptLibraryError` is the backstop for anything that slips through. The **parallel-sibling** case (two workers in one fan-out layer each minting the same concept code, blind to each other) is what stays **deferred until observed** — see [`../deferred-issues.md`](../deferred-issues.md); when fan-out lands, the orchestrator's behavior on hitting it is to **stop and surface** the collision (report the colliding concept code and the two definition files, halt the layer rather than auto-renaming, which would force the cross-file, non-additive edit the model otherwise avoids) — putting the real case in front of us to design the prevention against, instead of hiding it behind a speculative auto-fix.

**Why it pays off.** Beyond speed: each worker sees only its signature's contract + referenced concepts — not the whole library — so contexts stay small and sharp, which improves expansion quality as well as parallelism. The `expand-signature` instructions are authored once and serve as both the worker's system prompt and the orchestrator's inline-path reference — one source of truth. This adds an `agents/` component to the plugin (**Claude only** — Codex plugin manifests expose no `agents` field; their components are `skills`/`hooks`/`mcpServers`/`apps`).

**v1 scope decision — fan-out DEFERRED to a follow-up (post-review, supersedes the "Claude-only" plan below).** The eng review (decision D1) pulled fan-out out of v1 entirely: **both targets run the layer loop inline/serial**. The paragraph that follows describes the original Claude-fan-out plan and is retained as the follow-up's spec. ~~On **Claude**, fan-out ships as the `agents/` worker spawned via the Agent tool. On **Codex**, the same layer loop runs **inline/serial** (no worker sub-agent) for v1 — correctness is identical, only the per-layer parallelism is dropped. The skill is already per-target templated, so the fan-out section renders only for the Claude target.~~ Codex *does* support custom sub-agents (defined as `.codex/agents/*.toml` with `developer_instructions` + tool restrictions, installable by `mthds-agent codex apply-config`, spawned on explicit ask), so Codex fan-out is a tractable follow-up too. Both Claude and Codex fan-out are now in the same deferred follow-up (see [`../deferred-issues.md`](../deferred-issues.md)).

> The fan-out here is skill-level (the orchestrator uses the Agent tool when run). The same layer loop maps cleanly onto the Workflow tool if we ever want deterministic, journaled orchestration — but that is not required for the skill.

### 4.5 Runtime support — `PipeSignature` as a header (shipped)

The additive model (§2.7, §3, §4.4) treats a `PipeSignature` as a C-style **forward declaration** ("header") and the concrete pipe as its **definition**: a worker writes a *new* `<code>.mthds` definition file and never edits an existing one — the safest possible parallel-write story. The pipelex support for it — all **shipped** on branch `feature/Support-recursive-design` (plan: `_recursive/TODOS.md`, follow-ups: `_recursive/HANDOFF-recursive-followups.md`):

- **Signature/concrete reconciliation (Part A).** When the library merge sees the same code declared as a signature and as a concrete pipe, the **concrete satisfies the signature** (definition wins) instead of raising a duplicate-code error. Their `inputs`/`output` must match by **concept identity** — bare↔qualified and native spellings are equivalent, multiplicity compared structurally (not byte-string); refinement substitutability stays deferred. Two concrete definitions of one code, or two signatures with differing contracts, remain a hard error.
- **Library-level concept resolution (Part B).** Concept references resolve against the **merged** library, not per file, so a pipe in one file can reference by bare code a concept declared in a sibling file of the same domain (across `-L` directory batches too). A concept declared twice remains a `ConceptLibraryError`; an unresolvable reference now surfaces as a structured validation error rather than a raw traceback.
- **`pending_signatures` on validate.** A successful `validate bundle` emits `pending_signatures` — the library-wide list of pipes still typed `PipeSignature` (namespaced refs; empty when complete) — as a JSON field and a "Pending signatures" markdown section, on the agent-CLI and builder surfaces. This is the source for the hook's leftover-signature nudge (§5.2).

**Emit explicit `inputs`/`output` (spelling is free).** Contracts reconcile by **concept identity**, so a header's `output = "Brief"` and a definition's `output = "thisdomain.Brief"` match fine — bare-vs-qualified spelling need not agree. What *does* still hold: pipes do **not** infer `inputs` from prompt sigils, so a `PipeLLM` whose prompt references `$doc` but omits an `inputs` block keeps `inputs = None`, which mismatches a header declaring `{ doc = "Document" }`. So both the orchestrator (forward-declaring) and the worker (defining) must declare `inputs` and `output` **explicitly** — that is the one authoring rule the additive flow adds (the *spelling* of those refs is now flexible).

With these rules: the orchestrator forward-declares a controller's children (headers) when it wires them; each worker **adds** a definition file; headers persist after they're satisfied, so the backlog is **declared codes with no concrete definition yet** (`{signature codes} − {concrete codes}`) — exposed directly by validate as `pending_signatures`, recomputed each layer. Concepts have no signature form, so colliding intermediate concepts are still caught.

> **Why the old overwrite-in-place model is retired.** Earlier drafts of this doc swapped a stub by *overwriting* its file, presented as a working fallback until reconciliation shipped. It never actually worked for the common case — a pipe whose contract uses a non-native concept (nearly all of them). Concept references were validated **per file**, so a definition file referencing a concept declared in a sibling file was rejected *before* the merge, and declaring that concept in both files tripped the duplicate-concept guard: no authoring path through. Part B is what unblocks *any* multi-file model; Part A is what makes it specifically additive. Both were required — with them shipped, overwrite-in-place is gone, not merely disfavored.

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

**Leftover-signature nudge (adopted).** On lenient success, read the **`pending_signatures`** array from the `validate bundle --format json` output (the library-wide list of pipes still typed `PipeSignature`, namespaced refs; empty when complete). This is a **new success-path branch** — today the hook only inspects validate output on failure — so the JSON envelope is parsed (rather than scraping the markdown "Pending signatures" section, which is brittle). If the array is non-empty, emit a *non-blocking* `additionalContext` note listing them ("signatures remain — implement before running"). Use this field **directly** — not a `grep -q '"PipeSignature"'`, which false-positives now that headers persist additively after they're satisfied. Gives the agent an in-progress reminder without blocking. Mirror in the Codex hook (§5.3).

> **Decision D3 (post-review) — single invocation + a confirmation the original plan missed.** Stage 3 runs **one** call, `... -L <dir> --allow-signatures --format json`: parse `pending_signatures` from JSON **stdout** on success; keep parsing the **markdown error report on stderr** on failure (the existing `error_domain` classifier at hook lines ~108/119). This works only if `--format json` leaves errors as markdown-on-stderr — which two static reads of the pipelex source **disagreed** on. So Phase 0 must **run a failing validate with the flag and confirm it empirically**; if errors become JSON too, fall back to **two invocations** (one markdown for classify/block, one JSON for the nudge) at the cost of validating the library twice per save. The failure-path classifier change is a **regression risk** (it affects vibe/build/hand-edits, not just recursive builds) and is covered by mandatory regression tests R1–R3.

### 5.3 Codex hook parity

The Codex hook (`mthds-agent codex hook`, logic in `mthds-js`) runs the analogous `pipelex-agent validate bundle` at its Stage 3. It needs the same change — pass `--allow-signatures` (and, optionally, the same leftover-signature note). This is a code change in `mthds-js`, paired with the shell-hook change here.

> **v1 recommendation (post-review):** ship **only `--allow-signatures`** on the Codex hook; **skip** the `--format json`/nudge. Adding `--format json` re-opens the same success-vs-error format coupling (D3) on the Codex side (`classifyStage3Result()` also parses markdown stderr), and the orchestrator skill already tracks `pending_signatures` itself — so the Codex nudge is a redundant reminder, not load-bearing. Defer the Codex nudge to a follow-up.

### 5.4 mthds-agent — already sufficient

`mthds-agent validate` forwards unknown flags verbatim to the pipelex CLI (`.allowUnknownOption()`), so `--allow-signatures` already reaches pipelex today; no new option needs to be defined. The backlog is already exposed as `pending_signatures` on `validate bundle` (the unsatisfied set, library-wide), so no separate `mthds-agent list signatures` helper is needed. Optional polish only: expose/document `--allow-signatures` explicitly in `mthds-agent` and in the `mthds-agent-guide` shared reference.

---

## 6. Decisions (resolved)

- **Naming/connotation.** Keep the `mthds-recursive` name — it still fits a layer-by-layer process. Update only the skill `description` to reflect top-down, valid-at-every-step refinement.
- **Invocation.** The skill stays **explicit-invocation-only** (`disable-model-invocation: true` for non-Codex, as today). A recursive build is a deliberate, potentially long multi-step action the user launches with `/mthds-recursive` — not something the model triggers from chat. The rewrite (§7 item 4) must preserve this frontmatter.
- **Fan-out target scope.** *(Revised post-review, D1.)* Parallel fan-out is **deferred to a follow-up on both targets** — v1 runs the layer loop **inline/serial** on Claude and Codex alike (§4.4; rationale in [`../deferred-issues.md`](../deferred-issues.md)). The original plan shipped fan-out on Claude (the `agents/` worker + Agent tool) with Codex inline; the review pulled the whole `agents/` build-system chunk (and its open auto-discovery question) out of v1. Codex sub-agents can't be bundled in the plugin anyway (no `agents` manifest field) — they'd be installed as `.codex/agents/*.toml` via `mthds-agent codex apply-config`. Both Claude and Codex fan-out are in the same follow-up.
- **Scope limits.** Keep vibe's current limits (`dict`, `PipeStructure`, inline `templating_style`) as-is for this work. Revisiting them is tracked separately in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).
- **Delivery format / file layout.** The builder produces a **multi-file, same-domain library**, built additively (one concrete definition per file, headers reconciled at merge; §2.7). Keep small files for now. An optional final *flatten into one `bundle.mthds`* is deferred — tracked in [`../deferred-issues.md`](../deferred-issues.md).
- **Runtime relaxation (signature = header) — shipped.** The pipelex library merge now reconciles a `PipeSignature` with a concrete pipe of the same code (definition wins; contracts reconciled by **concept identity** — bare↔qualified/native equivalent, structural multiplicity), and concept references resolve at library level so cross-file bare refs work (§4.5). Validate also emits **`pending_signatures`** (the library-wide unsatisfied-header list) for the hook nudge. All landed on branch `feature/Support-recursive-design` (plan: `_recursive/TODOS.md`, follow-ups: `_recursive/HANDOFF-recursive-followups.md`) and ride the next pipelex release. The additive model is now the working model — overwrite-in-place is **retired**, not a fallback.
- **`mthds-build` relationship.** Build stays separate. It *could* later adopt the same signature-driven loop (its markdown drafts replaced by a live leniently-valid bundle). Out of scope here.
- **Version floor.** Lenient validation (`PipeSignature` + `--allow-signatures`) requires pipelex ≥ `0.31.0`. The **additive** model additionally requires the signature/concrete reconciliation + library-level concept resolution (Part A+B), which are **unreleased** — currently only on branch `feature/Support-recursive-design`. The floor for the additive flow is therefore *the first pipelex release after `0.31.0` that carries them* (> `0.31.0`), not `0.31.0` itself. `min_mthds_version` (`targets/defaults.toml`) tracks the **mthds-agent** version (currently `0.9.0`), not pipelex — so the bump is to *the mthds-agent version that ships/requires that pipelex release*. Determine that mthds-agent version and bump via `/bump-mthds-version`. **Open:** the exact pipelex release carrying Part A+B, and the matching mthds-agent version.
  - **⚠ Watch-item (decision D4 — floor effectiveness).** Bumping `min_mthds_version` enforces an **mthds-agent** floor only. mthds-agent spawns `pipelex`/`pipelex-agent` by **bare name through `PATH`** (decoupled), and the plugin's env-check (`preamble.md.j2`) emits only `MTHDS_AGENT_OUTDATED` — there is **no `PIPELEX_OUTDATED`/`PLXT_OUTDATED` enforcement**. So a user can satisfy the mthds-agent floor while running pipelex `0.31.0` and hit a loud-but-**opaque** `PipeLibraryError` at Layer 1. Before the prod release, **confirm** that the chosen mthds-agent version actually pins/requires the right pipelex (or add a direct pipelex-version guard in `mthds-env-check` or the skill's Step 0). Also confirm the **plxt** `PipeSignature` schema floor (~`v0.9.0`, in `vscode-pipelex`'s `mthds_schema.json`) — a second runtime floor the original plan didn't name. v1 ships behind a **single release gate** (the whole feature waits for the pipelex release; the hook/docs are no-ops on signature-free bundles and *could* ship early, but the decision was one gate for simplicity).
- **`additionalContext` nudge** (§5.2) — **adopt it.** On lenient success with unsatisfied headers remaining, emit the non-blocking reminder — sourced from the `pending_signatures` field on `validate bundle` (not a grep, since headers persist under the additive model).

---

## 7. Implementation plan

*Runtime prerequisite (pipelex) — **done**: the signature/concrete reconciliation + library-level concept resolution that enable the additive model, the normalized (concept-identity) contract check, and the `pending_signatures` list on validate (§4.5) all shipped on branch `feature/Support-recursive-design` (per `_recursive/TODOS.md` + `_recursive/HANDOFF-recursive-followups.md`) and ride the next pipelex release. The steps below assume the additive model throughout.*

1. **Unblock signatures in the hook.** Add `--allow-signatures` to `templates/hooks/validate-mthds.sh.j2` Stage 3; `make build`. This is foundational and independent of the skill rewrite.
   - **Checkpoint** — with the hook lenient, a hand-written signature-containing bundle can be saved without being blocked, while a signature-free bundle still validates exactly as before. Verify via the `internal-tools` integration suite (`make build && make agent-test`), which is the safety net for the hook/install system.
2. **Document the primitive.** Add the `PipeSignature` / `signature_for` / lenient-vs-strict section to `skills/mthds-recursive/references/recursive-cheat-sheet.md` and the `mthds-agent-guide` shared reference.
3. **⛔ DEFERRED (follow-up, D1) — Author the `expand-signature` instructions + worker agent.** Not in v1. v1 keeps the expansion job **inline in the skill's Step 2** (single consumer — no shared partial). The original item is retained as the follow-up's spec: write the uniform expansion job once; ship it as the `mthds-signature-expander` sub-agent (new `agents/` plugin component — **Claude target only**) and as the orchestrator's inline-path reference. Tools limited to Read + Write (the one definition file it adds) + validate; the worker **adds** its `<code>.mthds` definition (and, if it became a controller, forward-declares its child headers + owns new concepts in that same file) — additive, never overwriting, no merge (§4.4). It must declare `inputs`/`output` **explicitly** (pipes don't infer from sigils); their *spelling* need not match the header byte-for-byte — reconciliation is by concept identity (§4.5). The expansion **authoring rules** themselves (additive single-file write, explicit inputs/output, derive child/concept codes from the parent) still apply in v1 — they just live in the skill body, not a worker prompt.
4. **Rewrite the skill (orchestrator).** Replace the single-pass body of `templates/skills/mthds-recursive/SKILL.md.j2` with the Step 0–4 recursive flow, the autonomy model, and the Step 2 **inline/serial** additive add-a-definition loop (backlog = `{signatures} − {concretes}`, recomputed from the library each layer via `pending_signatures`; §4.4). Include the **concept-collision prevention** rule (D5 — check before introducing) and the contract-mismatch rule (conform the definition to the frozen header, never edit the header). No fan-out, no `{% if platform != "codex" %}` fan-out block (D1). Update the skill `description`; **preserve `disable-model-invocation: true`** for non-Codex (§6 "Invocation"). `make build` + `/reload-plugins` to dogfood.
5. **Codex parity (hook only).** Mirror §5.2/§5.3 in the `mthds-js` Codex hook (`--allow-signatures` + the `--format json` `pending_signatures` nudge). Codex *orchestration* fan-out is out of scope for v1 — the recursive loop runs inline under Codex (§6 "Fan-out target scope"); the rewritten skill's fan-out section renders for the Claude target only.
6. **Validate end-to-end.** `make build && make check`; run the `internal-tools` integration tests; dogfood the recursive flow on a real multi-layer method (e.g. the §3 example), exercising both inline and fan-out layers, and confirm lenient-per-layer → strict-at-end behaves as designed.
   - **Checkpoint** — recursive `mthds-recursive` produces a runnable method through layered refinement (fanning out workers on multi-signature layers), every intermediate save passes the (now-lenient) hook, and the final strict gate holds. Ready to ship.

---

## GSTACK REVIEW REPORT

_Eng review on 2026-06-07 (commit `5c755c3`). Scope reduced: **fan-out (Phase 3) deferred to a follow-up** — v1 runs the layer loop inline/serial on both targets._

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN (SCOPE_REDUCED) | 5 gated findings + 7 test gaps, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | n/a | non-visual change |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**Decisions locked (D1–D7):**
- **D1** — Defer fan-out / the `agents/` plugin component to a follow-up. v1 = inline/serial on both targets (correctness identical). `expand-signature` shared partial drops out (single consumer); instructions live inline in the skill.
- **D2** — A domain-only member file must validate with `-L` (no `main_pipe`). Phase 0 confirms; any failure is a pipelex bug fixed in `../_recursive`, not a hook workaround.
- **D3** — Hook Stage 3 uses one invocation `--allow-signatures --format json`; Phase 0 must empirically confirm errors still arrive as markdown-on-stderr (fall back to two invocations if not).
- **D4** — One release gate: hold the whole feature behind the pipelex Part A+B release; bump `min_mthds_version`; trust the floor. ⚠ residual: confirm the mthds-agent floor actually enforces a pipelex minimum (decoupled, PATH-resolved) — else old-pipelex users hit a loud-but-opaque Layer-1 failure.
- **D5** — Serial v1 prevents intermediate-concept collisions up front (check-before-introduce in skill Step 2); `ConceptLibraryError` stays the backstop. Parallel-collision handling re-introduced with fan-out.
- **D6** — Outside voice skipped.
- **D7** — Eval harness for skill behavior deferred to a separate `.md` design doc (`wip/recursive/eval-harness.md`), §3 example as seed; v1 ships dogfood-only.

**Test posture:** R1–R3 regression tests (signature-free unchanged; input-domain still blocks; config/runtime still warns — all under the new flags) are MANDATORY (IRON RULE). New-path N1–N4 added. Skill behavior is dogfood-only.

**UNRESOLVED:** 0 decisions. One watch-item (D4 floor effectiveness) carried into Phase 0/6.4.

**VERDICT:** ENG CLEARED (scope reduced) — ready to implement v1. The pipelex foundation (Part A+B, `--allow-signatures` no-op-on-signature-free, `pending_signatures`) is verified shipped+tested on `../_recursive`; the prod release gates on that pipelex release landing.
