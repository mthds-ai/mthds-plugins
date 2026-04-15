# Codex vs Claude Code Hooks

Both plugins validate `.mthds` files automatically after edits. The validation pipeline is the same (plxt lint, plxt fmt, mthds-agent validate), but the hook mechanism differs due to platform limitations.

## Claude Code hook

- **Event:** PostToolUse with `Write|Edit` matcher
- **Trigger:** fires immediately after every file write or edit
- **File discovery:** receives the exact file path from `tool_input.file_path` in stdin JSON
- **Scope:** validates one file per invocation
- **Sandbox:** hooks run without network restrictions
- **Stages:** plxt lint, plxt fmt, mthds-agent validate bundle (all three)
- **Template:** `templates/hooks/validate-mthds.sh.j2`

## Codex hook

- **Event:** Stop (fires at end of turn, before Codex finishes)
- **Trigger:** fires once per turn, not per-edit
- **File discovery:** parses `transcript_path` (session transcript JSONL) for `apply_patch` entries containing `.mthds` file paths
- **Scope:** validates all `.mthds` files touched during the turn
- **Sandbox:** hooks run inside the Codex sandbox with restricted network access
- **Stages:** plxt lint, plxt fmt only (mthds-agent validate disabled, see below)
- **Template:** `templates/hooks/codex-validate-mthds.sh.j2`

## Why the differences

### No Write/Edit interception in Codex

Codex's PostToolUse hook only intercepts Bash tool calls. Codex writes files using its internal `apply_patch` tool, which is not exposed to hooks. So we use the Stop hook instead, which fires at the end of every turn regardless of which tools were used.

### Transcript parsing instead of stdin file path

Since the Stop hook doesn't receive file paths, we parse the session transcript (`transcript_path` field in the Stop hook's stdin JSON) to find which `.mthds` files were written. The transcript is a JSONL file where `apply_patch` entries contain `Update File:` or `Add File:` lines with the full file path.

### mthds-agent validate temporarily disabled

`mthds-agent validate bundle` fetches remote Pipelex configuration from S3 on startup (`pipelex_remote_config_08.json`). The Codex sandbox blocks this network call, causing the command to hang until timeout. Since the validation itself is local (the remote config is not needed for structural validation), this is a bug in mthds-agent's eager network access.

**Stage 3 is commented out in the Codex hook** (`codex-validate-mthds.sh`). Only plxt lint + plxt fmt run. Semantic validation is skipped. This means the Codex hook catches TOML syntax and formatting errors but NOT semantic issues like missing pipe inputs, invalid concept references, or broken data flow. The Claude Code hook still runs all three stages.

To re-enable: add offline validation support to `mthds-agent` (in `mthds-js`), then uncomment Stage 3 in the hook template (`templates/hooks/codex-validate-mthds.sh.j2`).

### plxt lazy HTTP fix

plxt also had an eager HTTP client initialization bug that caused crashes in the Codex sandbox. This was fixed by making the reqwest client lazy (only created when lint encounters http/https schema sources). The fix is in vscode-pipelex PR #38.

## Why an install script instead of `codex plugin install`

Claude Code has built-in CLI commands for plugin management:

```bash
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Codex 0.118.0 has no equivalent. There is no `codex plugin install` or `codex marketplace add` CLI command. The `/plugins` browser exists inside Codex but cannot be automated from a script.

On top of that, Codex hooks are separate from plugins. Even if Codex could install the plugin automatically, it would not set up the hooks, the feature flag, or the hooks.json config. The install script handles everything:

1. Copies plugin files into `$PWD/plugins/mthds/`
2. Renders `<project>/.agents/plugins/marketplace.json` from the repo's canonical `packaging/codex-marketplace.json`
3. Copies the hook script to `~/.codex/hooks/`
4. Writes `~/.codex/hooks.json` with the Stop hook config
5. Enables `codex_hooks = true` in `~/.codex/config.toml`

### Coming in Codex 0.119.0

`codex marketplace add` is being added in [openai/codex#17087](https://github.com/openai/codex/pull/17087). This will allow installing plugin marketplaces from local directories, GitHub shorthand, or git URLs with optional `--ref` and `--sparse` checkout. When this ships, the install script can be simplified to:

```bash
codex marketplace add mthds-ai/mthds-plugins
```

The hook setup will still require the script until Codex supports the `"hooks"` field in plugin.json (specced but not yet wired up in the runtime).

## Tracked upstream issues

- [openai/codex#16732](https://github.com/openai/codex/issues/16732) — **ApplyPatchHandler doesn't emit PreToolUse/PostToolUse hook events.** Filed as a bug. `apply_patch` (Codex's file write tool) skips hooks entirely. Root cause: `ApplyPatchHandler` returns `None` for hook payloads, and `hook_runtime.rs` hardcodes `tool_name: "Bash"`. When fixed, we can switch from Stop hook to PostToolUse with `ApplyPatch` matcher and get per-edit validation like Claude Code.
- [openai/codex#14754](https://github.com/openai/codex/issues/14754) — **Add PreToolUse and PostToolUse hook events for code quality enforcement.** Feature request for the same capability.
- [openai/codex#17087](https://github.com/openai/codex/pull/17087) — **Add `codex marketplace add` command.** When shipped, replaces the install script's manual marketplace setup.

## TODO (Codex 0.119.0+)

- Switch to PostToolUse with ApplyPatch matcher when [#16732](https://github.com/openai/codex/issues/16732) is fixed — eliminates transcript parsing, enables per-edit validation
- Replace repo-local install with `codex marketplace add` when [#17087](https://github.com/openai/codex/pull/17087) ships
- Re-enable mthds-agent validate when offline mode is available
- Test if `~/.agents/plugins/marketplace.json` personal install works reliably
- Test if plugin.json `"hooks"` field auto-loads hooks from plugins
