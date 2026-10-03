# Signature-driven stepwise construction

Read this when step 3 of the skill chooses stepwise construction, before writing any file, and when step 4's direct construction would need a placeholder or a guessed contract, or exposes an unresolved structural boundary, before changing any file. Stepwise is the mode wherever a direct write is not safe: nested controllers or multiple structural layers whose child contracts are not all fixed; uncertain sub-pipe contracts, intermediate concept ownership, branching, iteration, or wiring; shared concepts whose shapes depend on consumers in different branches; a large graph that benefits from independently valid review checkpoints; or an explicit request for a scaffold, partial design, staged work, or a resumable intermediate result. This file is the additive, breadth-first construction loop and its valid intermediate checkpoints. The skill's guards hold throughout, and the syntax of `PipeSignature` and `signature_for` is the language reference's, read before writing.

Stepwise mode materializes uncertainty. Every not-yet-designed pipe is a reachable `PipeSignature`. Each refinement adds one concrete definition file, may introduce child signatures, and is validated immediately. The pending-signature verdict is the resumable backlog. Stepwise mode refines automatically, without per-layer approval: valid checkpoints, and the `dry_run.html` flowchart each validation redraws, are the review surface.

## Validating a scaffold

Every validation in this mode is lenient, since the bundle still reaches signatures by design:

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --allow-signatures --graph
```

While signatures remain, the Markdown verdict shows a `## Pending signatures (N)` heading, a `⚠️ This method is NOT yet runnable …` line and one bullet per pipe still declared as a signature. That bullet list is the backlog. When it is empty, the verdict prints `✅ All pipes are concretely implemented … this method is runnable.` and no pending section.

## Coming from a direct draft

When direct construction would need a placeholder or a guessed contract, or exposed an unresolved structural boundary, stop extending the direct draft and transition:

1. Keep the announced root contract and boundary concept shapes stable unless the evidence shows the client requirement itself was wrong.
2. Compose the replacement scaffold in memory. Its root keeps bundle metadata and boundary concepts, replaces the main concrete graph with one root `PipeSignature`, and removes abandoned direct-only intermediate concepts and concrete child definitions that the refinement files will own.
3. Replace the candidate file set as one consistent layout. Do **not** append signatures beside the abandoned concrete definitions: keeping both drafts would create duplicate concepts, conflicting concrete pipes, or falsely satisfied signatures. Re-read the directory and confirm every pipe and concept code is declared only where the stepwise model permits it: one root header, then one later concrete per pending code; each concept exactly once.
4. Validate the root scaffold before adding definitions. It must be valid with the root pipe in the pending list; then continue at "Refine layer by layer" below.

This replacement is the construction-mode transition, not an additive refinement.

## The root scaffold

Write `bundle.mthds` in the bundle home with your agent's file tools, carrying:

- `domain`, `description`, `main_pipe`, optional `system_prompt`;
- the fully specified boundary concepts;
- the top pipe as one `PipeSignature` whose code is `main_pipe`, with its precise `description`, explicit `inputs`, `output`, and `signature_for`.

```toml
domain      = "<snake_case_domain>"
description = "<what the job means>"
main_pipe   = "<top_pipe_code>"

# boundary concepts, specified fully

[pipe.<top_pipe_code>]
description   = "<precise semantics of the whole job>"
inputs        = { <name> = "<InputConcept>" }
output        = "<OutputConcept>"
signature_for = "<intended implementation type, e.g. PipeSequence>"
```

The root is written once for this construction mode, and its main pipe's concrete definition arrives later in a file of its own, like any other. Validate it: the one-signature library must pass with the top pipe listed as pending. An explicit partial-scaffold request may stop after any later valid checkpoint, but never before this first passing verdict.

## Refine layer by layer

Drain the signature backlog breadth-first, **serially** (one signature at a time — no parallel workers in this version):

1. Validate and read the backlog from the `## Pending signatures` list. This verdict is the bundle's own todo list.
2. Expand each current pending signature one at a time. Every expansion adds exactly one new `<code>.mthds` definition file and never edits an existing construction file.
3. Re-validate after each expansion, recompute the backlog, and repeat until it is empty.

### Expand one signature

Given pending signature `S` with frozen `inputs`, `output`, `description`, and `signature_for`:

1. Decide operator or controller. A single cognitive or IO step is an operator; multiple steps, iteration, branching, or parallelism require a controller.
2. Add `<code>.mthds`, using `S`'s **bare** pipe code. The verdict names signatures as `domain.code`, but a namespaced `[pipe.domain.code]` would define a different pipe and never satisfy the header. A non-root file carries only `domain = "<same_domain>"` for membership. If the code is literally `bundle`, use a non-colliding filename such as `bundle_pipe.mthds`; filenames do not define pipe identity.
3. For a leaf, write the concrete operator (`PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`) with all type-specific fields. For a controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire one structural level, declare only intermediate concepts not already owned by the assembled library, and forward-declare every not-yet-designed child as a new `PipeSignature` in the same file.
4. Repeat `S`'s explicit `inputs` and `output` on the concrete definition. Contracts reconcile by concept identity (bare and qualified spellings, native equivalents), not textual coincidence.
5. Before introducing an intermediate concept, check its code across the assembled library. Derive a unique parent-based code if needed. Declare it once, in the controller that logically introduces it, with a shape fixed from every wired consumer: a later file can never add fields to it. If consumers in different branches field-read it, the common parent owns and structures it.

### If validation fails after an expansion

The new file bounds the ordinary fix:

- **Contract mismatch:** conform the definition to the frozen header. If the header itself is wrong, that is a propagating contract change; pause and revise the parent region deliberately rather than silently changing the header.
- **Other semantic errors:** use the error list, its locators, and the relevant section of the language reference; fix the added file and re-validate.

## Converging

When the verdict prints the `✅ … this method is runnable.` line, validate once more **without** `--allow-signatures`, the form the skill's runnable gate takes. A signature is never a validation error, so the gate is that line, which only an empty backlog prints, not the pass alone; then go on to the skill's step 6.

## Stopping early

Early stopping exists only in stepwise mode. When the user requested a partial scaffold or interrupts before convergence, confirm the lenient validation passes, report the exact pending-signature backlog, and explain that resuming means expanding those signatures: no state outside the bundle is needed. Do not claim it is runnable.

## The rules of this mode

- **Additive refinement.** After the root scaffold, every refinement adds one concrete definition file; existing construction files and satisfied headers persist.
- **One concrete definition per refinement file.** This keeps failures bounded and checkpoints resumable.
- **Backlog = `{signatures} − {concretes}`.** Recompute it from the verdict after every expansion; never hand-track it.
- **The root file is written once.** Direct construction is not subject to this construction-history rule.
