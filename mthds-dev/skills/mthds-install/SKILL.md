---
name: mthds-install
description: Install MTHDS method packages from GitHub or local directories. Use when user says "install a method", "install from GitHub", "add a method package", "mthds install", "install method", "set up a method", or wants to install an MTHDS method package for use with an AI agent.
min_mthds_version: 0.10.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Install MTHDS method packages

Install method packages from GitHub or local directories using the `mthds-agent` CLI.

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
[ -n "$_best_f" ] && exec "$_best_f" "0.10.0"
echo "MTHDS_ENV_CHECK_MISSING"
'
```

**Interpret the output:**

- `MTHDS_AGENT_MISSING` → STOP. Do not proceed. Tell the user:

> The `mthds-agent` CLI is required but not installed. Install it with:
>
> ```
> rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_VERSION_UNKNOWN` → STOP. The installed `mthds-agent` returned an unparseable version. Tell the user:

> Could not parse the output of `mthds-agent --version`. Your installation may be corrupt. Reinstall with:
>
> ```
> rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_OUTDATED <installed> <required>` → The installed `mthds-agent` is too old for this plugin. **Do not hard-stop.** Instead, tell the user their mthds-agent (v\<installed>) is older than the required v\<required>, then follow the [upgrade flow](../shared/upgrade-flow.md) to offer upgrading mthds-agent via `rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/`. After the upgrade flow completes (whether the user upgraded or declined), proceed to Step 1. The upgrade flow's "Not now" and "Never ask" options let users continue with current versions.

- `MTHDS_UPDATE_CHECK_FAILED ...` → WARN. The update check command failed. Show the error output to the user. Suggest checking network connectivity and `mthds-agent` installation. Proceed to Step 1 with current versions.

- `UPGRADE_AVAILABLE ...` → Read [upgrade flow](../shared/upgrade-flow.md) and follow the upgrade prompts before continuing to Step 1.

- `JUST_UPGRADED ...` → Announce what was upgraded to the user, then continue to Step 1.

- `UP_TO_DATE ...` → Proceed to Step 1. The line is a terse list of verified installed versions (e.g. `UP_TO_DATE mthds-agent=0.10.0 plxt=0.4.0 plugin=0.12.0`); if you mention the env-check in your preamble acknowledgement, relay the agent and plugin versions you saw. Two "explicit-quiet" variants share the same prefix and are also clean — proceed to Step 1 without warning, and do not relay the quiet state unless the user is troubleshooting:
  - `UP_TO_DATE update-check=disabled` — the user has turned update-check off via config.
  - `UP_TO_DATE update-check=snoozed` — the user has an active snooze on the current version key; an upgrade would otherwise be available, but they explicitly asked for quiet.

- No output → WARN. The env-check produced no output at all, which usually means `mthds-agent` itself is broken or the wrapper script bailed before printing. Tell the user the environment check could not be confirmed, then proceed cautiously to Step 1.

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.



- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


Do not attempt manual installation. The CLI handles resolution, file placement, shim generation, and runtime setup.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-runner-setup` when you're ready.

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
| `--location` | Yes | `local`, `global` | `local` = project `.mthds/methods/`, `global` = `~/.mthds/methods/` |
| `--method <name>` | No | method name | Install only one method from a multi-method package |
| `--no-runner` | No | — | Skip automatic Pipelex runtime installation |

Method packages always install under `.mthds/methods/` regardless of which agent runs the command.

**Defaults**:
- Use `--location local` unless the user explicitly asks for global install

### Step 3: Run the Install

**From GitHub**:

```bash
mthds-agent install <org/repo> --location local
```

**From a local directory**:

```bash
mthds-agent install --local <path> --location local
```

**Install a specific method from a multi-method package**:

```bash
mthds-agent install <org/repo> --location local --method <name>
```

### Step 4: Present Results

On success, the CLI returns JSON:

```json
{
  "success": true,
  "installed_methods": ["method-name"],
  "location": "local",
  "target_dir": "/path/to/.mthds/methods",
  "shim_dir": "~/.mthds/bin",
  "shims_generated": ["method-name"]
}
```

Present to the user:
- Which methods were installed and where (`target_dir`)
- If CLI shims were generated, note the shim directory and advise adding `~/.mthds/bin` to PATH if not already present

### Step 5: Handle Errors

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `--location is required` | Missing `--location` flag | Add `--location local` or `--location global` |
| `Failed to resolve methods` | GitHub repo not found or no methods in repo | Verify the address and that the repo contains METHODS.toml |
| `Method "X" not found` | `--method` filter doesn't match any method in the package | Check available method names in the package |
| `Failed to install pipelex runtime` | Runtime install failed (network, permissions) | Retry, or use `--no-runner` to skip runtime install |

For all error types and recovery strategies, see [Error Handling Reference](../shared/error-handling.md).

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
