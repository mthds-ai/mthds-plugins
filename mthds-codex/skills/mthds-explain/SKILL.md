---
name: mthds-explain
description: Explain and document MTHDS bundles. Use when user says "what does this pipeline do?", "explain this workflow", "explain this method", "walk me through this .mthds file", "describe the flow", "document this pipeline", "how does this work?", or wants to understand an existing MTHDS method bundle.
min_mthds_version: 0.9.0

---

# Explain MTHDS bundles

Analyze and explain existing MTHDS method bundles in plain language.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

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


Do not write `.mthds` files manually, do not do any other work. The CLI is required for validation, formatting, and execution — without it the output will be broken.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-runner-setup` when you're ready.

### Step 1: Read the .mthds File

Read the entire bundle file to understand its structure.

### Step 2: Identify Components

List all components found in the bundle:
- **Domain**: the top-level `domain` key (bundle header, not a `[domain]` section)
- **Concepts**: all `[concept.*]` blocks — note which are custom vs references to native concepts
- **Pipes**: all `[pipe.*]` blocks — identify the main pipe and sub-pipes
- **Main pipe**: the top-level `main_pipe` key (bundle header, not a `[bundle]` section)

### Step 3: Trace Execution Flow

Starting from the main pipe, trace the execution path:
1. For **PipeSequence**: follow the `steps` array in order
2. For **PipeBatch**: identify `batch_over` and `batch_as`, then the inner pipe
3. For **PipeParallel**: list all branches
4. For **PipeCondition**: map condition → pipe for each branch
5. For **PipeLLM / PipeExtract / PipeImgGen / PipeSearch / PipeFunc**: these are leaf operations

### Step 4: Present Explanation

Structure the explanation as:

1. **Purpose**: one-sentence summary of what the method does
2. **Inputs**: list each input with its concept type and expected content
3. **Output**: the final output concept and what it contains
4. **Step-by-step flow**: walk through execution in order, explaining what each pipe does
5. **Key concepts**: explain any custom concepts defined in the bundle

### Step 5: Generate Flow Diagram

Create a text diagram showing the execution flow. Example:

```
main_sequence
  1. step_one (PipeLLM) -> intermediate_result
  2. step_two (PipeExtract) -> final_output

Inputs: input_a, input_b
Output: final_output
```

Adapt the format to the method structure (linear, branching, batched).

### Step 6: Optional — Validate

If the user wants to confirm the method is valid:
```bash
mthds-agent validate bundle <file>.mthds -L <bundle-dir>/
```

### Step 7: Optional — Visual Graph

For an interactive flowchart without running the method, use validate with `--graph`:
```bash
mthds-agent validate bundle <file>.mthds -L <bundle-dir>/ --graph
```

This generates `dry_run.html` next to the bundle — a static flowchart of the method structure.

For a live execution graph showing actual runtime data, use `/mthds-run`:
```bash
mthds-agent run bundle <bundle-dir>/
```

This produces `live_run.html` alongside the execution results.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read when explaining what data flows through pipes (e.g., what attributes Page or Image content carries)
