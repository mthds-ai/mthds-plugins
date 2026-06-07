---
name: mthds-vibe
description: Build a method bundle top-down by stepwise refinement — capture the whole job as one pipe signature, then refine it layer by layer into a runnable method that is valid at every step.
min_mthds_version: 0.9.0

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
- **The backlog is the bundle's own todo list.** It is exactly `pending_signatures` from validate (declared signatures with no concrete definition yet). Drain it round by round until empty → strict validation passes → runnable.

See [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md) for the `PipeSignature` syntax, the `signature_for` hint, the operator-vs-controller decision, and all pipe-type field rules — it is the syntax source of truth.

---

## Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
# Wrapped in `bash -c` so the bash array syntax below works even when the
# session shell is zsh (Codex runs blocks under the user's shell).
bash -c '
# Pick the cached env-check from the plugin version with the highest semver.
# Pad each numeric segment to fixed width so lex sort matches semver sort
# (avoids the 0.10 < 0.9 lex-order trap). Sort keys are digits-only by
# construction, so the [[ > ]] compare is locale-independent. Bash 3.2 OK.
_best_f=""; _best_k=""
for f in "${CODEX_HOME:-$HOME/.codex}"/plugins/cache/*/mthds/*/bin/mthds-env-check; do
  [ -x "$f" ] || continue
  _v="${f%/bin/*}"; _v="${_v##*/}"
  _k=""; IFS=. read -ra _parts <<<"${_v%%[-+]*}"
  for _p in "${_parts[@]}"; do _p=${_p%%[!0-9]*}; _k="${_k}$(printf %06d "${_p:-0}")"; done
  [[ "$_k" > "$_best_k" ]] && { _best_f="$f"; _best_k="$_k"; }
done
[ -n "$_best_f" ] && exec "$_best_f" "0.9.0" --codex
echo "MTHDS_ENV_CHECK_MISSING"
'
```

**Interpret the output:**

- `MTHDS_AGENT_MISSING` → STOP. Do not proceed. Tell the user:

> The `mthds-agent` CLI is required but not installed. Install it with:
>
> ```
> npm install -g mthds
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_VERSION_UNKNOWN` → STOP. The installed `mthds-agent` returned an unparseable version. Tell the user:

> Could not parse the output of `mthds-agent --version`. Your installation may be corrupt. Reinstall with:
>
> ```
> npm install -g mthds@latest
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_OUTDATED <installed> <required>` → The installed `mthds-agent` is too old for this plugin. **Do not hard-stop.** Instead, tell the user their mthds-agent (v\<installed>) is older than the required v\<required>, then follow the [upgrade flow](../shared/upgrade-flow.md) to offer upgrading mthds-agent via `npm install -g mthds@latest`. After the upgrade flow completes (whether the user upgraded or declined), proceed to Step 1. The upgrade flow's "Not now" and "Never ask" options let users continue with current versions.

- `MTHDS_UPDATE_CHECK_FAILED ...` → WARN. The update check command failed. Show the error output to the user. Suggest checking network connectivity and `mthds-agent` installation. Proceed to Step 1 with current versions.

- `UPGRADE_AVAILABLE ...` → Read [upgrade flow](../shared/upgrade-flow.md) and follow the upgrade prompts before continuing to Step 1.

- `JUST_UPGRADED ...` → Announce what was upgraded to the user, then continue to Step 1.

- `UP_TO_DATE ...` → Proceed to Step 1. The line is a terse list of verified installed versions (e.g. `UP_TO_DATE mthds-agent=0.9.0 plxt=0.4.0 plugin=0.12.0`); if you mention the env-check in your preamble acknowledgement, relay the agent and plugin versions you saw. Two "explicit-quiet" variants share the same prefix and are also clean — proceed to Step 1 without warning, and do not relay the quiet state unless the user is troubleshooting:
  - `UP_TO_DATE update-check=disabled` — the user has turned update-check off via config.
  - `UP_TO_DATE update-check=snoozed` — the user has an active snooze on the current version key; an upgrade would otherwise be available, but they explicitly asked for quiet.

- No output → WARN. The env-check produced no output at all, which usually means `mthds-agent` itself is broken or the wrapper script bailed before printing. Tell the user the environment check could not be confirmed, then proceed cautiously to Step 1.

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.

- `CODEX_CONFIG_NEEDS_SETUP` → Codex's `~/.codex/` is not set up for the mthds plugin, so the bundled `.mthds` validation hook will not load. When this fires it is the **only** terminal status the env-check emits — `update-check` is skipped entirely (not run, not suppressed) because fixing the hook is the prerequisite and `update-check`'s upgrade marker is one-shot; the user re-runs and gets fresh update info next time. The env-check may print one or more `#`-prefixed diagnostic lines after the status — relay them if present. Resolve this before Step 1:

  1. **Preview** — run `mthds-agent codex apply-config --dry-run` and show the user the output. `WOULD_APPLY` lists the keys it will add under `applied`; `ALREADY_OK` means no keys need adding. Either way, relay any `warnings` entries — those (e.g. read-only sandbox, hooks disabled) need a hand-fix `apply-config` will not perform. If `ALREADY_OK` with no warnings, treat as resolved and go to Step 1.
  2. **Ask** — use AskUserQuestion: "Apply Codex config now?" with options "Apply now" / "Skip".
  3. **Apply now** — run `mthds-agent codex apply-config`:
     - `APPLIED` / `ALREADY_OK` → tell the user the config is fixed and they must **restart Codex** for the validation hook to load (it will not load in this session). Relay any `warnings` — those still need a hand-fix.
     - Error about conflicting keys → show it verbatim; the user must hand-edit `~/.codex/config.toml`, then re-run `mthds-agent codex apply-config`.
     - Error from the sandbox blocking the write to `~/.codex/config.toml` → ask the user to run `mthds-agent codex apply-config` themselves in a terminal, then restart Codex.
  4. **Skip** — tell the user the validation hook stays off until they run `mthds-agent codex apply-config` and restart Codex.

  Then proceed to Step 1. This session has no PostToolUse hook. The mthds skills still run `mthds-agent validate bundle` explicitly, so `.mthds` files built or edited through a skill are still semantically validated — but the write-time `plxt lint`/`fmt` pass depends on the hook and will not run until Codex is restarted.

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

