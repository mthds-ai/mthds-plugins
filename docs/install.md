# Install the MTHDS plugin

The MTHDS plugin is superseded by [the Pipelex plugin](https://github.com/Pipelex/pipelex-plugins), which is the one to install to build and run methods from your coding agent. This page is for those who already use the MTHDS plugin. The one-line installs are in the [README](../README.md#install); these are the same steps, run by hand.

Every install starts with the `mthds-agent` CLI and its bootstrap, which installs `uv`, the `plxt` linter and the runtime the skills drive.

## Claude Code

```bash
npm install -g mthds
mthds-agent bootstrap
claude plugin marketplace add mthds-ai/mthds-plugins
claude plugin install mthds@mthds-plugins
```

Then run `/reload-plugins` in Claude Code, or start a new session.

## Codex

The plugin needs Codex 0.130 or later, the first release that loads the hooks a plugin bundles. Upgrade with `npm install -g @openai/codex@latest` if yours is older.

```bash
npm install -g mthds
mthds-agent bootstrap
mthds-agent codex apply-config
codex plugin marketplace add mthds-ai/mthds-plugins
```

Then restart Codex and run `/plugins` to install `mthds`.

The `.mthds` validation hook ships inside the plugin (`hooks/codex-hooks.json`, declared in the Codex plugin manifest), so Codex finds it once the plugin is installed, with no hook to wire up yourself. What it needs is the configuration `mthds-agent codex apply-config` writes, a one-time, additive change to `~/.codex/config.toml`:

- `[features] plugin_hooks = true`, because Codex loads the hooks a plugin bundles only when this is set.
- `[sandbox_workspace_write] network_access = true`, because Codex's default workspace-write sandbox otherwise blocks outbound network for hook commands.

It also removes the `~/.codex/hooks.json` entry that older installs left behind, from the `install-hook` step they used to run. Running it twice changes nothing, and it never overwrites configuration it does not own. Use `--dry-run` to preview the change, and `--check` to exit non-zero when something would change, without writing.

If the plugin is installed without this step — added from the marketplace screen, for instance — the skills notice: their environment check detects the missing configuration and offers to run `apply-config` for you. Running it up front means the validation hook is live before you build your first method.

Why the Codex hook differs from the Claude Code one is in [Codex vs Claude Code hooks](codex-vs-claude-hooks.md).
