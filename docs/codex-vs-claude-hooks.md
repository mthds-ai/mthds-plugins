# Codex vs Claude Code Hooks

Both plugins validate `.mthds` files automatically after edits. The validation pipeline is the same (plxt lint, plxt fmt, mthds-agent validate), and as of Codex 0.124.0 the hook event is the same too — `PostToolUse` with a tool-name matcher. The remaining differences are about how each platform handles plugin packaging and hook delivery.

## Claude Code hook

- **Event:** `PostToolUse` with matcher `Write|Edit`
- **Trigger:** fires immediately after every file write or edit
- **File discovery:** receives the exact file path from `tool_input.file_path` in stdin JSON
- **Scope:** validates one file per invocation
- **Sandbox:** hooks run without network restrictions
- **Stages:** plxt lint, plxt fmt, mthds-agent validate bundle (all three)
- **Template:** `templates/hooks/validate-mthds.sh.j2`
- **Wiring:** `hooks.json` is bundled inside the plugin and auto-loaded by Claude Code

## Codex hook

- **Event:** `PostToolUse` with matcher `apply_patch`
- **Trigger:** fires once per `apply_patch` call (one fire per multi-file patch, with all touched files in a single payload)
- **File discovery:** parses `tool_input.command` (the raw apply_patch envelope) for `*** Update File:` / `*** Add File:` / `*** Move to:` headers
- **Scope:** validates every `.mthds` file that exists on disk after the patch applies (rename source paths and `*** Delete File:` targets are silently skipped)
- **Sandbox:** hooks run inside the Codex sandbox with restricted network access
- **Stages:** plxt lint, plxt fmt only — Stage 3 (`mthds-agent validate bundle`) stays disabled until offline-mode validation lands in mthds-agent
- **Template:** `templates/hooks/codex-validate-mthds.sh.j2`
- **Wiring:** `bin/install-codex.sh` merges a `PostToolUse(apply_patch)` entry into `~/.codex/hooks.json` and copies the script into `~/.codex/hooks/`

## Why the differences

### Hook script vs `tool_input.command`

`apply_patch` is Codex's freeform file-write tool: the model emits a heredoc-shaped patch envelope (`*** Begin Patch / *** Update File: <path> / @@ ... / *** End Patch`) instead of distinct write/edit calls. The PostToolUse payload exposes that envelope verbatim as `tool_input.command`. The hook parses the envelope's `*** Update File: / *** Add File: / *** Move to:` headers to discover every touched file. There is no equivalent of Claude Code's `tool_input.file_path` because a single `apply_patch` call can touch any number of files.

### `mthds-agent validate` still disabled in the Codex sandbox

`mthds-agent validate bundle` fetches remote Pipelex configuration from S3 (`pipelex_remote_config_08.json`) on startup. The Codex sandbox blocks this network call and the command hangs. Validation itself is local — the remote config is not actually needed for structural checks — so the fix is to make the remote fetch lazy / skippable in `mthds-agent`. Tracked as Phase 2D in `TODOS.md`. Until then, the Codex hook runs only plxt lint + plxt fmt; Claude Code runs all three stages.

### plxt lazy HTTP fix

`plxt` had an eager `reqwest` client initialization that crashed in the Codex sandbox; it was made lazy in `vscode-pipelex` PR #38 (only created when lint encounters http/https schema sources).

## Why an install script is still needed for Codex

Claude Code:

```bash
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Codex 0.124.0+:

```bash
codex plugin marketplace add mthds-ai/mthds-plugins
# then /plugins inside Codex to install — there's no one-shot CLI install yet
```

The plugin code itself installs cleanly via Codex's marketplace command. What Codex doesn't yet do is auto-load `hooks` from a plugin manifest: `RawPluginManifest` (in `codex-rs/core-plugins/src/manifest.rs`) deserializes only `name|version|description|skills|mcp_servers|apps|interface` — the `"hooks": "./hooks/codex-hooks.json"` field documented in the plugin spec is silently dropped. So hooks must still be wired into `~/.codex/hooks.json` out-of-band.

`bin/install-codex.sh` does only that:

1. Ensures `mthds-agent` is on PATH (and ≥ MIN_MTHDS_VERSION)
2. Copies `bin/mthds-env-check` to `~/.codex/bin/`
3. Copies `mthds-codex/hooks/codex-validate-mthds.sh` to `~/.codex/hooks/`
4. Merges a `PostToolUse(apply_patch)` entry into `~/.codex/hooks.json` (idempotent; migrates legacy `Stop` entries from pre-0.9.0 installs)

The `[features] codex_hooks = true` toggle is no longer required — `codex_hooks` is `Stage::Stable, default_enabled: true` in current Codex.

When the upstream `hooks` plugin-manifest field lands, `bin/install-codex.sh` can be deleted entirely and the install collapses to a single `codex plugin marketplace add` line.

## Tracked upstream issues

- [openai/codex#16732](https://github.com/openai/codex/issues/16732) — **ApplyPatchHandler doesn't emit PreToolUse/PostToolUse hook events.** **FIXED in 0.124.0** ([PR #18391](https://github.com/openai/codex/pull/18391)). `apply_patch` now serializes hook payloads with `tool_name = "apply_patch"` and `tool_input.command = <patch envelope>`. `Write` and `Edit` are accepted as matcher aliases for ergonomics.
- [openai/codex#14754](https://github.com/openai/codex/issues/14754) — **Add PreToolUse and PostToolUse hook events for code quality enforcement.** Subsumed by #16732.
- [openai/codex#17087](https://github.com/openai/codex/pull/17087) — **`codex marketplace add` command.** **SHIPPED** as `codex plugin marketplace add` (note the `plugin` namespace). Accepts `owner/repo[@ref]`, HTTP(S) Git URLs, SSH URLs, or local marketplace root directories.
- (no public issue yet) — **`hooks` field in plugin manifest deserializer.** `RawPluginManifest` in `codex-rs/core-plugins/src/manifest.rs:11-30` lacks a `hooks` field; the docs reference one. Phase 2A in `TODOS.md` may file this issue.

## What's next

See `TODOS.md` for the full roadmap. Phase 2 items (upstream-blocked or out-of-repo): plugin-manifest `hooks` field deserializer, single-shot `codex plugin install`, mthds-agent offline-mode validation, optional unification of Claude/Codex hook templates, and moving the install logic into `mthds-agent bootstrap`.
