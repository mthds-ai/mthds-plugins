# Codex vs Claude Code Hooks

Both plugins validate `.mthds` files automatically after edits. The validation pipeline is the same shape (plxt lint, plxt fmt, mthds-agent validate), and as of Codex 0.124.0 the hook event is the same too — `PostToolUse` with a tool-name matcher. The remaining differences are about how each platform handles plugin packaging and hook delivery.

## Claude Code hook

- **Event:** `PostToolUse` with matcher `Write|Edit`
- **Trigger:** fires immediately after every file write or edit
- **File discovery:** receives the exact file path from `tool_input.file_path` in stdin JSON
- **Scope:** validates one file per invocation
- **Sandbox:** hooks run without network restrictions
- **Stages:** plxt lint, plxt fmt, mthds-agent validate bundle (all three)
- **Implementation:** bash script `templates/hooks/validate-mthds.sh.j2` (rendered into `mthds/hooks/`)
- **Wiring:** `hooks.json` is bundled inside the plugin and auto-loaded by Claude Code

## Codex hook

- **Event:** `PostToolUse` with matcher `apply_patch`
- **Trigger:** fires once per `apply_patch` call (one fire per multi-file patch, with all touched files in a single payload)
- **File discovery:** parses `tool_input.command` (the raw apply_patch envelope) for `*** Update File:` / `*** Add File:` / `*** Move to:` headers
- **Scope:** validates every `.mthds` file that exists on disk after the patch applies (rename source paths and `*** Delete File:` targets are silently skipped)
- **Sandbox:** hooks run inside the Codex sandbox with restricted network access
- **Stages:** plxt lint, plxt fmt only — Stage 3 (`mthds-agent validate bundle`) stays disabled until offline-mode validation lands in mthds-agent
- **Implementation:** `mthds-agent codex hook` — a TypeScript subcommand of mthds-js (≥ 0.5.0). The plugin ships no hook files.
- **Wiring:** `mthds-agent codex install-hook` writes a `PostToolUse(apply_patch)` entry into `~/.codex/hooks.json` whose `command` is the literal string `mthds-agent codex hook` (PATH-resolved at hook-fire time)

## Why the differences

### Hook script vs `tool_input.command`

`apply_patch` is Codex's freeform file-write tool: the model emits a heredoc-shaped patch envelope (`*** Begin Patch / *** Update File: <path> / @@ ... / *** End Patch`) instead of distinct write/edit calls. The PostToolUse payload exposes that envelope verbatim as `tool_input.command`. The hook parses the envelope's `*** Update File: / *** Add File: / *** Move to:` headers to discover every touched file. There is no equivalent of Claude Code's `tool_input.file_path` because a single `apply_patch` call can touch any number of files.

### Hook implementation lives in mthds-agent, not the plugin

Claude Code auto-loads `hooks/hooks.json` from the plugin manifest, so the validation logic naturally lives inside the plugin (a bash script under `${CLAUDE_PLUGIN_ROOT}/hooks/`). Codex doesn't (yet) read a `hooks` field from `plugin.json` (`RawPluginManifest` in `codex-rs/core-plugins/src/manifest.rs:11-30` lacks the field). The hook config has to live at `~/.codex/hooks.json`, written by something the user runs at install time.

Two options for "what runs":

1. **Copy a script into `~/.codex/hooks/` at install time.** Older approach (the now-retired `bin/install-codex.sh`). The hook config points at the copied path. Pros: no agent dependency. Cons: requires a separate install step, copies break when the plugin upgrades, validation logic is duplicated bash that must stay in sync with the Claude version.

2. **Invoke `mthds-agent codex hook` via `PATH`.** Current approach. The hook config's `command` is just the agent subcommand string. The agent itself is already on PATH after `npm install -g mthds`. Pros: no copies, no per-version path drift, validation logic versioned with mthds-agent (single source of truth across platforms). Cons: requires mthds-agent to be installed (true anyway — every other skill in the plugin needs it).

We picked option 2. The plugin no longer ships any hook files; `mthds-agent codex install-hook` is a one-time JSON merge, not a file-copy step.

### `mthds-agent validate` still disabled in the Codex sandbox

