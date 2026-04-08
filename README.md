# MTHDS Plugins

A skills plugin for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenAI Codex](https://developers.openai.com/codex) for building, running, validating, and editing AI methods (.mthds bundle files).

[MTHDS](https://mthds.ai/latest/) is an open standard for AI methods. Find methods on the hub: [MTHDS Hub](https://mthds.sh). Install the reference python runtime from [Pipelex](https://github.com/Pipelex/pipelex).

## Install for Claude Code

Open Claude Code and paste this. Claude does the rest.

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && claude plugin marketplace add mthds-ai/mthds-plugins && claude plugin install mthds@mthds-plugins'. Then tell me to restart Claude Code.
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
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && bash <(curl -fsSL https://raw.githubusercontent.com/mthds-ai/mthds-plugins/main/bin/install-codex.sh)'. Then tell me to restart Codex and run /plugins to install mthds.
```

### Manual install (Codex)

```bash
npm install -g mthds
mthds-agent bootstrap
bash bin/install-codex.sh
# Restart Codex, then run /plugins to install mthds
```

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

## Automatic validation

Both plugins include hooks that validate `.mthds` files automatically:

1. **Lint** — `plxt lint` validates TOML structure and schema
2. **Format** — `plxt fmt` auto-formats the file
3. **Validate** — `mthds-agent validate bundle` checks semantic correctness

**Claude Code:** A PostToolUse hook fires on every `.mthds` file edit. Errors block the edit immediately.

**Codex:** A Stop hook fires at the end of every turn. It finds all changed `.mthds` files via `git diff`, validates each one, and tells Codex to continue and fix any errors before finishing.

Missing tools (`plxt`, `mthds-agent`) block `.mthds` edits until installed.

## License

[MIT](LICENSE) — Copyright (c) 2026 Evotis S.A.S.

Maintained by [Pipelex](https://pipelex.com).
"Pipelex" is a trademark of Evotis S.A.S.
