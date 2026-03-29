---
name: mthds-pipelex-setup
min_mthds_version: 0.2.1
description: Set up Pipelex inference configuration — choose backends and configure API keys. Use when user says "set up pipelex", "configure backends", "configure inference", "set up API keys", "pipelex setup", "pipelex init", wants to run methods for the first time, or gets a config/credential error when running.
---

# Set Up Pipelex Inference Configuration

Guided setup for configuring the Pipelex runtime with inference backends and API keys. This is only needed to **run** methods with live inference — building, validating, editing, and dry-running work without any configuration.

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


### Step 1 — Assess Current State

The preamble (Step 0) already verifies mthds-agent and its managed binaries (including
pipelex-agent) are present and up to date. This step checks Pipelex configuration health.

Run `mthds-agent doctor` (outputs markdown) to check the current configuration health.

- **If healthy** (backends configured, credentials valid): Tell the user their setup is already complete. Suggest trying `/mthds-run` on a method.
- **If issues found**: Show the doctor output and proceed to Step 2 to fix them.

### Step 2 — Choose Backends

Ask the user which backends they want to configure. Two paths:

#### Option A — Pipelex Gateway (simplest)

The Pipelex Gateway provides access to multiple AI models through a single API key.

1. Ask the user: "Do you accept the Pipelex Gateway Terms of Service and Privacy Policy? See: https://www.pipelex.com/privacy-policy"
2. If they accept: run `mthds-agent login` to log in to Pipelex and configure the `PIPELEX_GATEWAY_API_KEY`. This command handles authentication and key setup automatically.
3. If they decline: proceed with Option B instead

#### Option B — Bring Your Own Key (BYOK)

The user provides their own API keys for individual providers.

1. Ask which providers they want to enable. Common options: `openai`, `anthropic`. Run `mthds-agent init --help` to discover all available backends.
2. If 2+ backends are selected, ask which should be the `primary_backend`.

### Step 3 — Telemetry Preference

Ask the user: "Do you want anonymous telemetry enabled?"

- `"off"` — no telemetry
- `"anonymous"` — anonymous usage data

### Step 4 — Apply Configuration

**You MUST have all answers from Steps 2-3 before running this command.**

Build the JSON config and run:

```bash
# Example: Pipelex Gateway (user accepted terms):
mthds-agent init -g --config '{"backends": ["pipelex_gateway"], "accept_gateway_terms": true, "telemetry_mode": "anonymous"}'

# Example: BYOK with OpenAI only:
mthds-agent init -g --config '{"backends": ["openai"], "telemetry_mode": "off"}'

# Example: BYOK with multiple backends:
mthds-agent init -g --config '{"backends": ["openai", "anthropic"], "primary_backend": "anthropic", "telemetry_mode": "off"}'
```

- `-g` targets the global `~/.pipelex/` directory. Without it, targets project-level `.pipelex/` (requires a project root).
- Config JSON schema: `{"backends": list[str], "primary_backend": str, "accept_gateway_terms": bool, "telemetry_mode": str}`. All fields optional.
- When `pipelex_gateway` is in backends, `accept_gateway_terms` must be set.
- When 2+ backends are selected without `pipelex_gateway`, `primary_backend` is required.

### Step 5 — Set API Keys (BYOK only)

If the user chose BYOK (Option B), guide them to set environment variables for their chosen backends:

- **OpenAI**: `export OPENAI_API_KEY="sk-..."`
- **Anthropic**: `export ANTHROPIC_API_KEY="sk-ant-..."`

Recommend adding these to their shell profile (`~/.zshrc`, `~/.bashrc`, etc.) for persistence.

After the user confirms they've set the keys, run `mthds-agent doctor` again (outputs markdown) to verify everything is healthy.

### Step 6 — Confirm Success

Once the doctor reports a healthy configuration:

1. Confirm the setup is complete
2. Suggest trying `/mthds-run` on a method to test the configuration

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