`mthds-agent validate bundle` fetches remote Pipelex configuration from S3 (`pipelex_remote_config_08.json`) on startup. The Codex sandbox blocks this network call and the command hangs. Validation itself is local — the remote config is not actually needed for structural checks — so the fix is to make the remote fetch lazy / skippable in `mthds-agent`. Tracked as Phase 2D in `TODOS.md`. Until then, the Codex hook runs only plxt lint + plxt fmt; Claude Code runs all three stages.

### Sandbox network access

By default, Codex's `workspace-write` sandbox blocks outbound network for hook commands. Even after Phase 2D ships, any future runtime call that talks to the network (telemetry, package resolution, remote pipelex config) will fail silently inside the sandbox unless the user opts in. The fix is one TOML key:

```toml
[sandbox_workspace_write]
network_access = true
```

`mthds-agent codex apply-config` (mthds-js ≥ 0.6.0) merges that key into `~/.codex/config.toml` additively — it never removes or rewrites unrelated keys, and re-running it is a no-op. Use `--dry-run` to preview, `--check` for env-check / CI gating.

The same command also warns (without modifying anything) when:

- `[features] hooks = false` (or its alias `[features] codex_hooks = false`) is explicitly set. The hooks flag defaults to enabled, so the install flow does not need to set it. An explicit `false` on either name disables hooks entirely and breaks the plugin.
- `sandbox_mode = "read-only"`, which prevents `apply_patch` from running at all.

`mthds-agent doctor` runs the same inspection in read-only mode and surfaces the same warnings, so a user who runs `doctor` before installing learns about both issues without anything being written.

### plxt lazy HTTP fix

`plxt` had an eager `reqwest` client initialization that crashed in the Codex sandbox; it was made lazy in `vscode-pipelex` PR #38 (only created when lint encounters http/https schema sources).

## Install flows

Claude Code:

```bash
npm install -g mthds
mthds-agent bootstrap
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Codex 0.124.0+:

```bash
npm install -g mthds
mthds-agent bootstrap
mthds-agent codex install-hook
mthds-agent codex apply-config
codex plugin marketplace add mthds-ai/mthds-plugins
# then /plugins inside Codex to install — there's no one-shot CLI install yet
```

The Codex flow has two extra steps until upstream Codex auto-loads the `hooks` field from `plugin.json` and lands a way to opt-in to sandbox network for plugin-declared hook commands. When both land, both flows collapse to the same shape.

## env-check resolution

The Codex skill preamble runs `mthds-env-check` to verify `mthds-agent` is installed and at the required version. The env-check binary lives at `bin/mthds-env-check` inside the plugin. After `codex plugin marketplace add` + `/plugins install`, Codex stages a per-version copy under `$CODEX_HOME/plugins/cache/<source>/mthds/<version>/bin/mthds-env-check`. The preamble globs that path. Nothing is copied to `~/.codex/bin/`.

## Tracked upstream issues

- [openai/codex#16732](https://github.com/openai/codex/issues/16732) — **ApplyPatchHandler doesn't emit PreToolUse/PostToolUse hook events.** **FIXED in 0.124.0** ([PR #18391](https://github.com/openai/codex/pull/18391)). `apply_patch` now serializes hook payloads with `tool_name = "apply_patch"` and `tool_input.command = <patch envelope>`. `Write` and `Edit` are accepted as matcher aliases for ergonomics.
- [openai/codex#14754](https://github.com/openai/codex/issues/14754) — **Add PreToolUse and PostToolUse hook events for code quality enforcement.** Subsumed by #16732.
- [openai/codex#17087](https://github.com/openai/codex/pull/17087) — **`codex marketplace add` command.** **SHIPPED** as `codex plugin marketplace add` (note the `plugin` namespace). Accepts `owner/repo[@ref]`, HTTP(S) Git URLs, SSH URLs, or local marketplace root directories.
- (no public issue yet) — **`hooks` field in plugin manifest deserializer.** `RawPluginManifest` in `codex-rs/core-plugins/src/manifest.rs:11-30` lacks a `hooks` field; the docs reference one. Phase 2A in `TODOS.md` may file this issue.

## What's next

See `TODOS.md` for the full roadmap. Phase 2 items (upstream-blocked or out-of-repo): plugin-manifest `hooks` field deserializer, single-shot `codex plugin install`, mthds-agent offline-mode validation.
