# Codex vs Claude Code Hooks

Both plugins validate `.mthds` files automatically after edits. The validation pipeline is the same shape (plxt lint, plxt fmt, mthds-agent validate), the hook event is the same (`PostToolUse` with a tool-name matcher), and — now that Codex supports plugin-bundled hooks — both hooks ship inside the plugin itself. The remaining differences come from Codex's freeform file-write tool and its sandbox.

## Claude Code hook

- **Event:** `PostToolUse` with matcher `Write|Edit`
- **Trigger:** fires immediately after every file write or edit
- **File discovery:** receives the exact file path from `tool_input.file_path` in stdin JSON
- **Scope:** validates one file per invocation
- **Sandbox:** hooks run without network restrictions
- **Stages:** plxt lint, plxt fmt, mthds-agent validate bundle (all three). Stage 3 is **lenient** (`--allow-signatures`) and emits a non-blocking `pending_signatures` nudge on success — see [Lenient validation](#lenient-validation--allow-signatures-both-hooks)
- **Implementation:** bash script `templates/hooks/validate-mthds.sh.j2` (rendered into `mthds/hooks/`)
- **Wiring:** `hooks.json` is bundled inside the plugin and auto-loaded by Claude Code

## Codex hook

- **Event:** `PostToolUse` with matcher `^apply_patch$`
- **Trigger:** fires once per `apply_patch` call (one fire per multi-file patch, with all touched files in a single payload)
- **File discovery:** parses `tool_input.command` (the raw apply_patch envelope) for `*** Update File:` / `*** Add File:` / `*** Move to:` headers
- **Scope:** validates every `.mthds` file that exists on disk after the patch applies (rename source paths and `*** Delete File:` targets are silently skipped)
- **Sandbox:** hooks run inside the Codex sandbox with restricted network access
- **Stages:** plxt lint, plxt fmt, `pipelex-agent validate bundle` (all three). Stage 3 calls `pipelex-agent` directly (not `mthds-agent`); it is **lenient** (`--allow-signatures`) and blocks on input-domain errors and emits `additionalContext` on config/runtime errors. Unlike the Claude hook it does **not** emit the `pending_signatures` nudge — see [Lenient validation](#lenient-validation--allow-signatures-both-hooks)
- **Implementation:** `mthds-agent codex hook` — a TypeScript subcommand of mthds-js. The validation runtime lives in the npm package, not the plugin.
- **Wiring:** the plugin bundles `hooks/codex-hooks.json` and points the Codex plugin manifest's `hooks` field at it. Codex discovers it directly — no per-user install step. Loading it requires `[features] plugin_hooks = true` (see below).

## Why the differences

### `apply_patch` envelope vs `tool_input.file_path`

`apply_patch` is Codex's freeform file-write tool: the model emits a heredoc-shaped patch envelope (`*** Begin Patch / *** Update File: <path> / @@ ... / *** End Patch`) instead of distinct write/edit calls. The PostToolUse payload exposes that envelope verbatim as `tool_input.command`. The hook parses the envelope's `*** Update File: / *** Add File: / *** Move to:` headers to discover every touched file. There is no equivalent of Claude Code's `tool_input.file_path` because a single `apply_patch` call can touch any number of files.

### Validation runtime lives in mthds-agent, not the plugin

The bundled `codex-hooks.json` is tiny — a `PostToolUse(apply_patch)` entry whose command is the literal string `mthds-agent codex hook`. The actual validation logic is that subcommand, shipped in the mthds-js npm package. Keeping it there gives a single source of truth across platforms (the Claude bash hook and the Codex subcommand run the same validation stages) and lets the validation logic be versioned with mthds-agent rather than the plugin. `mthds-agent` is already on PATH after `npm install -g mthds`, which every other skill in the plugin needs anyway.

### Plugin-bundled hooks are opt-in

Codex loads a plugin's bundled hooks only when `[features] plugin_hooks = true`. The flag is off by default, so `mthds-agent codex apply-config` sets it (along with the sandbox network key). Until the flag is on, the bundled hook simply does not load — the plugin's skill preamble runs `apply-config --check` and, when setup is incomplete, offers to run `apply-config` for the user (preview via `--dry-run`, confirm, apply). Plugin-bundled hook discovery requires Codex 0.130+.

### Stage 3 validation in the Codex sandbox (now enabled)

Earlier, `mthds-agent validate bundle` fetched a remote Pipelex configuration on startup; the Codex sandbox blocked that network call and the command hung, so Stage 3 was disabled there. That is resolved. The Codex hook now runs Stage 3 by calling `pipelex-agent validate bundle <file> -L <dir> --allow-signatures --format json --error-format json` directly, and pipelex's `validate bundle` path is **offline-safe** — no gateway or remote-config fetch — so it runs cleanly inside the sandbox. It classifies on the **structured JSON** error envelope on stderr (`error_domain` / `message` / `validation_errors`): block on input-domain (or missing/unknown — default to block for safety), emit `additionalContext` on config/runtime. Both hooks now run all three stages.

### Lenient validation — `--allow-signatures` (both hooks)

Both hooks run Stage 3 **leniently**, passing `--allow-signatures` to `validate bundle`. A `PipeSignature` is a contract-only forward declaration; recursive/stepwise building (the `mthds-recursive` skill) saves bundles whose graph still reaches unimplemented signatures, and a strict validate would block every one of those intermediate saves. Lenient validation accepts a reachable signature (each mints a mock of its declared output), so in-progress builds aren't blocked. On a **signature-free** bundle lenient ≡ strict, so this is a no-op for `mthds-build`, hand-edits, and finished methods. The strict gate (which rejects any reachable signature) moves to the skill's explicit finalize step and to `run` — both of which always reject signatures, so an unfinished method can never be run.

Both hooks pin `--allow-signatures --format json --error-format json` (the two streams are independent — `--format` governs the success envelope on stdout, `--error-format` the error report on stderr, and `--error-format` *inherits* `--format` when omitted, so pinning both keeps each stream machine-readable). Both classify on the **structured JSON verdict** — `is_valid` from the stdout success envelope, `error_domain` / `message` / `validation_errors` from the stderr error envelope — not a markdown grep. The two hooks diverge only on the **success nudge**:

- **Claude hook** reads the `pending_signatures` array from the stdout success envelope and, if non-empty, emits a **non-blocking** `additionalContext` nudge listing the still-unimplemented signatures.
- **Codex hook** does not emit the nudge for v1 — the orchestrator skill tracks `pending_signatures` itself, so the Codex nudge is a deferred follow-up (see `wip/deferred-issues.md`), not a correctness gap.

(Canonical reference for the two-stream `--format` / `--error-format` design: `mthds-plugins/CLAUDE.md` §"`--format` vs `--error-format`" and `pipelex/cli/agent_cli/CLAUDE.md` §"Output format".)

### Sandbox network access

By default, Codex's `workspace-write` sandbox blocks outbound network for hook commands. `mthds-agent codex apply-config` merges `[sandbox_workspace_write] network_access = true` into `~/.codex/config.toml` so future runtime calls that talk to the network (telemetry, package resolution, remote pipelex config) don't fail silently inside the sandbox. The merge is additive — it never removes or rewrites unrelated keys, and re-running it is a no-op. Use `--dry-run` to preview, `--check` for env-check / CI gating.

`apply-config` also warns (without modifying anything) when:

- `[features] hooks = false` (or its alias `codex_hooks = false`) is explicitly set. That flag defaults to enabled; an explicit `false` disables all hooks and breaks the plugin.
- `sandbox_mode = "read-only"`, which prevents `apply_patch` from running at all.

A required key explicitly set to a conflicting value (e.g. `plugin_hooks = false`) is reported as a clear error rather than silently overridden — `apply-config` never flips an explicit user choice. `mthds-agent doctor` runs the same inspection in read-only mode and surfaces the same findings, plus any obsolete `~/.codex/hooks.json` entry.

### plxt lazy HTTP fix

`plxt` had an eager `reqwest` client initialization that crashed in the Codex sandbox; it was made lazy in `vscode-pipelex` PR #38 (only created when lint encounters http/https schema sources).

## Migration from `install-hook`

Before Codex supported plugin-bundled hooks, the plugin had no way to ship the hook: Codex did not read a `hooks` field from plugin manifests, so the hook config had to live at `~/.codex/hooks.json`, written at install time by `mthds-agent codex install-hook`. That command is retired. `apply-config` removes any `PostToolUse(apply_patch)` or legacy `Stop` entry that `install-hook` (or the even older `install-codex.sh`) left behind, so the bundled hook does not fire twice.

## Install flows

Claude Code:

```bash
npm install -g mthds
mthds-agent bootstrap
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Codex 0.130.0+:

```bash
npm install -g mthds
mthds-agent bootstrap
mthds-agent codex apply-config
codex plugin marketplace add mthds-ai/mthds-plugins
# then /plugins inside Codex to install — there's no one-shot CLI install yet
```

The Codex flow has one extra step (`apply-config`) over Claude Code, plus the final manual `/plugins` install. `apply-config` sets the `plugin_hooks` feature flag and the sandbox network key and cleans up legacy hook entries; its `plugin_hooks` half becomes unnecessary once Codex enables plugin hooks by default.

## env-check resolution

The Codex skill preamble runs `mthds-env-check` to verify `mthds-agent` is installed and at the required version, and that `~/.codex/` is set up for the plugin (it shells out to `apply-config --check`). When the check reports `CODEX_CONFIG_NEEDS_SETUP`, the preamble drives an offer-then-run flow: it previews the fix with `apply-config --dry-run`, asks the user, runs `apply-config`, and falls back to handing over the command if the sandbox blocks the write. The bundled hook still loads only on the next Codex restart, so the preamble is explicit that the current session relies on the skills' own explicit `plxt lint` + `validate bundle` steps. The env-check binary lives at `bin/mthds-env-check` inside the plugin. After `codex plugin marketplace add` + `/plugins install`, Codex stages a per-version copy under `$CODEX_HOME/plugins/cache/<source>/mthds/<version>/bin/mthds-env-check`. The preamble globs that path.

## Upstream history

- [openai/codex#16732](https://github.com/openai/codex/issues/16732) — **ApplyPatchHandler didn't emit PreToolUse/PostToolUse hook events.** Fixed in Codex 0.124.0: `apply_patch` now serializes hook payloads with `tool_name = "apply_patch"` and `tool_input.command = <patch envelope>`.
- [openai/codex#17087](https://github.com/openai/codex/pull/17087) — **`codex plugin marketplace add`.** Shipped in 0.124.0. Accepts `owner/repo[@ref]`, HTTP(S)/SSH Git URLs, or local marketplace directories.
- **Plugin-bundled hooks.** Shipped in Codex 0.129–0.130: Codex now reads a `hooks` entry from `.codex-plugin/plugin.json` (or a default `hooks/hooks.json`) and loads the hook when `[features] plugin_hooks = true`. This is what lets the plugin ship `codex-hooks.json` directly and retired the `install-hook` workaround.

## What's next

The remaining gap is upstream-blocked:

- **`plugin_hooks` defaults to off.** While it is opt-in, `apply-config` must set it. Once Codex enables plugin hooks by default, that half of `apply-config` becomes unnecessary and the Codex install flow collapses toward the Claude Code shape.

(Stage 3 validation in the Codex sandbox — previously listed here as blocked — is now resolved: pipelex's `validate bundle` is offline-safe and the Codex hook runs it directly.)
