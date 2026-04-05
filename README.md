# MTHDS Plugins

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills plugin for building, running, validating, and editing AI methods (.mthds bundle files).

[MTHDS](https://mthds.ai/latest/) is an open standard for AI methods. Find methods on the hub: [MTHDS Hub](https://mthds.sh). Install the reference python runtime from [Pipelex](https://github.com/Pipelex/pipelex).

## Installation

Open Claude Code and paste this. Claude does the rest.

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && claude plugin marketplace add mthds-ai/mthds-plugins && claude plugin install mthds@mthds-plugins' then tell me the result. If it worked, add a "MTHDS" section to CLAUDE.md that lists the available skills (/mthds-build, /mthds-run, /mthds-check, /mthds-edit, /mthds-explain, /mthds-fix, /mthds-inputs, /mthds-install, /mthds-runner-setup, /mthds-pkg, /mthds-publish, /mthds-share, /mthds-upgrade) and notes that .mthds files are automatically validated when the agent modifies them and that MTHDS is the open language for executable AI methods, defined at mthds.ai. Then tell me to restart Claude Code with /exit and claude.
```

### Manual install

```bash
npm install -g mthds
mthds-agent bootstrap
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Restart Claude Code (`/exit`, then `claude`).

## Skills to use with [MTHDS](https://mthds.ai/latest/)

| Skill | Description |
|:------|:------------|
| `/mthds-upgrade` | Upgrade MTHDS stack to latest version |
| `/mthds-build` | Build new AI method bundles from scratch |
| `/mthds-check` | Validate workflow bundles (read-only) |
| `/mthds-edit` | Modify existing bundles |
| `/mthds-explain` | Explain and document workflows |
| `/mthds-fix` | Auto-fix validation errors |
| `/mthds-run` | Execute methods and interpret output |
| `/mthds-inputs` | Prepare inputs: templates, synthetic data, files |
| `/mthds-install` | Install method packages from GitHub or local |
| `/mthds-runner-setup` | Set up inference backends and API keys |
| `/mthds-pkg` | Manage MTHDS packages (init, deps, lock) |
| `/mthds-publish` | Publish methods to mthds.sh |
| `/mthds-share` | Share methods on social media |

## What happens automatically

The plugin includes a **PostToolUse hook** that fires on every `.mthds` file edit:

1. **Lint** — `plxt lint` validates TOML structure and schema
2. **Format** — `plxt fmt` auto-formats the file
3. **Validate** — `mthds-agent validate bundle` checks semantic correctness

Errors block the edit. Warnings are shown but don't block. Missing tools (`plxt`, `mthds-agent`) block `.mthds` edits until installed.

## License

[MIT](LICENSE) — Copyright (c) 2026 Evotis S.A.S.

Maintained by [Pipelex](https://pipelex.com).
"Pipelex" is a trademark of Evotis S.A.S.
