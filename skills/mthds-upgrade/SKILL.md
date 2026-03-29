---
name: mthds-upgrade
min_mthds_version: 0.2.1
description: >
  Upgrade MTHDS CLI tools to the latest compatible versions.
  Use when: "upgrade mthds", "update mthds", "mthds upgrade",
  "update my tools", "upgrade pipelex", "update pipelex",
  "upgrade plxt", "update tools".
---

## Step 0 — Environment check

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


## Step 1 — Force version check

Run this bash:

```bash
mthds-agent update-check --force
```

Interpret the output:
- No output or `UP_TO_DATE`: All tools are up to date. Tell the user and stop.
- `UPGRADE_AVAILABLE <json>`: Upgrades are available. Read `../shared/upgrade-flow.md` and follow the upgrade flow.
- `JUST_UPGRADED <json>`: Tools were just upgraded. Report what changed and stop.
- `MTHDS_AGENT_OUTDATED <installed> <required>`: mthds-agent itself is outdated. Warn the user that their mthds-agent (v\<installed>) is older than v\<required> and suggest `npm install -g mthds@latest`, but do not block — proceed to Step 2.

## Step 2 — Report summary

After upgrade completes (or if already up to date), summarize:
- Which tools were checked
- Which were upgraded (with old -> new versions)
- Which failed (with manual install commands)
- Current status of all tools

## Reference

- Upgrade flow details: `../shared/upgrade-flow.md`
- Tool install guide: `../shared/mthds-agent-guide.md`
