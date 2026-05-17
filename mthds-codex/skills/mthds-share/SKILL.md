---
name: mthds-share
description: Share MTHDS methods on social media (X/Twitter, Reddit, LinkedIn). Use when user says "share this method", "post on social media", "share on X", "share on Reddit", "share on LinkedIn", "tweet about this method", or wants to share a published method on social platforms.
min_mthds_version: 0.7.0

---

# Share MTHDS methods on social media

Generate share URLs for method packages and open them in the browser. Supports X (Twitter), Reddit, and LinkedIn.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
# Pick the cached env-check from the plugin version with the highest semver.
# Pad each numeric segment to fixed width so lex sort matches semver sort
# (avoids the 0.10 < 0.9 lex-order trap). Sort keys are digits-only by
# construction, so the [[ > ]] compare is locale-independent. Bash 3.2 OK.
_best_f=""; _best_k=""
for f in "${CODEX_HOME:-$HOME/.codex}"/plugins/cache/*/mthds/*/bin/mthds-env-check; do
  [ -x "$f" ] || continue
  _v="${f%/bin/*}"; _v="${_v##*/}"
  _k=""; IFS=. read -ra _parts <<<"${_v%%[-+]*}"
  for _p in "${_parts[@]}"; do _p=${_p%%[!0-9]*}; _k="${_k}$(printf '%06d' "${_p:-0}")"; done
  [[ "$_k" > "$_best_k" ]] && { _best_f="$f"; _best_k="$_k"; }
done
[ -n "$_best_f" ] && exec "$_best_f" "0.7.0" --codex
echo "MTHDS_ENV_CHECK_MISSING"
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

- `CODEX_CONFIG_NEEDS_SETUP` → Codex's `~/.codex/` is not set up for the mthds plugin, so the bundled `.mthds` validation hook will not load. The env-check may print a `#`-prefixed diagnostic line after the status — relay it if present. Resolve this before Step 1:

  1. **Preview** — run `mthds-agent codex apply-config --dry-run` and show the user the output. `WOULD_APPLY` lists the keys it will add under `applied`; `ALREADY_OK` means no keys need adding. Either way, relay any `warnings` entries — those (e.g. read-only sandbox, hooks disabled) need a hand-fix `apply-config` will not perform. If `ALREADY_OK` with no warnings, treat as resolved and go to Step 1.
  2. **Ask** — use AskUserQuestion: "Apply Codex config now?" with options "Apply now" / "Skip".
  3. **Apply now** — run `mthds-agent codex apply-config`:
     - `APPLIED` / `ALREADY_OK` → tell the user the config is fixed and they must **restart Codex** for the validation hook to load (it will not load in this session). Relay any `warnings` — those still need a hand-fix.
     - Error about conflicting keys → show it verbatim; the user must hand-edit `~/.codex/config.toml`, then re-run `mthds-agent codex apply-config`.
     - Error from the sandbox blocking the write to `~/.codex/config.toml` → ask the user to run `mthds-agent codex apply-config` themselves in a terminal, then restart Codex.
  4. **Skip** — tell the user the validation hook stays off until they run `mthds-agent codex apply-config` and restart Codex.

  Then proceed to Step 1. This session has no PostToolUse hook. The mthds skills still run `mthds-agent validate bundle` explicitly, so `.mthds` files built or edited through a skill are still semantically validated — but the write-time `plxt lint`/`fmt` pass depends on the hook and will not run until Codex is restarted.

- No output or `UP_TO_DATE` → Proceed to Step 1.

- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


### Step 1: Ask the User

Before sharing, gather two pieces of information:

1. Which method(s) to share (address or local path) — ask as a free-text question if not already known from context.

2. Use AskUserQuestion with multiSelect to ask about platforms:
   - **Question**: "Which platforms do you want to share on?"
   - **Header**: "Platforms"
   - **multiSelect**: true
   - **Options**:
     1. **X (Twitter)** — "Share on X with a pre-filled tweet."
     2. **Reddit** — "Share as a Reddit text post."
     3. **LinkedIn** — "Share as a LinkedIn post."

Do NOT share automatically. Always confirm the platforms with the user first.

### Step 2: Run the Share Command

**Get share URLs for all platforms** (default):

```bash
mthds-agent share <org/repo>
```

**Get share URLs for specific platforms** (use `--platform` once per platform):

```bash
mthds-agent share <org/repo> --platform x
mthds-agent share <org/repo> --platform x --platform linkedin
mthds-agent share <org/repo> --platform reddit --platform linkedin
```

**Share a specific method from a multi-method package**:

```bash
mthds-agent share <org/repo> --method <name> --platform x
```

**Share from a local directory**:

```bash
mthds-agent share --local <path> --platform x --platform reddit
```

| Flag | Required | Values | Description |
|------|----------|--------|-------------|
| `[address]` | Yes* | `org/repo` | GitHub repo address |
| `--local <path>` | Yes* | directory path | Share from a local directory |
| `--method <name>` | No | method name | Share only one method from a multi-method package |
| `--platform <name>` | No | `x`, `reddit`, `linkedin` | Platform to share on. Repeat for multiple. Defaults to all |

*One of `address` or `--local` is required.

### Step 3: Parse the Output

On success, the CLI returns JSON:

```json
{
  "success": true,
  "methods": ["method-name"],
  "address": "org/repo",
  "share_urls": {
    "x": "https://twitter.com/intent/tweet?text=...",
    "reddit": "https://www.reddit.com/submit?type=TEXT&title=...&text=...",
    "linkedin": "https://www.linkedin.com/feed/?shareActive=true&text=..."
  }
}
```

Only the platforms requested via `--platform` will appear in `share_urls`. If no `--platform` is specified, all three are returned.

### Step 4: Open in Browser

After getting the URLs, open each one in the user's browser. Use the platform-appropriate command:

```bash
open "<url>"       # macOS
xdg-open "<url>"   # Linux
start "<url>"      # Windows
```

Tell the user which browser tabs were opened.

### Step 5: Handle Errors

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid platform` | `--platform` value is not `x`, `reddit`, or `linkedin` | Use valid platform names |
| `Failed to resolve methods` | GitHub repo not found or no methods in repo | Verify the address |
| `Method "X" not found` | `--method` filter doesn't match any method | Check available method names |

For all error types and recovery strategies, see [Error Handling Reference](../shared/error-handling.md).

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
