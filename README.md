# MTHDS Plugins

A skills plugin for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenAI Codex](https://developers.openai.com/codex) for building, running, validating, and editing AI methods (.mthds bundle files).

[MTHDS](https://mthds.ai/latest/) is an open standard for AI methods. Find methods on the hub: [MTHDS Hub](https://mthds.sh). Install the reference python runtime from [Pipelex](https://github.com/Pipelex/pipelex).

## Install for Claude Code

Open Claude Code and paste this. Claude does the rest.

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && claude plugin marketplace add mthds-ai/mthds-plugins && claude plugin install mthds@mthds-plugins'. Then tell me to /reload-plugins.
```

### Manual install (Claude Code)

```bash
npm install -g mthds
mthds-agent bootstrap
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

## Install for Codex

Open Codex and paste this. Codex does the rest.

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && mthds-agent codex apply-config && codex plugin marketplace add mthds-ai/mthds-plugins'. Then tell me to restart Codex and run /plugins to install mthds.
```

Requires Codex 0.130.0+ (plugin-bundled hooks shipped in 0.130). Bump with `npm install -g @openai/codex@latest` if needed.

### Manual install (Codex)

```bash
npm install -g mthds
mthds-agent bootstrap                # uv + plxt + pipelex-agent
mthds-agent codex apply-config       # set up ~/.codex/ for the mthds plugin
codex plugin marketplace add mthds-ai/mthds-plugins
# Restart Codex, then run /plugins to install mthds
```

The `.mthds` validation hook ships inside the plugin (`hooks/codex-hooks.json`, declared in the Codex plugin manifest); Codex discovers it directly once the plugin is installed — there is no per-user hook wiring step.

`mthds-agent codex apply-config` makes one-time additive changes to `~/.codex/config.toml`:

- `[features] plugin_hooks = true` — Codex only loads plugin-bundled hooks when this is enabled.
- `[sandbox_workspace_write] network_access = true` — Codex's default workspace-write sandbox otherwise blocks outbound network for hook commands.

It also removes any obsolete `~/.codex/hooks.json` entry left by older mthds installs (which used a now-retired `install-hook` step). The command is idempotent and never overwrites unrelated config — use `--dry-run` to preview, `--check` for CI/env-check. See `docs/codex-vs-claude-hooks.md`.

If mthds gets installed without this step (for example, added straight from the marketplace UI), the skills catch it: their Step 0 env-check detects the gap and offers to run `apply-config` for you. Running it up front just avoids building your first method before the validation hook is live.

## Skills

Skills work identically on both Claude Code (`/skill-name`) and Codex (`$skill-name`).

| Skill | Description |
|:------|:------------|
| `mthds-upgrade` | Upgrade MTHDS stack to latest version |
| `mthds-build` | Build new AI method bundles from scratch |
| `mthds-check` | Validate workflow bundles (read-only) |
| `mthds-edit` | Modify existing bundles |
| `mthds-explain` | Explain and document workflows |
| `mthds-fix` | Auto-fix validation errors |
| `mthds-run` | Execute methods and interpret output |
| `mthds-inputs` | Prepare inputs: templates, synthetic data, files |
| `mthds-install` | Install method packages from GitHub or local |
| `mthds-runner-setup` | Set up inference backends and API keys |
| `mthds-pkg` | Manage MTHDS packages (init, deps, lock) |
| `mthds-publish` | Publish methods to mthds.sh |
| `mthds-share` | Share methods on social media |
| `mthds-recursive` | Write a complete MTHDS bundle directly in a single pass |

## Automatic validation

Both plugins include hooks that validate `.mthds` files automatically:

1. **Lint** — `plxt lint` validates TOML structure and schema
2. **Format** — `plxt fmt` auto-formats the file
3. **Validate** — `mthds-agent validate bundle` checks semantic correctness

**Claude Code:** A PostToolUse hook matches Write/Edit and receives the file path directly. Errors block the edit immediately.

**Codex:** A PostToolUse hook matches `apply_patch` (Codex's file-write tool) and parses the patch envelope to find every touched `.mthds` file. Same per-edit validation, same immediate feedback.

Missing tools (`plxt`, `mthds-agent`) block `.mthds` edits until installed.

## License

[MIT](LICENSE) — Copyright (c) 2026 Evotis S.A.S.

Maintained by [Pipelex](https://pipelex.com).
"Pipelex" is a trademark of Evotis S.A.S.
