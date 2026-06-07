# Recursive Method Building — Design Doc

Origin: [kick-off.md](kick-off.md). This doc turns that kick-off into a methodology and a concrete skill design.

## TL;DR

Build a `.mthds` method **top-down by stepwise refinement**, where every intermediate state is a real, validatable library (a set of same-domain `.mthds` files, built additively — one definition per file). Start by capturing the whole job as a *single pipe signature* — the client contract (inputs, output, semantics). Then refine one signature at a time, one level down, into operators and controllers, leaving the not-yet-built parts as further signatures. Validate **leniently** (`--allow-signatures`) after each layer; the library is always valid and always resumable. Stop when no signatures remain (strict validation passes → runnable), or stop early and keep the leniently-valid scaffold.

This is an **in-place evolution of `mthds-vibe`**: its current single-pass authoring becomes recursive layer-by-layer refinement.

The capability that unlocks this shipped in pipelex (the `PipeSignature` pipe type + `--allow-signatures` lenient validation, worktree `../_recursive`); the merge-time **signature/concrete reconciliation + library-level concept resolution** that make the build *additive* (§4.5) have since shipped on the same worktree branch. It is already reachable through `mthds-agent` today via flag passthrough — no CLI plumbing required. The one piece of tooling that must change is the PostToolUse hook (see [Required tooling changes](#required-tooling-changes)).

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

- **Contract stability.** A definition must preserve its header's `inputs` and `output` **exactly** (string-equal — the definition reconciles with the header only on a matching contract); the parent depends on that contract. You may freely choose a signature's *internals*; you may not change its surface without revising the parent too (a more expensive, propagating change — flag it when it happens).
- **`main_pipe` is the anchor.** The top signature's code and its inputs/output are frozen after Layer 0; refinement supplies its body as a separate definition file (reconciled with the frozen header) but never changes its identity or surface. This is the client contract.
- **Concepts refine lazily.** Boundary concepts are specified at Layer 0. Intermediate concepts are introduced simple (often `refines` a native) and gain `structure` only when a downstream consumer references specific fields — at that point structure the concept. (A signature mints a mock of its declared output; if a consumer reads `$x.field`, `x`'s concept must declare `field`.)
- **Error localization.** A lenient-validation failure after a step is, by construction, in the step you just added — bounding the fix.
- **Scope.** Recursive building adds `PipeSignature` (+ `signature_for`) to vibe's emittable set. The existing scope limits (no `dict`, no `PipeStructure`, no inline `templating_style`) are orthogonal to the strategy and stay as-is for now; revisiting them is tracked in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).

### 2.7 Artifact layout — a multi-file, same-domain library (additive)

The artifact is not one growing file but a **library**: a directory of `.mthds` files that all declare the same `domain`, loaded together with `-L`. The runtime merges them into one domain, and pipes/concepts reference each other across files by bare code (`LibraryCrateFactory`, `PipeLibrary`).

Construction is **additive**: a `PipeSignature` is a C-style **forward declaration** ("header") and the concrete pipe is its **definition**. Expanding a signature **adds a new definition file**; no existing file is ever rewritten. (The earlier overwrite-in-place model is retired — see §4.5 for why, and why it never actually worked for the common case.)

- **Header + definition, one concrete per file.** A child pipe is **forward-declared as a `PipeSignature` header** inline in the file of the parent that wires it — the moment the parent references it. Expanding it = **adding a separate `<code>.mthds` file** holding the concrete definition. At merge, the header and the definition reconcile (the **concrete wins**), so the same code legitimately appears as a header in one file and a concrete in another. Each pipe has **at most one concrete definition file**; the caller only ever references the child by bare code, and both that reference and the header are stable across the expansion.
- **Why additive works (and what's still a hard error).** Two *concrete* pipes with the same code remain a **hard error** (`PipeLibraryError`), as do two signatures with mismatched contracts — a free safety net against accidental duplicates. What changed: a signature + a concrete of the same code now **reconcile** instead of colliding (Part A). And concept references resolve against the **merged** library, not per file (Part B), so a pipe in one file can reference by bare code a concept declared in a sibling file. Concepts have **no signature form**, so a concept declared twice is still a `ConceptLibraryError` — colliding intermediate concepts are still caught.
- **Contract must match exactly.** A header and its definition must carry **identical, explicit `inputs` and `output`** — string-equal at merge (multiplicity included). Pipes do **not** infer `inputs` from prompt sigils, so a header that lists `inputs` and a definition that omits them is a contract mismatch and errors. Both the orchestrator (when it forward-declares) and the worker (when it defines) must emit the same explicit contract. See §4.5.
- **Root file.** One file (`bundle.mthds`) is the root: it carries the `domain` header, the `main_pipe` directive, and the boundary concepts — plus the top pipe's `PipeSignature` header (Layer 0). It is written once and **persists**; the concrete main pipe is added in its own `<main_pipe>.mthds` file like any other definition (`main_pipe` is a reference, not the implementation). Every other file repeats the same `domain` header; only the root's `main_pipe` counts (first-write-wins; the rest are ignored, with a warning).
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

What this illustrates: the top contract frozen at Layer 0; a mixed layer where one child is defined immediately while siblings stay headers; expansion as **adding a definition file** that reconciles with a persistent header (the call tree never re-wires, and no file is ever overwritten); intermediate concepts introduced lazily and owned by the file that introduces them; the exact-match header/definition contract; `signature_for` pre-deciding each expansion; and the lenient → strict transition (empty backlog) as the definition of "done".

---

## 4. Skill design — evolving `mthds-vibe` in place

Same skill, same name/slot (`templates/skills/mthds-vibe/SKILL.md.j2`). The single-pass body is replaced by the recursive loop. The shared `Step 0` env-check, the deliver step, and the "never write `inputs.json`" rule carry over unchanged.

### 4.1 Step structure

- **Step 0 — Environment check.** Unchanged (`{% include 'skills/shared/preamble.md.j2' %}`). No backend/keys needed — building and validating never run the method.
- **Step 1 — Capture the top-level requirement as one signature.** Determine input concept(s), output concept, and a precise description; specify boundary concepts fully. Write the **root file** `bundle.mthds` (the `domain` header, `main_pipe`, and the fully-specified boundary concepts) with a single `PipeSignature` as the main pipe. Validate leniently. *This is the only step with optional interactivity* (see Autonomy). Announce the captured contract in one line before recursing, so the user can interject without being blocked by a question.
- **Step 2 — Refine layer by layer (auto), fanning out.** Work the signature backlog — the headers with no definition yet (`{signature codes} − {concrete codes}`) — breadth-first by layer. For a layer with one pending signature, expand inline; for several, **fan out one `mthds-signature-expander` sub-agent per signature** (see §4.4). Each worker **adds a new `<code>.mthds` definition file** (an operator, or a controller that also forward-declares its child headers and declares the concepts it owns) — never overwriting an existing file, no merge step. Validate the assembled library leniently (`-L <dir> --allow-signatures`); on failure, fix the offending file and re-validate. Recompute the backlog from the assembled library and repeat until it is empty (or the user stopped early).
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

**Orchestrator vs worker.** `mthds-vibe` is the **orchestrator**: it owns the library dir, the backlog, the layer loop, per-layer validation, and finalize. The **worker** is a dedicated sub-agent type (`mthds-signature-expander`) whose system prompt *is* the `expand-signature` job, with tools limited to Read + Write (scoped to the one file it adds) + the validate command. It **adds one file**: the `<code>.mthds` *definition* for the signature it was handed — it never edits an existing file.

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

**Contract & collisions.** A worker must reproduce its target's `inputs`/`output` **exactly and explicitly** in the definition (string-equal at merge, multiplicity included; pipes don't infer `inputs` from prompt sigils — see §4.5), so the definition reconciles with the header. Same domain = one shared namespace, so workers name the children they spawn by deriving from their own pipe code (namespacing by parent). Two *concrete* definitions of one code, or a definition whose contract diverges from its header, are a **hard error** at validation (never silent) — the orchestrator resolves the rare conflict. Each concept is declared once, in the file of the pipe that introduces it.

**Why it pays off.** Beyond speed: each worker sees only its signature's contract + referenced concepts — not the whole library — so contexts stay small and sharp, which improves expansion quality as well as parallelism. The `expand-signature` instructions are authored once and serve as both the worker's system prompt and the orchestrator's inline-path reference — one source of truth. This adds an `agents/` component to the plugin, templated like the skills to keep the multi-target build consistent.

> The fan-out here is skill-level (the orchestrator uses the Agent tool when run). The same layer loop maps cleanly onto the Workflow tool if we ever want deterministic, journaled orchestration — but that is not required for the skill.

### 4.5 Runtime support — `PipeSignature` as a header (shipped)

The additive model (§2.7, §3, §4.4) treats a `PipeSignature` as a C-style **forward declaration** ("header") and the concrete pipe as its **definition**: a worker writes a *new* `<code>.mthds` definition file and never edits an existing one — the safest possible parallel-write story. Two merge-time rules in pipelex make it work; both **shipped** on branch `feature/Support-recursive-design` (plan: `_recursive/TODOS.md`):

- **Signature/concrete reconciliation (Part A).** When the library merge sees the same code declared as a signature and as a concrete pipe, the **concrete satisfies the signature** (definition wins) instead of raising a duplicate-code error. Their `inputs`/`output` must match **exactly** — string-equal at merge, multiplicity included. Two concrete definitions of one code, or two signatures with differing contracts, remain a hard error.
- **Library-level concept resolution (Part B).** Concept references resolve against the **merged** library, not per file, so a pipe in one file can reference by bare code a concept declared in a sibling file of the same domain (across `-L` directory batches too). A concept declared twice remains a `ConceptLibraryError`; an unresolvable reference now surfaces as a structured validation error rather than a raw traceback.

**The exact-match contract — emit explicit `inputs`/`output` on both sides.** Reconciliation compares the raw blueprint strings *before* concepts resolve, so it can only compare what is written. Pipes do **not** infer `inputs` from prompt sigils — a `PipeLLM` whose prompt references `$doc` but omits an `inputs` block keeps `inputs = None`, which would *mismatch* a header that declares `{ doc = "Document" }`. So both the orchestrator (forward-declaring the header) and the worker (writing the definition) must emit **identical, explicit** `inputs` and `output`. This is the one authoring rule the additive flow adds.

With these rules: the orchestrator forward-declares a controller's children (headers) when it wires them; each worker **adds** a definition file; headers persist after they're satisfied, so the backlog is **declared codes with no concrete definition yet** (`{signature codes} − {concrete codes}`), recomputed each layer. Concepts have no signature form, so colliding intermediate concepts are still caught.

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

**Leftover-signature nudge (adopted).** On lenient success, emit a *non-blocking* `additionalContext` note listing the **unsatisfied headers** — signatures with no concrete definition yet ("signatures remain — implement before running"). Source these from the **validator's own reachable-signature report**, not a `grep -q '"PipeSignature"'`: under the additive model headers persist after they're satisfied, so the literal string lingers even when the library is complete — but the merge replaces a reconciled signature with its concrete, so the pre-pass reports only the genuinely-unbuilt ones. Gives the agent an in-progress reminder without blocking. Mirror in the Codex hook (§5.3).

### 5.3 Codex hook parity

The Codex hook (`mthds-agent codex hook`, logic in `mthds-js`) runs the analogous `pipeline-agent validate bundle` at its Stage 3. It needs the same change — pass `--allow-signatures` (and, optionally, the same leftover-signature note). This is a code change in `mthds-js`, paired with the shell-hook change here.

### 5.4 mthds-agent — already sufficient

`mthds-agent validate` forwards unknown flags verbatim to the pipelex CLI (`.allowUnknownOption()`), so `--allow-signatures` already reaches pipelex today; no new option needs to be defined. Optional polish: expose/document it explicitly in `mthds-agent` and in the `mthds-agent-guide` shared reference, and consider a small `mthds-agent list signatures` helper that reports the backlog as the **unsatisfied** set (`{signatures} − {concretes}`) — not every header, since under the additive model satisfied headers persist. Not required for the feature.

---

## 6. Decisions (resolved)

- **Naming/connotation.** Keep the `mthds-vibe` name — it still fits a layer-by-layer process. Update only the skill `description` to reflect top-down, valid-at-every-step refinement.
- **Scope limits.** Keep vibe's current limits (`dict`, `PipeStructure`, inline `templating_style`) as-is for this work. Revisiting them is tracked separately in [`../revisit-vibe-scope-limits.md`](../revisit-vibe-scope-limits.md).
- **Delivery format / file layout.** The builder produces a **multi-file, same-domain library**, built additively (one concrete definition per file, headers reconciled at merge; §2.7). Keep small files for now. An optional final *flatten into one `bundle.mthds`* is deferred — tracked in [`../deferred-issues.md`](../deferred-issues.md).
- **Runtime relaxation (signature = header) — shipped.** The pipelex library merge now reconciles a `PipeSignature` with a concrete pipe of the same code (definition wins; contracts must match **exactly**), and concept references resolve at library level so cross-file bare refs work (§4.5). Both landed on branch `feature/Support-recursive-design` (plan: `_recursive/TODOS.md`) and ride the next pipelex release. The additive model is now the working model — overwrite-in-place is **retired**, not a fallback.
- **`mthds-build` relationship.** Build stays separate. It *could* later adopt the same signature-driven loop (its markdown drafts replaced by a live leniently-valid bundle). Out of scope here.
- **Version floor.** Lenient validation (`PipeSignature` + `--allow-signatures`) requires pipelex ≥ `0.31.0`. The **additive** model additionally requires the signature/concrete reconciliation + library-level concept resolution (Part A+B), which are **unreleased** — currently only on branch `feature/Support-recursive-design`. The floor for the additive flow is therefore *the first pipelex release after `0.31.0` that carries them* (> `0.31.0`), not `0.31.0` itself. `min_mthds_version` (`targets/defaults.toml`) tracks the **mthds-agent** version (currently `0.9.0`), not pipelex — so the bump is to *the mthds-agent version that ships/requires that pipelex release*. Determine that mthds-agent version and bump via `/bump-mthds-version`. **Open:** the exact pipelex release carrying Part A+B, and the matching mthds-agent version.
- **`additionalContext` nudge** (§5.2) — **adopt it.** On lenient success with unsatisfied headers remaining, emit the non-blocking reminder — sourced from the validator's reachable-signature report (not a grep, since headers persist under the additive model).

---

## 7. Implementation plan

*Runtime prerequisite (pipelex) — **done**: the signature/concrete reconciliation + library-level concept resolution that enable the additive model (§4.5) shipped on branch `feature/Support-recursive-design` (per `_recursive/TODOS.md`) and ride the next pipelex release. The steps below assume the additive model throughout.*

1. **Unblock signatures in the hook.** Add `--allow-signatures` to `templates/hooks/validate-mthds.sh.j2` Stage 3; `make build`. This is foundational and independent of the skill rewrite.
   - **Checkpoint** — with the hook lenient, a hand-written signature-containing bundle can be saved without being blocked, while a signature-free bundle still validates exactly as before. Verify via the `internal-tools` integration suite (`make build && make agent-test`), which is the safety net for the hook/install system.
2. **Document the primitive.** Add the `PipeSignature` / `signature_for` / lenient-vs-strict section to `skills/mthds-vibe/references/vibe-cheat-sheet.md` and the `mthds-agent-guide` shared reference.
3. **Author the `expand-signature` instructions + worker agent.** Write the uniform expansion job once; ship it as the `mthds-signature-expander` sub-agent (new `agents/` plugin component, templated like the skills) and as the orchestrator's inline-path reference. Tools limited to Read + Write (the one definition file it adds) + validate; the worker **adds** its `<code>.mthds` definition (and, if it became a controller, forward-declares its child headers + owns new concepts in that same file) — additive, never overwriting, no merge (§4.4). It must emit explicit `inputs`/`output` matching the header **exactly** (§4.5).
4. **Rewrite the skill (orchestrator).** Replace the single-pass body of `templates/skills/mthds-vibe/SKILL.md.j2` with the Step 0–4 recursive flow, the autonomy model, and the Step 2 fan-out + additive add-a-definition loop (backlog = `{signatures} − {concretes}`, recomputed from the library each layer; §4.4). Update the skill `description`. `make build` + `/reload-plugins` to dogfood.
5. **Codex parity.** Mirror §5.2/§5.3 in the `mthds-js` Codex hook.
6. **Validate end-to-end.** `make build && make check`; run the `internal-tools` integration tests; dogfood the recursive flow on a real multi-layer method (e.g. the §3 example), exercising both inline and fan-out layers, and confirm lenient-per-layer → strict-at-end behaves as designed.
   - **Checkpoint** — recursive `mthds-vibe` produces a runnable method through layered refinement (fanning out workers on multi-signature layers), every intermediate save passes the (now-lenient) hook, and the final strict gate holds. Ready to ship.
