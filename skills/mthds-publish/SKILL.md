---
name: mthds-publish
min_mthds_version: 0.2.1
description: Publish MTHDS methods to mthds.sh. Use when user says "publish this method", "publish to mthds", "publish my methods", "mthds publish", "register my method", or wants to publish a method package to the mthds.sh hub.
---

# Publish MTHDS methods to mthds.sh

Publish method packages to mthds.sh (telemetry tracking). No files are written, no runner is installed — this only registers the method on the hub.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
if ! command -v mthds-agent &>/dev/null; then
  echo "MTHDS_AGENT_MISSING"
else
  # Version gate: block if mthds-agent is too old for this plugin
  # NOTE: This bash semver comparison must stay in sync with the TypeScript
  # implementation in mthds-js/src/installer/runtime/version-check.ts.
  # Both implement major.minor.patch comparison. The bash version is
  # intentionally simpler (no prerelease/build metadata support).
  INSTALLED=$(mthds-agent --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  REQUIRED="0.2.1"
  if [ -z "$INSTALLED" ]; then
    echo "MTHDS_AGENT_VERSION_UNKNOWN"
  else
    IFS='.' read -r ia ib ic <<< "$INSTALLED"
    IFS='.' read -r ra rb rc <<< "$REQUIRED"
    if [ "$ia" -lt "$ra" ] 2>/dev/null ||
       { [ "$ia" -eq "$ra" ] && [ "$ib" -lt "$rb" ]; } 2>/dev/null ||
       { [ "$ia" -eq "$ra" ] && [ "$ib" -eq "$rb" ] && [ "$ic" -lt "$rc" ]; } 2>/dev/null; then
      echo "MTHDS_AGENT_OUTDATED $INSTALLED $REQUIRED"
    else
      UPDATE_ERR_FILE=$(mktemp 2>/dev/null) || {
        echo "MTHDS_UPDATE_CHECK_FAILED exit=mktemp"
      }
      if [ -n "$UPDATE_ERR_FILE" ]; then
        UPDATE_OUTPUT=$(mthds-agent update-check 2>"$UPDATE_ERR_FILE")
        UPDATE_EXIT=$?
        UPDATE_ERR=$(cat "$UPDATE_ERR_FILE" 2>/dev/null)
        rm -f "$UPDATE_ERR_FILE"
        if [ $UPDATE_EXIT -ne 0 ]; then
          echo "MTHDS_UPDATE_CHECK_FAILED exit=$UPDATE_EXIT"
          [ -n "$UPDATE_ERR" ] && echo "$UPDATE_ERR"
          [ -n "$UPDATE_OUTPUT" ] && echo "$UPDATE_OUTPUT"
        elif [ -n "$UPDATE_OUTPUT" ]; then
          echo "$UPDATE_OUTPUT"
        fi
      fi
    fi
  fi
fi
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


### Step 1: Identify the Source

Determine where the method package lives:

| Source | Syntax | Example |
|--------|--------|---------|
| GitHub (short) | `org/repo` | `mthds-ai/contract-analysis` |
| GitHub (full URL) | `https://github.com/org/repo` | `https://github.com/mthds-ai/contract-analysis` |
| Local directory | `--local <path>` | `--local ./my-methods/` |

### Step 2: Run the Publish Command

**From GitHub**:

```bash
mthds-agent publish <org/repo>
```

**From a local directory**:

```bash
mthds-agent publish --local <path>
```

**Publish a specific method from a multi-method package**:

```bash
mthds-agent publish <org/repo> --method <name>
```

| Flag | Required | Values | Description |
|------|----------|--------|-------------|
| `[address]` | Yes* | `org/repo` | GitHub repo address |
| `--local <path>` | Yes* | directory path | Publish from a local directory |
| `--method <name>` | No | method name | Publish only one method from a multi-method package |

*One of `address` or `--local` is required.

### Step 3: Parse the Output

On success, the CLI returns JSON:

```json
{
  "success": true,
  "published_methods": ["method-name"],
  "address": "org/repo"
}
```

Present to the user:
- Which methods were published
- The address on mthds.sh

### Step 4: Offer to Share

After a successful publish, ask the user if they want to share their methods on social media. If yes, use the `/mthds-share` skill or run `mthds-agent share` directly.

### Step 5: Handle Errors

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to resolve methods` | GitHub repo not found or no methods in repo | Verify the address and that the repo contains METHODS.toml |
| `Method "X" not found` | `--method` filter doesn't match any method | Check available method names in the package |
| `No valid methods to publish` | No methods passed validation | Check METHODS.toml in the package |

For all error types and recovery strategies, see [Error Handling Reference](../shared/error-handling.md).

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
