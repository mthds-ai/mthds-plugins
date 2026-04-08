---
name: mthds-upgrade
description: Upgrade MTHDS CLI tools to the latest compatible versions. Use when user says "upgrade mthds", "update mthds", "mthds upgrade", "update my tools", "upgrade pipelex", "update pipelex", "upgrade plxt", "update tools".
min_mthds_version: 0.3.5

---

# Upgrade MTHDS CLI tools

Upgrade mthds-agent and its managed tools to the latest versions.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
mthds-env-check "0.3.5" 2>/dev/null || echo "MTHDS_ENV_CHECK_MISSING"
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


### Step 1: Force Version Check

```bash
mthds-agent update-check --force
```

Interpret the output:
- No output or `UP_TO_DATE`: All tools are up to date. Tell the user and stop.
- `UPGRADE_AVAILABLE <json>`: Upgrades are available. Read `../shared/upgrade-flow.md` and follow the upgrade flow.
- `JUST_UPGRADED <json>`: Tools were just upgraded. Report what changed and stop.
- `MTHDS_AGENT_OUTDATED <installed> <required>`: mthds-agent itself is outdated. Warn the user that their mthds-agent (v\<installed>) is older than v\<required> and suggest `npm install -g mthds@latest`, but do not block — proceed to Step 2.

### Step 2: Report Summary

After upgrade completes (or if already up to date), summarize:
- Which tools were checked
- Which were upgraded (with old -> new versions)
- Which failed (with manual install commands)
- Current status of all tools

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [Upgrade Flow](../shared/upgrade-flow.md) — read for upgrade prompt details and user preference handling
