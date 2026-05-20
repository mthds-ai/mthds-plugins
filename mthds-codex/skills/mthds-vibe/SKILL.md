---
name: mthds-vibe
description: Vibe-code a method bundle by writing MTHDS code directly in a single pass.
min_mthds_version: 0.7.0

---

# Vibe-write a MTHDS bundle

Write MTHDS code (a TOML-based declarative language) for a complete `bundle.mthds` in a single pass. The PostToolUse hook and an explicit `validate bundle` step catch errors after the write.

## Scope (what this skill can emit)

This skill covers:

- Bundle headers: `domain`, `description`, `main_pipe`, `system_prompt`.
- Concepts: simple, refining, structured (with field types `text`, `integer`, `boolean`, `number`, `date`, `concept`, `list`).
- Pipes: `PipeLLM`, `PipeCompose`, `PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeFunc`.

**Outside this skill's scope:** `dict` field types, `PipeStructure`, inline `templating_style` blocks, and other advanced features. When the user asks for those, write the closest in-scope equivalent and call out the deviation; do not silently emit unsupported constructs.

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
[ -n "$_best_f" ] && exec "$_best_f" "0.7.0" --codex
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

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.

- `CODEX_CONFIG_NEEDS_SETUP` → Codex's `~/.codex/` is not set up for the mthds plugin, so the bundled `.mthds` validation hook will not load. The env-check may print a `#`-prefixed diagnostic line after the status — relay it if present. Resolve this before Step 1:

  1. **Preview** — run `mthds-agent codex apply-config --dry-run` and show the user the output. `WOULD_APPLY` lists the keys it will add under `applied`; `ALREADY_OK` means no keys need adding. Either way, relay any `warnings` entries — those (e.g. read-only sandbox, hooks disabled) need a hand-fix `apply-config` will not perform. If `ALREADY_OK` with no warnings, treat as resolved and go to Step 1.
  2. **Ask** — use AskUserQuestion: "Apply Codex config now?" with options "Apply now" / "Skip".
  3. **Apply now** — run `mthds-agent codex apply-config`:
     - `APPLIED` / `ALREADY_OK` → tell the user the config is fixed and they must **restart Codex** for the validation hook to load (it will not load in this session). Relay any `warnings` — those still need a hand-fix.
     - Error about conflicting keys → show it verbatim; the user must hand-edit `~/.codex/config.toml`, then re-run `mthds-agent codex apply-config`.
     - Error from the sandbox blocking the write to `~/.codex/config.toml` → ask the user to run `mthds-agent codex apply-config` themselves in a terminal, then restart Codex.
  4. **Skip** — tell the user the validation hook stays off until they run `mthds-agent codex apply-config` and restart Codex.

  Then proceed to Step 1. This session has no PostToolUse hook. The mthds skills still run `mthds-agent validate bundle` explicitly, so `.mthds` files built or edited through a skill are still semantically validated — but the write-time `plxt lint`/`fmt` pass depends on the hook and will not run until Codex is restarted.

- No output or `UP_TO_DATE` → Proceed to Step 1.

- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


Do not write `.mthds` files until the environment check passes. The CLI is required for validation and formatting — without it the output will be broken and the PostToolUse hook will fail.

> **No backend setup needed**: This skill works without inference backends or API keys. Building and validating a `.mthds` file does not require running it. Backend configuration is only needed for live execution — use `/mthds-runner-setup` when ready.

---

## Step 1 — Gather the Essentials

Read [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md) **before writing**. It is the single source of truth for syntax, field rules, and supported pipe types.

Confirm in one short exchange (or infer from context):

- **Inputs** — what does the user have? (documents, images, text, structured data)
- **Output** — what should the bundle produce?
- **Transformations** — extraction, LLM analysis, batching, branching?
- **Domain** — a `snake_case` namespace for the bundle.

If the user has already described the method clearly enough, skip the questions and proceed.

## Step 2 — Sketch the Shape (in-context, no files)

Briefly enumerate, in chat (not on disk):

- The concepts you'll define (PascalCase names + one-line description; mark which refine native concepts vs. which have structure).
- The pipes you'll define (snake_case names, `type`, inputs → output signatures), with the main pipe first.

If the user has not weighed in, present this sketch in 5–15 lines and proceed to Step 3 immediately. Don't ask for confirmation unless the request was ambiguous — vibe mode trusts the model's first read.

## Step 3 — Write the Bundle in One Pass

**Save location:** Always write to `mthds-wip/<bundle_dir>/bundle.mthds`. Do not ask for a location.

