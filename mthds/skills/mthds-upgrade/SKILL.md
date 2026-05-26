---
name: mthds-upgrade
description: Upgrade MTHDS CLI tools to the latest compatible versions. Use when user says "upgrade mthds", "update mthds", "mthds upgrade", "update my tools", "upgrade pipelex", "update pipelex", "upgrade plxt", "update tools".
min_mthds_version: 0.9.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Upgrade MTHDS CLI tools

Upgrade mthds-agent and its managed tools to the latest versions.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
# Wrapped in `bash -c` so the bash array syntax below works even when the
# session shell is zsh.
bash -c '
# Pick the cached env-check from the plugin version with the highest semver.
# Matches both `mthds` (prod) and `mthds-dev` (dev) plugin caches. The padded
# segment trick keeps lex order = semver order so 0.10 does not sort below 0.9.
_best_f=""; _best_k=""
for f in "$HOME/.claude/plugins/cache/"*/mthds*/*/bin/mthds-env-check; do
  [ -x "$f" ] || continue
  _v="${f%/bin/*}"; _v="${_v##*/}"
  _k=""; IFS=. read -ra _parts <<<"${_v%%[-+]*}"
  for _p in "${_parts[@]}"; do _p=${_p%%[!0-9]*}; _k="${_k}$(printf %06d "${_p:-0}")"; done
  [[ "$_k" > "$_best_k" ]] && { _best_f="$f"; _best_k="$_k"; }
done
[ -n "$_best_f" ] && exec "$_best_f" "0.9.0"
echo "MTHDS_ENV_CHECK_MISSING"
'
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

- `UP_TO_DATE ...` → Proceed to Step 1. The line is a terse list of verified installed versions (e.g. `UP_TO_DATE mthds-agent=0.9.0 plxt=0.4.0 plugin=0.12.0`); if you mention the env-check in your preamble acknowledgement, relay the agent and plugin versions you saw. Two "explicit-quiet" variants share the same prefix and are also clean — proceed to Step 1 without warning, and do not relay the quiet state unless the user is troubleshooting:
  - `UP_TO_DATE update-check=disabled` — the user has turned update-check off via config.
  - `UP_TO_DATE update-check=snoozed` — the user has an active snooze on the current version key; an upgrade would otherwise be available, but they explicitly asked for quiet.

- No output → WARN. The env-check produced no output at all, which usually means `mthds-agent` itself is broken or the wrapper script bailed before printing. Tell the user the environment check could not be confirmed, then proceed cautiously to Step 1.

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.



- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


### Step 1: Force Version Check

```bash
mthds-agent update-check --force
```

Interpret the output:
- `UP_TO_DATE ...`: All tools are up to date. Relay the verified versions to the user, then stop. Two "explicit-quiet" variants are also possible — tell the user the check did not actually run normally this time:
  - `UP_TO_DATE update-check=disabled`: the user has turned update-check off via config — the check did not consult the network this run. To run a real check, suggest they re-enable update-check (`mthds-agent config set update-check true`) and re-run this skill.
  - `UP_TO_DATE update-check=snoozed`: the user has an active snooze on the current version key — an upgrade is actually available but suppressed. `--force` clears snooze, so re-running this skill (which calls `update-check --force`) should produce the real status; if you still see snoozed, that indicates a config issue.
- `UPGRADE_AVAILABLE <json>`: Upgrades are available. Read `../shared/upgrade-flow.md` and follow the upgrade flow.
- `JUST_UPGRADED <json>`: Tools were just upgraded. Report what changed and stop.
- No output / non-zero exit / any other output: WARN. `mthds-agent update-check --force` produced no recognizable signal — the binary may be broken, missing a subcommand, or have failed before printing. Show the user any output verbatim, suggest reinstalling `mthds-agent` (`npm install -g mthds@latest`), then stop. Do not assume "all current".

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
