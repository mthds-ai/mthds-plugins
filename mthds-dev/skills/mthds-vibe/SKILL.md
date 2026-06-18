---
name: mthds-vibe
description: Build a method bundle top-down by stepwise refinement — capture the whole job as one pipe signature, then refine it layer by layer into a runnable method that is valid at every step.
disable-model-invocation: true
min_mthds_version: 0.10.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Build a MTHDS bundle top-down (recursive refinement)

Build a `.mthds` method **top-down by stepwise refinement**. Capture the whole job as a single pipe *signature* (the client contract — inputs, output, semantics). Then refine one signature at a time, one level down, into operators and controllers, leaving the not-yet-built parts as further signatures. Validate **leniently** (`--allow-signatures`) after each layer; the library is always valid and always resumable. Stop when no signatures remain (strict validation passes → runnable), or stop early and keep the leniently-valid scaffold.

## Scope (what this skill can emit)

- Bundle headers: `domain`, `description`, `main_pipe`, `system_prompt`.
- Concepts: simple, refining, structured (field types `text`, `integer`, `boolean`, `number`, `date`, `concept`, `list`).
- Pipes: `PipeSignature` (contract-only header), `PipeLLM`, `PipeCompose`, `PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeFunc`.

**Outside this skill's scope:** `dict` field types, `PipeStructure`, inline `templating_style` blocks, and other advanced features. When the user asks for those, write the closest in-scope equivalent and call out the deviation; do not silently emit unsupported constructs.

---

## How it works — read this first

- **The artifact is a library, not one file.** A directory of same-domain `.mthds` files, loaded together with `-L`. The runtime merges them into one domain; pipes and concepts reference each other across files by bare code.
- **Construction is additive.** A `PipeSignature` is a forward declaration ("header"); the concrete pipe is its "definition". Each refinement **adds a new `<code>.mthds` file**; no existing file is ever rewritten — no merge step. At merge, a concrete satisfies the signature of the same code (the definition wins), so the same code legitimately appears as a header in one file and a concrete in another.
- **Invariant:** every unbuilt pipe is a reachable signature, so the assembled library passes lenient validation (`--allow-signatures`) at every step.
- **Operation (one refinement step):** take one unimplemented signature, **add** its definition file one level down — an operator (done), or a controller that wires sub-pipes, forward-declares each not-yet-built sub-pipe as a new header, and owns any intermediate concepts it introduces — then re-validate.
- **The backlog is the bundle's own todo list.** It is exactly the `## Pending signatures` list that validate reports (declared signatures with no concrete definition yet). Drain it round by round until empty → strict validation passes → runnable.

See [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md) for the `PipeSignature` syntax, the `signature_for` hint, the operator-vs-controller decision, and all pipe-type field rules — it is the syntax source of truth.

---

## Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
# Wrapped in `bash -c` so the bash array syntax below works even when the
# session shell is zsh.
bash -c '
# Pick the cached env-check from the plugin version with the highest semver.
# Matches both `mthds` (prod) and `mthds-dev` (dev) plugin caches. The padded
# segment trick keeps lex order = semver order so 0.10 does not sort below 0.9.
_best_f=""; _best_k=""
for f in "$HOME/.claude/plugins/cache/"*/mthds*/*/bin/mthds-env-check; do
  [ -x "$f" ] || continue
  _v="${f%/bin/*}"; _v="${_v##*/}"
  _k=""; IFS=. read -ra _parts <<<"${_v%%[-+]*}"
  for _p in "${_parts[@]}"; do _p=${_p%%[!0-9]*}; _k="${_k}$(printf %06d "${_p:-0}")"; done
  [[ "$_k" > "$_best_k" ]] && { _best_f="$f"; _best_k="$_k"; }