1. Create the directory: `mkdir -p mthds-wip/<bundle_dir>/`.
2. Compose the full `bundle.mthds` content following [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md). Required structure:

   ```toml
   domain      = "<snake_case_domain>"
   description = "<bundle description>"
   main_pipe   = "<main_pipe_code>"

   # concepts (simple in [concept], structured/refining in [concept.<Code>])
   # ...

   # pipes (main pipe first, then sub-pipes in execution order)
   # ...
   ```

3. Write the file with the **Write** tool to `mthds-wip/<bundle_dir>/bundle.mthds`. The PostToolUse hook runs `plxt lint`, `plxt fmt`, and `mthds-agent validate bundle` automatically on save.

**Authoring rules** (lifted from the cheat sheet — verify against it if uncertain):

- Domain is `snake_case`, may have dots. Reserved first segments: `native`, `mthds`, `pipelex`.
- Concept codes are `PascalCase`, singular, no adjectives. Pipe codes are `snake_case`.
- Inputs are `snake_case` keys with `PascalCase` concept values; multiplicity via `[]` or `[N]`.
- `refines` and `structure` are mutually exclusive on a concept.
- Every pipe needs `type`, `description`, `output`. `inputs` is optional in the schema but almost always present.
- Every prompt variable MUST be a declared input, AND every declared input MUST be referenced by a prompt variable.
- `PipeCondition` needs `default_outcome` even when outcomes look exhaustive.
- `PipeImgGen` and `PipeSearch` need `prompt` (even a passthrough like `"$img_prompt"`).
- `PipeBatch`: `input_item_name` must differ from `input_list_name` and from every other key in `inputs`.
- `PipeParallel`: at least one of `add_each_output = true` or `combined_output` must be set.
- Pipe references in `steps`, `branches`, `outcomes`, `branch_pipe_code` use bare pipe codes (no domain prefix) when staying in-domain.
- Keep `inputs = { ... }` on a single line.

When in doubt about field names or shapes, **stop and re-read the cheat sheet section for that pipe type** rather than guessing.

## Step 4 — Validate Explicitly

The PostToolUse hook validates on save, but run validation explicitly to surface errors deterministically (and to handle environments where the hook is disabled or limited):

```bash
mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph
```

The `-L` flag isolates the bundle from other `.mthds` files in the project, preventing namespace collisions. `--graph` produces `dry_run.html` next to the bundle on success.

## Step 5 — Iterate on Errors

If validation fails:

1. Read the error output. Each error has an `error_type` and (usually) a `pipe_code` or `concept_code`.
2. Map the error to the relevant section of [vibe-cheat-sheet.md](references/vibe-cheat-sheet.md) and fix the file with the **Edit** tool.
3. Re-run the validate command from Step 4.
4. Repeat until validation passes.

See [Error Handling](../shared/error-handling.md) for error type recovery patterns.

## Step 6 — Deliver

Once validation passes:

1. **Input schema** — Run `mthds-agent inputs bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/` and show the user the input JSON schema so they can see what the method expects. **Do NOT save it to `inputs.json`** — input preparation is handled exclusively by `/mthds-inputs`.

2. **Flowchart** — Mention that `dry_run.html` was generated next to the bundle.

3. **Next steps** — Suggest:
   > Test with mock inference (no real inputs needed):
   > ```
   > mthds-agent run bundle mthds-wip/<bundle_dir>/ --dry-run --mock-inputs
   > ```
   > Prepare real inputs with `/mthds-inputs`, then run:
   > ```
   > mthds-agent run bundle mthds-wip/<bundle_dir>/
   > ```

> **NEVER write `inputs.json` manually.** If the user provides files, paths, or wants to run with real data, invoke `/mthds-inputs` — it handles path resolution (paths must be relative to `inputs.json`, not CWD), placeholder formatting, and file copying.

---

## Quick Mode Heuristic

This skill is automatic by default. Only switch to interactive if:

- The user explicitly asks for guidance ("walk me through").
- The request is genuinely ambiguous about inputs/outputs/transformations after one re-read.
- Validation has failed twice on the same construct — pause and ask the user to confirm intent before a third attempt.

Otherwise: read the cheat sheet, sketch briefly, write the file, validate, deliver.

---

## Reference

- [Vibe Cheat Sheet](references/vibe-cheat-sheet.md) — **read this before writing**. The MTHDS code subset this skill writes, with examples for every supported pipe type.
- [Native Content Types](../shared/native-content-types.md) — attributes of native concepts (`Image.url`, `Page.text_and_images`, ...) for `$var.field` references and construct `from` paths.
- [Error Handling](../shared/error-handling.md) — read when validate returns errors to determine recovery.
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — full CLI command syntax if needed beyond `validate bundle` and `inputs bundle`.
