---
name: mthds-install
min_mthds_version: 0.2.1
description: Install MTHDS method packages from GitHub or local directories. Use when user says "install a method", "install from GitHub", "add a method package", "mthds install", "install method", "set up a method", or wants to install an MTHDS method package for use with an AI agent.
---

# Install MTHDS method packages

Install method packages from GitHub or local directories using the `mthds-agent` CLI.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.claude/plugins/marketplaces/mthds-plugins/bin/mthds-env-check "0.2.1" 2>/dev/null || ../mthds-plugins/bin/mthds-env-check "0.2.1" 2>/dev/null || true
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

- No output or `UP_TO_DATE` → Proceed to Step 1.

- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


Do not attempt manual installation. The CLI handles resolution, file placement, shim generation, and runtime setup.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-pipelex-setup` when you're ready.

### Step 1: Identify the Source

Determine where the method package lives:

| Source | Syntax | Example |
|--------|--------|---------|
| GitHub (short) | `org/repo` | `mthds-ai/contract-analysis` |
| GitHub (full URL) | `https://github.com/org/repo` | `https://github.com/mthds-ai/contract-analysis` |
| Local directory | `--local <path>` | `--local ./my-methods/` |

If the user provides a GitHub URL or `org/repo` string, use it as the address argument. If they point to a local directory, use `--local`.

### Step 2: Choose Install Parameters

| Flag | Required | Values | Description |
|------|----------|--------|-------------|
| `--agent` | Yes | `claude-code`, `cursor`, `codex` | AI agent to install for |
| `--location` | Yes | `local`, `global` | `local` = project `.claude/methods/`, `global` = `~/.claude/methods/` |
| `--method <name>` | No | method name | Install only one method from a multi-method package |
| `--skills` | No | — | Also install the MTHDS skills plugin |
| `--no-runner` | No | — | Skip automatic Pipelex runtime installation |

**Defaults**:
- Use `--agent claude-code` (since this skill runs inside Claude Code)
- Use `--location local` unless the user explicitly asks for global install

### Step 3: Run the Install

**From GitHub**:

```bash
mthds-agent install <org/repo> --agent claude-code --location local
```

**From a local directory**:

```bash
mthds-agent install --local <path> --agent claude-code --location local
```

**Install a specific method from a multi-method package**:

```bash
mthds-agent install <org/repo> --agent claude-code --location local --method <name>
```

**Install with skills plugin**:

```bash
mthds-agent install <org/repo> --agent claude-code --location local --skills
```

### Step 4: Present Results

On success, the CLI returns JSON:

```json
{
  "success": true,
  "installed_methods": ["method-name"],
  "location": "local",
  "target_dir": "/path/to/.claude/methods",
  "installed_skills": [],
  "shim_dir": "~/.mthds/bin",
  "shims_generated": ["method-name"]
}
```

Present to the user:
- Which methods were installed and where (`target_dir`)
- If CLI shims were generated, note the shim directory and advise adding `~/.mthds/bin` to PATH if not already present
- If skills were installed, mention they are now available

### Step 5: Handle Errors

When encountering errors, re-run with `--log-level debug` for additional context:

```bash
mthds-agent --log-level debug install <org/repo> --agent claude-code --location local
```

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `--agent is required` | Missing `--agent` flag | Add `--agent claude-code` |
| `--location is required` | Missing `--location` flag | Add `--location local` or `--location global` |
| `Unknown agent` | Invalid agent ID | Use one of: `claude-code`, `cursor`, `codex` |
| `Failed to resolve methods` | GitHub repo not found or no methods in repo | Verify the address and that the repo contains METHODS.toml |
| `Method "X" not found` | `--method` filter doesn't match any method in the package | Check available method names in the package |
| `Failed to install pipelex runtime` | Runtime install failed (network, permissions) | Retry, or use `--no-runner` to skip runtime install |

For all error types and recovery strategies, see [Error Handling Reference](../shared/error-handling.md).

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