done
[ -n "$_best_f" ] && exec "$_best_f" "0.10.0"
echo "MTHDS_ENV_CHECK_MISSING"
'
```

**Interpret the output:**

- `MTHDS_AGENT_MISSING` → STOP. Do not proceed. Tell the user:

> The `mthds-agent` CLI is required but not installed. Install it with:
>
> ```
> rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_VERSION_UNKNOWN` → STOP. The installed `mthds-agent` returned an unparseable version. Tell the user:

> Could not parse the output of `mthds-agent --version`. Your installation may be corrupt. Reinstall with:
>
> ```
> rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_OUTDATED <installed> <required>` → The installed `mthds-agent` is too old for this plugin. **Do not hard-stop.** Instead, tell the user their mthds-agent (v\<installed>) is older than the required v\<required>, then follow the [upgrade flow](../shared/upgrade-flow.md) to offer upgrading mthds-agent via `rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/`. After the upgrade flow completes (whether the user upgraded or declined), proceed to Step 1. The upgrade flow's "Not now" and "Never ask" options let users continue with current versions.

- `MTHDS_UPDATE_CHECK_FAILED ...` → WARN. The update check command failed. Show the error output to the user. Suggest checking network connectivity and `mthds-agent` installation. Proceed to Step 1 with current versions.

- `UPGRADE_AVAILABLE ...` → Read [upgrade flow](../shared/upgrade-flow.md) and follow the upgrade prompts before continuing to Step 1.

- `JUST_UPGRADED ...` → Announce what was upgraded to the user, then continue to Step 1.

- `UP_TO_DATE ...` → Proceed to Step 1. The line is a terse list of verified installed versions (e.g. `UP_TO_DATE mthds-agent=0.10.0 plxt=0.4.0 plugin=0.12.0`); if you mention the env-check in your preamble acknowledgement, relay the agent and plugin versions you saw. Two "explicit-quiet" variants share the same prefix and are also clean — proceed to Step 1 without warning, and do not relay the quiet state unless the user is troubleshooting:
  - `UP_TO_DATE update-check=disabled` — the user has turned update-check off via config.
  - `UP_TO_DATE update-check=snoozed` — the user has an active snooze on the current version key; an upgrade would otherwise be available, but they explicitly asked for quiet.

- No output → WARN. The env-check produced no output at all, which usually means `mthds-agent` itself is broken or the wrapper script bailed before printing. Tell the user the environment check could not be confirmed, then proceed cautiously to Step 1.

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.



- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


Do not write `.mthds` files until the environment check passes. The CLI is required for validation and formatting — without it the output will be broken and the PostToolUse hook will fail.

> **No backend setup needed**: building and validating never run the method, so no inference backends or API keys are required. Backend configuration is only needed for live execution — use `/mthds-runner-setup` when ready.

---

## Step 1 — Capture the whole job as one signature (Layer 0)

Read [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md) **before writing**.

Determine the three things that *are* the requirement:

- **Input concept(s)** — what the client provides.
- **Output concept** — what the client gets back.
- **Description** — the semantics, in prose precise enough to implement against.

**Specify the boundary concepts fully now.** The top input and output concepts are the client-facing data contract — give them their structure at Layer 0. Intermediate concepts come later, each introduced by the controller that owns it.

**Write the root file** `mthds-wip/<bundle_dir>/bundle.mthds`:

1. `mkdir -p mthds-wip/<bundle_dir>/`.
2. Write `bundle.mthds` with the **Write** tool. It carries the `domain` header, `description`, `main_pipe`, optional `system_prompt`, the fully-specified boundary concepts, and the top pipe as a single `PipeSignature` whose code is the `main_pipe`:

   ```toml
   domain      = "<snake_case_domain>"
   description = "<what the job means>"
   main_pipe   = "<top_pipe_code>"

   # boundary concepts — specified fully (structure if structured)
   # ...

   [pipe.<top_pipe_code>]
   type          = "PipeSignature"
   description   = "<precise semantics of the whole job>"
   inputs        = { <name> = "<InputConcept>" }
   output        = "<OutputConcept>"
   signature_for = "<intended impl type, e.g. PipeSequence>"
   ```

3. The root file is written **once and persists** — refinement never touches it again. The concrete main pipe is added later in its own `<top_pipe_code>.mthds` file (like any other definition; `main_pipe` is a reference, not the implementation).

Validate leniently (the one-signature library passes):

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --allow-signatures --graph
```

