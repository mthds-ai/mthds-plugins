---
name: mthds-pkg
description: Manage MTHDS packages — initialize, configure exports, list, and validate. Use when user says "init package", "set up METHODS.toml", "manage packages", "mthds init", "validate package", "list package", or wants to manage MTHDS package manifests.
min_mthds_version: 0.3.3
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Manage MTHDS packages

Initialize, configure exports, list, and validate MTHDS packages using the `mthds-agent` CLI.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.claude/plugins/marketplaces/mthds-plugins/bin/mthds-env-check "0.3.3" 2>/dev/null || ../mthds-plugins/bin/mthds-env-check "0.3.3" 2>/dev/null || echo "MTHDS_ENV_CHECK_MISSING"
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

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.

- No output or `UP_TO_DATE` → Proceed to Step 1.

- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


Do not write `.mthds` files manually, do not do any other work. The CLI is required for validation, formatting, and execution — without it the output will be broken.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-runner-setup` when you're ready.

### 1. Initialize a package

Create a `METHODS.toml` manifest:

```bash
mthds-agent package init --address <address> --version <version> --description <description> -C <pkg-dir>
```

Required flags:

| Flag | Purpose | Example |
|------|---------|---------|
| `--address` | Package address (hostname/path format) | `github.com/org/repo` |
| `--version` | Package version (semver) | `1.0.0` |
| `--description` | Package description | `"My method package"` |

Optional flags:

| Flag | Purpose | Example |
|------|---------|---------|
| `--authors` | Comma-separated list of authors | `"Alice, Bob"` |
| `--license` | License identifier | `MIT` |
| `--name` | Method name (2-25 lowercase chars) | `my-tool` |
| `--display-name` | Human-readable display name (max 128 chars) | `"My Tool"` |
| `--main-pipe` | Main pipe code (snake_case) | `extract_data` |
| `--force` | Overwrite existing METHODS.toml | — |

### 2. Configure exports

Exports declare which pipes the package makes available to consumers. They are organized by **domain** in `METHODS.toml`:

```toml
[exports.restaurant_analysis]
pipes = ["present_restaurant", "extract_menu", "analyze_menu"]
```

To configure exports:

1. Read the `.mthds` bundle(s) in the package to find the domain codes and pipe codes defined inside them
2. Edit `METHODS.toml` to add an `[exports.<domain>]` section for each domain, listing the pipe codes to export

Rules:

- The `main_pipe` of each bundle is auto-exported — you do not need to list it unless you want to be explicit
- Concepts are always public and do not need to be listed in exports
- Each `[exports.<domain>]` section requires a `pipes` key with a list of pipe code strings

### 3. List package manifest

Display the current package manifest:

```bash
mthds-agent package list -C <pkg-dir>
```

### 4. Validate package manifest

Validate the `METHODS.toml` package manifest:

```bash
mthds-agent package validate -C <pkg-dir>
```

> **Note**: `mthds-agent package validate` validates the `METHODS.toml` package manifest. To validate `.mthds` bundle semantics, use `mthds-agent validate bundle` (see /mthds-check skill).

## The `-C` option

All `mthds-agent package` commands accept `-C <path>` (long: `--package-dir`) to target a package directory other than the shell's current working directory. This is essential when the agent's CWD differs from the package location.

```bash
# From any directory, target a specific package
mthds-agent package init --address github.com/org/repo --version 1.0.0 --description "My package" -C mthds-wip/restaurant_presenter/
mthds-agent package validate -C mthds-wip/restaurant_presenter/
```

If `-C` is omitted, commands default to the current working directory.

## Common Workflows

**Starting a new package**:
1. `mthds-agent package init --address <address> --version <version> --description <desc> -C <pkg-dir>` — create the manifest
2. Read `.mthds` bundles in the package to extract domain codes and pipe codes
3. Edit `METHODS.toml` to set the correct `[exports.<domain>]` sections
4. `mthds-agent package validate -C <pkg-dir>` — validate the manifest

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
