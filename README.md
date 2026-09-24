# mthds-plugins

The MTHDS plugin for Claude Code and Codex, superseded by the Pipelex plugin.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mthds-ai/mthds-plugins/blob/main/LICENSE)

**To build and run AI methods from your coding agent, install [the Pipelex plugin](https://github.com/Pipelex/pipelex-plugins).** It supersedes this one: its skills write and run methods, its hook checks every edit, and it brings the Pipelex tools with it. This page is kept for those who already use the MTHDS plugin.

## What this repository is

This repository is the `mthds-plugins` marketplace. Its plugin, `mthds`, gives Claude Code and Codex the `mthds-*` skills and a hook that validates every `.mthds` file your agent edits. The skills work through the [`mthds-agent`](https://www.npmjs.com/package/mthds) CLI, which drives a runtime installed on your machine.

[MTHDS](https://mthds.ai/latest/) is an open standard for AI methods, and a method runs on any MTHDS-compliant runtime; [Pipelex](https://github.com/Pipelex/pipelex) is the reference one. Methods are shared on the [MTHDS Hub](https://mthds.sh).

## Install

If you already use the MTHDS plugin and need it on another machine, paste the line for your agent into its chat, not into a terminal, and the agent runs the rest.

**Claude Code**

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && claude plugin marketplace add mthds-ai/mthds-plugins && claude plugin install mthds@mthds-plugins'. Then tell me to /reload-plugins.
```

**Codex**, 0.130 or later

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && mthds-agent codex apply-config && codex plugin marketplace add mthds-ai/mthds-plugins'. Then tell me to restart Codex and run /plugins to install mthds.
```

The manual commands, and what `mthds-agent codex apply-config` changes in `~/.codex/`, are in [Install the MTHDS plugin](docs/install.md).

## Skills

The skills work the same in both agents: `/skill-name` in Claude Code, `$skill-name` in Codex.

| Skill | What it does |
|:------|:-------------|
| `mthds-upgrade` | Upgrade the MTHDS stack to its latest version |
| `mthds-build` | Build a new method bundle from scratch |
| `mthds-check` | Validate a bundle, without changing it |
| `mthds-edit` | Modify an existing bundle |
| `mthds-explain` | Explain and document a method |
| `mthds-fix` | Fix validation errors automatically |
| `mthds-run` | Run a method and interpret its output |
| `mthds-inputs` | Prepare inputs: templates, synthetic data, files |
| `mthds-install` | Install method packages from GitHub or a local path |
| `mthds-runner-setup` | Set up inference backends and API keys |
| `mthds-pkg` | Manage MTHDS packages: init, dependencies, lock |
| `mthds-publish` | Publish methods to mthds.sh |
| `mthds-share` | Share methods on social media |
| `mthds-recursive` | Write a complete bundle directly, in a single pass |

## Automatic validation

After every edit your agent makes to a `.mthds` file, the plugin's hook checks the file in three stages, and when the file is wrong it stops your agent and hands it the errors to fix:

1. **Lint** — `plxt lint` validates the TOML structure and the schema.
2. **Format** — `plxt fmt` formats the file.
3. **Validate** — the runtime's validator checks that the method is semantically correct.

A problem with your environment rather than with the file, such as a missing configuration, is passed to your agent as context without stopping it, and so is a formatting failure in Claude Code. A missing `plxt` stops the agent on every `.mthds` edit until it is installed. What each stage does in each agent is in [Codex vs Claude Code hooks](docs/codex-vs-claude-hooks.md).

## Documentation

- [Install the MTHDS plugin](docs/install.md): the manual install for each agent, and the Codex configuration.
- [Codex vs Claude Code hooks](docs/codex-vs-claude-hooks.md): how the validation hook runs in each agent.
- [The MTHDS standard](https://mthds.ai/latest/): the language a method is written in.

## Develop

The skills and hooks are rendered from the Jinja2 templates in `templates/`, once per build target; the plugin directories (`mthds/`, `mthds-codex/` and the others) are generated, so edit the templates and rebuild:

```bash
make install   # create .venv and install the dependencies
make build     # render every target from templates/
make check     # the shared, Claude and Codex packaging checks
make test      # the unit tests
```

[Build targets](docs/build-targets.md) explains the targets and their variables.

## License

[MIT](https://github.com/mthds-ai/mthds-plugins/blob/main/LICENSE) — Copyright (c) 2026 Evotis S.A.S.

Maintained by [Pipelex](https://pipelex.com). "Pipelex" is a trademark of Evotis S.A.S.