**Announce the captured contract in one line** (inputs → output, one-sentence semantics) before recursing, so the user can interject — non-blocking. *This is the only step with optional interactivity* (see Autonomy below).

---

## Step 2 — Refine layer by layer (auto)

Drain the signature backlog breadth-first, **serially** (one signature at a time — no parallel workers in this version). Repeat this loop until the backlog is empty:

1. **Read the backlog.** Validate leniently; validate states runnability in plain English and lists what remains:

   ```bash
   mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --allow-signatures --graph
   ```

   - **Still pending** → the markdown shows a `## Pending signatures (N)` heading, a `⚠️ This method is NOT yet runnable …` line, and one bullet per library-wide pipe still typed `PipeSignature`. That bullet list is the backlog.
   - **Done** → the markdown shows `✅ All pipes are concretely implemented … this method is runnable.` and **no** `## Pending signatures` section. The backlog is empty → go to Step 3.

   (No `--format json` — the agent reads this markdown directly; the verdict line and the backlog are both plain text. Errors on failure stay markdown too.)

2. **Expand each pending signature, one at a time** (see "To expand one signature" below). Each expansion **adds exactly one new `<code>.mthds` file** and never edits an existing one. `--graph` re-renders `dry_run.html` each layer so the structure is visible as it grows.

3. **Re-validate, recompute `pending_signatures`, repeat.** Expanding a controller forward-declares its children, which become newly pending; expanding an operator removes one. Draining the whole current pending set each round walks the tree breadth-first by construction.

### To expand one signature

Given one pending signature `S` (its frozen contract — `inputs`, `output`, `description`, `signature_for`):

1. **Decide operator or controller.** The `signature_for` hint usually pre-answers it. Heuristic when absent or wrong: a single cognitive/IO step → operator; multiple steps, iteration, branching, or parallelism → controller.

2. **Add `<S>.mthds`** to the bundle dir. Every non-root file carries **only** `domain = "<same_domain>"` for membership — omit `description`, `system_prompt`, `main_pipe` (those live in the root).

   - **Operator (leaf):** write the concrete operator (`PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`) and fill its type-specific fields. No new signatures — this branch is done.
   - **Controller (composite):** write the controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire its sub-pipes, **forward-declare each not-yet-trivial sub-pipe as a new `PipeSignature` header** (contract + `signature_for`) in this same file, and declare any intermediate concepts the wiring needs. The new headers join the backlog.

3. **Declare `inputs` and `output` explicitly**, repeating `S`'s contract. Pipes never infer `inputs` from prompt sigils, so a definition that omits them mismatches its header. Spelling is free — the contract reconciles by **concept identity** (bare↔qualified, native equivalents, multiplicity structural), so `output = "Brief"` and `output = "thisdomain.Brief"` match.

4. **Prevent concept collisions (do this before introducing a new intermediate concept).** Check the concept code is not already declared anywhere in the assembled library or pending set; if it is, **derive a unique code** by namespacing from the parent pipe code. Each concept is declared **once**, in the file of the pipe that introduces it. (A duplicate is the loud backstop: validate fails with `Concept '<code>' is declared in two different bundle files … rename one of the concepts`.)

5. **Fix each concept's shape when you introduce it — you cannot add fields later.** A concept is declared **once**, in its introducing file; the additive model never lets a later file add structure (a second declaration is the same hard "declared in two different bundle files" error). So decide the shape from the consumers this controller wires: if any downstream consumer **field-reads** the concept (`$x.field`, or a construct `from = "x.field"`), declare it **structured now** — a field-read on a simple concept fails even under lenient validation. If the concept is only ever consumed **whole** (`@x` in a prompt, or mapped wholesale), keep it **simple** (often `refines` a native). When a sibling field-reads a concept, hoist that concept up to the common parent controller that wires both its producer and that consumer, and structure it there.

### If validation fails after an expansion

The failure is, by construction, in the file you just added — bounding the fix.

