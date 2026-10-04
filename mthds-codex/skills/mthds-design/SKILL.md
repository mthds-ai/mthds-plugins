---
name: mthds-design
description: Design a new MTHDS method bundle (.mthds files) top-down, contract-first. Use when the user says "design a method", "build a method", "create a pipeline", "build a workflow", "new .mthds file", "make a method", "write a method that does X", "turn this workflow into MTHDS", or wants any new method from scratch. Construction adapts to complexity — a shallow, fully understood graph is written directly as one runnable bundle, and deep, uncertain or staged work goes stepwise, one validated signature at a time.
min_mthds_version: 0.30.0

---

# Design a MTHDS bundle top-down at the right depth

Design a new `.mthds` method **contract-first**, directly or stepwise (step 3). A change to an existing method is `/mthds-edit`'s.

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
[ -n "$_best_f" ] && exec "$_best_f" "0.30.0" --codex
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

- `UP_TO_DATE ...` → Proceed to Step 1. The line is a terse list of verified installed versions (e.g. `UP_TO_DATE mthds-agent=0.10.0 plxt=0.4.0 plugin=0.12.0`); if you mention the env-check in your preamble acknowledgement, relay the agent and plugin versions you saw. Two "explicit-quiet" variants share the same prefix and are also clean — proceed to Step 1 without warning, and do not relay the quiet state unless the user is troubleshooting:
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


Until the environment check passes, write no `.mthds` file and do no other work: the CLI is required for validation, formatting and execution, and without it the output will be broken.

> **No backend setup needed**: designing and validating never run the method, so no inference backend or API key is required. Backend configuration is only needed to run methods with live inference — use `/mthds-runner-setup` when you're ready.

## Guards

- **Every claimed checkpoint or completion state comes from `mthds-agent validate bundle` over the whole bundle directory**, never from reading the files.
- **Never write `inputs.json`.** When the user provides files or paths, or wants to run with real data, invoke `/mthds-inputs`: it resolves paths relative to `inputs.json` rather than the working directory, formats placeholders and copies files, which a hand-written file gets wrong.
- **This skill never runs a method**: a run needs inputs and spends inference credit.

## Process

### 1. Capture the contract

Read the [MTHDS language reference](../shared/mthds-reference.md) **before writing**: it is the syntax source of truth. For what it places outside the authoring subset (`dict` field types, `PipeStructure` and the like), write the closest in-scope equivalent and call out the deviation.

Fix the **input concept(s)**, the **output concept** and the **description**, precise enough to implement against, and specify every boundary concept fully now. Shape each concept from all its known consumers: it must be structured if any consumer field-reads it (`$x.field`, a construct `from = "x.field"`), and can stay simple otherwise. Declare each concept exactly once, complete, owned by the root boundary or by the controller that introduces it.

**Announce the captured contract in one line** (inputs → output, one-sentence semantics), with the bundle home of step 2 in the same line, before writing, without waiting for a reply. Discuss only genuine ambiguity, or when the user asks to collaborate.

### 2. The bundle home

A path the user named wins. Otherwise the bundle goes in `mthds-wip/<bundle_dir>/`, `<bundle_dir>` being the `domain` with any dot turned into an underscore. That directory is `<bundle_home>` in every command below, and its root file is `bundle.mthds`. Do not ask the user for the location.

### 3. Infer the construction mode

**Never ask the user to choose the workflow.**

- **Direct** when the complete graph can be authored without placeholders or speculative contracts: the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators; no child is a controller unless the whole nested graph and every contract is fixed and a direct layout is still clearly safer; every branch, iteration, mapping and intermediate owner is decided; every concept shape can be fixed from its consumers; every pipe can be concrete in the first coherent artifact. One controller is a strong fast-path signal, not a rule. Pipe count is secondary: cross-branch concept dependencies, uncertain ownership, or unresolved child contracts make even a lone controller stepwise.
- **Stepwise** otherwise, and even where direct holds, for a large graph that benefits from independently valid review checkpoints or on an explicit request for a scaffold, partial design, staged work, or a resumable intermediate result: read [stepwise.md](references/stepwise.md) before writing any file.

When borderline, take the simplest path that can be written **completely** and validated confidently.

### 4. Direct construction

Design the whole graph in memory, then write `bundle.mthds` top-down — metadata, concepts, the concrete main pipe, its leaves — with concept codes checked library-wide and explicit `inputs` and `output` on every pipe. Write it with your agent's file tools, never through the shell, so the plugin's hook checks it. More than one file only at a natural module boundary, never one per pipe, and every file of the bundle declares the same `domain`. Include **no temporary `PipeSignature` declarations**. Leave `model` out unless the user asks for a model, a setting or a kind of behaviour, or the pipe's input is one the default model cannot read, such as a web page for a `PipeExtract`, or the pipe is a `PipeJudge`, which always names one; then look the reference up as the language reference's [model section](../shared/mthds-reference.md#model-references) says. **If the design would need a placeholder or a guessed contract, or writing or validation exposes an unresolved structural boundary**, stop extending the draft and read [stepwise.md](references/stepwise.md) before changing any file.

### 5. Validate

```bash
mthds-agent validate bundle <bundle_home>/bundle.mthds -L <bundle_home>/ --graph
```

`-L` loads every `.mthds` file beneath the bundle directory and keeps the project's other bundles out of its namespace. Read the Markdown verdict it prints. On errors, fix from the error list and its locators, which name the offending file, then validate again; [error handling](../shared/error-handling.md) says how to recover by error domain.

### 6. The runnable gate and delivery

For a completed method, validation **without** `--allow-signatures` must pass and print the `✅ … this method is runnable.` line: this verdict is the runnable gate, so fix and re-validate until it passes. Then:

1. **Project the input schema**: run `mthds-agent inputs bundle <bundle_home>/bundle.mthds -L <bundle_home>/ --explicit` and show the user the inputs the method expects. Do not save it to `inputs.json`: preparing inputs is `/mthds-inputs`'s.
2. **The flowchart**: say that validation wrote an interactive flowchart, `dry_run.html`, next to the bundle.
3. **Next steps**: suggest a dry run with mock inference, which needs no real inputs, then `/mthds-inputs` to prepare real ones and a run:
   ```bash
   mthds-agent run bundle <bundle_home>/ --dry-run --mock-inputs
   mthds-agent run bundle <bundle_home>/
   ```

## Stops

| Condition | Do this |
|---|---|
| an error in the `input` domain | the bundle is wrong: fix it and validate again |
| an error in the `config` or `runtime` domain | report it, and retry once before stopping: the environment is at fault, not the bundle |
| validation fails twice on the same construct, or the contract itself looks wrong | pause and show the user |

## References

- [MTHDS language reference](../shared/mthds-reference.md): before writing any `.mthds` file.
- [stepwise.md](references/stepwise.md): stepwise at step 3 or 4.
- [Native content types](../shared/native-content-types.md): a native's fields, for `$var.field` and `from`.
- [Error handling](../shared/error-handling.md): recovering from a CLI error by its domain.
- [MTHDS agent guide](../shared/mthds-agent-guide.md): CLI syntax and output formats, `--allow-signatures` included.