**Specify the boundary concepts fully now.** The top input and output concepts are the client-facing data contract — give them their structure at Layer 0. Intermediate concepts come later, lazily.

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

1. **Read the backlog.** Validate leniently and read `pending_signatures` from the JSON envelope on stdout:

   ```bash
   mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --allow-signatures --graph --format json
   ```

   `pending_signatures` is the library-wide list of pipes still typed `PipeSignature`. Empty → go to Step 3.

2. **Expand each pending signature, one at a time** (see "To expand one signature" below). Each expansion **adds exactly one new `<code>.mthds` file** and never edits an existing one. `--graph` re-renders `dry_run.html` each layer so the structure is visible as it grows.

3. **Re-validate, recompute `pending_signatures`, repeat.** Expanding a controller forward-declares its children, which become newly pending; expanding an operator removes one. Draining the whole current pending set each round walks the tree breadth-first by construction.

### To expand one signature

Given one pending signature `S` (its frozen contract — `inputs`, `output`, `description`, `signature_for`):

1. **Decide operator or controller.** The `signature_for` hint usually pre-answers it. Heuristic when absent or wrong: a single cognitive/IO step → operator; multiple steps, iteration, branching, or parallelism → controller.

2. **Add `<S>.mthds`** to the bundle dir. Every non-root file carries **only** `domain = "<same_domain>"` for membership — omit `description`, `system_prompt`, `main_pipe` (those live in the root).

   - **Operator (leaf):** write the concrete operator (`PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`) and fill its type-specific fields. No new signatures — this branch is done.
   - **Controller (composite):** write the controller (`PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`), wire its sub-pipes, **forward-declare each not-yet-trivial sub-pipe as a new `PipeSignature` header** (contract + `signature_for`) in this same file, and declare any intermediate concepts the wiring needs. The new headers join the backlog.

3. **Declare `inputs` and `output` explicitly**, repeating `S`'s contract. Pipes never infer `inputs` from prompt sigils, so a definition that omits them mismatches its header. Spelling is free — the contract reconciles by **concept identity** (bare↔qualified, native equivalents, multiplicity structural), so `output = "Brief"` and `output = "thisdomain.Brief"` match.

4. **Prevent concept collisions (do this before introducing a new intermediate concept).** Check the concept code is not already declared anywhere in the assembled library or pending set; if it is, **derive a unique code** by namespacing from the parent pipe code. Each concept is declared **once**, in the file of the pipe that introduces it. (`ConceptLibraryError` is the loud backstop if a duplicate slips through.)

5. **Refine concepts lazily.** Introduce an intermediate concept simple (often `refines` a native). Give it `structure` only when a downstream consumer reads a specific field (e.g. a prompt uses `$x.field`, or a construct maps `from = "x.field"`) — structure it at that moment, not before.

### If validation fails after an expansion

The failure is, by construction, in the file you just added — bounding the fix.

- **Contract mismatch** (the definition's `inputs`/`output` diverges from its header): conform the **definition** to the frozen header. **Never edit the header** — the parent depends on that contract. (Changing a contract is a propagating change that means revising the parent too; if the header itself is genuinely wrong, stop and flag it rather than silently editing it.)
- **Other semantic errors:** map the error to the relevant cheat-sheet section, fix the added file with the **Edit** tool, re-validate. See [Error Handling](../shared/error-handling.md).

---

## Step 3 — Finalize (strict validation)

When `pending_signatures` is empty, validate **strictly** (drop `--allow-signatures`):

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph
```

Strict validation rejects any reachable signature, so passing it is the gate that says *runnable*. Fix any remaining whole-bundle semantic errors and re-run until it passes.

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

**Early-stop variant.** If the user stops before the backlog is empty, deliver the leniently-valid scaffold instead: confirm it passes lenient validation, list the unimplemented signatures (the current `pending_signatures`), and explain that resuming means expanding them — no external state is needed, the bundle is its own todo list. A validated design skeleton is a legitimate deliverable.

> **NEVER write `inputs.json` manually.** If the user provides files, paths, or wants to run with real data, invoke `/mthds-inputs` — it handles path resolution (paths must be relative to `inputs.json`, not CWD), placeholder formatting, and file copying.

---

## Invariants & rules (keep these true at every step)

- **Contract stability.** A definition preserves its header's `inputs`/`output` contract, matched by **concept identity** (not byte-string). Choose a signature's internals freely; never change its surface without revising the parent too.
- **`main_pipe` is the anchor.** The top signature's code and its inputs/output are frozen after Layer 0. Its body arrives as a separate definition file; its identity and surface never change.
- **Additive writes.** One concrete definition per file; headers persist after they're satisfied. Never overwrite an existing file — always add a new `<code>.mthds`.
- **Concepts refine lazily.** Boundary concepts at Layer 0; intermediate concepts introduced simple, structured only when a consumer reads a field.
- **Backlog = `{signatures} − {concretes}`.** Recomputed each layer from `pending_signatures` — never hand-tracked, never reconstructed as a depth tree.

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