- **Contract mismatch** (the definition's `inputs`/`output` diverges from its header): conform the **definition** to the frozen header. **Never edit the header** — the parent depends on that contract. (Changing a contract is a propagating change that means revising the parent too; if the header itself is genuinely wrong, stop and flag it rather than silently editing it.)
- **Other semantic errors:** map the error to the relevant cheat-sheet section, fix the added file with the **Edit** tool, re-validate. See [Error Handling](../shared/error-handling.md).

---

## Step 3 — Finalize (strict validation)

Once validate reports the `✅ … this method is runnable` verdict (no signatures remain), validate **strictly** (drop `--allow-signatures`):

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph
```

Strict validation rejects any reachable signature, so passing it is the gate that says *runnable* (it reprints the same ✅ verdict). Fix any remaining whole-bundle semantic errors and re-run until it passes.

---

## Step 4 — Deliver

Once strict validation passes:

1. **Input schema** — Run `mthds-agent inputs bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/` and show the user the input JSON schema so they can see what the method expects. **Do NOT save it to `inputs.json`** — input preparation is handled exclusively by `/mthds-inputs`.

2. **Flowchart** — Mention that `dry_run.html` was generated next to the bundle (refreshed at every layer).

3. **Next steps** — Suggest:
   > Test with mock inference (no real inputs needed):
   > ```
   > mthds-agent run bundle mthds-wip/<bundle_dir>/ --dry-run --mock-inputs
   > ```
   > Prepare real inputs with `/mthds-inputs`, then run:
   > ```
   > mthds-agent run bundle mthds-wip/<bundle_dir>/
   > ```

**Early-stop variant.** If the user stops before the backlog is empty, deliver the leniently-valid scaffold instead: confirm it passes lenient validation, list the unimplemented signatures (validate's current `## Pending signatures` list), and explain that resuming means expanding them — no external state is needed, the bundle is its own todo list. A validated design skeleton is a legitimate deliverable.

> **NEVER write `inputs.json` manually.** If the user provides files, paths, or wants to run with real data, invoke `/mthds-inputs` — it handles path resolution (paths must be relative to `inputs.json`, not CWD), placeholder formatting, and file copying.

---

## Invariants & rules (keep these true at every step)

- **Contract stability.** A definition preserves its header's `inputs`/`output` contract, matched by **concept identity** (not byte-string). Choose a signature's internals freely; never change its surface without revising the parent too.
- **`main_pipe` is the anchor.** The top signature's code and its inputs/output are frozen after Layer 0. Its body arrives as a separate definition file; its identity and surface never change.
- **Additive writes.** One concrete definition per file; headers persist after they're satisfied. Never overwrite an existing file — always add a new `<code>.mthds`.
- **A concept's shape is fixed at introduction.** Boundary concepts structured at Layer 0; an intermediate concept's shape is decided in its introducing file — structured if any consumer field-reads it, simple if consumed whole — and cannot be changed in a later file.
- **Backlog = `{signatures} − {concretes}`.** Recomputed each layer from validate's `## Pending signatures` list — never hand-tracked, never reconstructed as a depth tree.

---

## Autonomy

This skill is **automatic by default**.

- **Requirements (Step 1)** — infer the contract and proceed; always *announce* it (non-blocking). Engage in discussion *only* when the request is genuinely ambiguous about inputs/output/semantics, or when the user signals they want to discuss.
- **Recursion (Step 2+)** — always auto. No per-layer approval prompts. The leniently-valid checkpoints and `dry_run.html` are the review surface; the user can interrupt at any time.
- Pause and ask only if validation fails twice on the same construct, or a header itself appears wrong (a propagating contract change).

---

## Reference

- [Vibe Cheat Sheet](references/vibe-cheat-sheet.md) — **read before writing**. The MTHDS code subset this skill writes, including the `PipeSignature` header and lenient-vs-strict validation.
- [Native Content Types](../shared/native-content-types.md) — attributes of native concepts (`Image.url`, `Page.text_and_images`, ...) for `$var.field` references and construct `from` paths.
- [Error Handling](../shared/error-handling.md) — read when validate returns errors to determine recovery.
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — full CLI command syntax, including `--allow-signatures` and reading `pending_signatures`.
