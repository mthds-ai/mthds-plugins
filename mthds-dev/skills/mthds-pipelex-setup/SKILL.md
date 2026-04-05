---
name: mthds-pipelex-setup
description: Set up Pipelex inference configuration — choose backends and configure API keys. Use when user says "set up pipelex", "configure backends", "configure inference", "set up API keys", "pipelex setup", "pipelex init", wants to run methods for the first time, or gets a config/credential error when running.
min_mthds_version: 0.3.3
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Set Up Pipelex Inference Configuration

> **First-time setup?** If this is your first time configuring inference (you saw an `InferenceSetupRequiredError`), use `/mthds-runner-setup` instead — it provides a friendlier onboarding experience. This skill is for reconfiguration and advanced setup.

Guided setup for configuring the Pipelex runtime with inference backends and API keys. This is only needed to **run** methods with live inference — building, validating, editing, and dry-running work without any configuration.

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
> npm install -g /build-src/mthds-js/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_VERSION_UNKNOWN` → STOP. The installed `mthds-agent` returned an unparseable version. Tell the user:

> Could not parse the output of `mthds-agent --version`. Your installation may be corrupt. Reinstall with:
>
> ```
> npm install -g /build-src/mthds-js/
> ```
>
> Then re-run this skill.

- `MTHDS_AGENT_OUTDATED <installed> <required>` → The installed `mthds-agent` is too old for this plugin. **Do not hard-stop.** Instead, tell the user their mthds-agent (v\<installed>) is older than the required v\<required>, then follow the [upgrade flow](../shared/upgrade-flow.md) to offer upgrading mthds-agent via `npm install -g /build-src/mthds-js/`. After the upgrade flow completes (whether the user upgraded or declined), proceed to Step 1. The upgrade flow's "Not now" and "Never ask" options let users continue with current versions.

- `MTHDS_UPDATE_CHECK_FAILED ...` → WARN. The update check command failed. Show the error output to the user. Suggest checking network connectivity and `mthds-agent` installation. Proceed to Step 1 with current versions.

- `UPGRADE_AVAILABLE ...` → Read [upgrade flow](../shared/upgrade-flow.md) and follow the upgrade prompts before continuing to Step 1.

- `JUST_UPGRADED ...` → Announce what was upgraded to the user, then continue to Step 1.

- `MTHDS_ENV_CHECK_MISSING` → WARN. The env-check script was not found at either expected path. Tell the user the environment check could not run, but proceed to Step 1.

- No output or `UP_TO_DATE` → Proceed to Step 1.

- Any other output → WARN. The preamble produced unexpected output. Show it to the user verbatim. Proceed to Step 1 cautiously.


### Step 1 — Assess Current State

The preamble (Step 0) already verifies mthds-agent and its managed binaries (including
pipelex-agent) are present and up to date. This step checks Pipelex configuration health.

Run `mthds-agent doctor` (outputs markdown) to check the current configuration health.

- **If healthy** (backends configured, credentials valid): Tell the user their setup is already complete. Suggest trying `/mthds-run` on a method.
- **If issues found**: Show the doctor output and proceed to Step 2 to fix them.

### Step 2 — Choose Backends

Use AskUserQuestion to present the backend choice:

- **Question**: "Which backend would you like to configure?"
- **Header**: "Backend"
- **Options**:
  1. **Pipelex Gateway (Recommended)** — "One API key for all AI models through a single gateway."
  2. **Bring Your Own Key (BYOK)** — "Use your own API keys from providers like OpenAI or Anthropic."

#### Option A — Pipelex Gateway (simplest)

The Pipelex Gateway provides access to multiple AI models through a single API key.

1. Use AskUserQuestion to ask about terms acceptance:
   - **Question**: "Do you accept the Pipelex Gateway Terms of Service and Privacy Policy? See: https://www.pipelex.com/privacy-policy"
   - **Header**: "Terms"
   - **Options**:
     1. **Accept** — "I accept the Terms of Service and Privacy Policy."
     2. **Decline** — "I'd rather use my own API keys (BYOK) instead."
2. If they accept: run `mthds-agent login` to log in to Pipelex and configure the `PIPELEX_GATEWAY_API_KEY`. This command handles authentication and key setup automatically.
3. If they decline: proceed with Option B instead

#### Option B — Bring Your Own Key (BYOK)

The user provides their own API keys for individual providers.

1. Ask which providers they want to enable. Common options: `openai`, `anthropic`. Run `mthds-agent init --help` to discover all available backends.
2. If 2+ backends are selected, ask which should be the `primary_backend`.

### Step 3 — Apply Configuration

**You MUST have all answers from Step 2 before running this command.**

Build the JSON config and run:

```bash
# Example: Pipelex Gateway (user accepted terms):
mthds-agent init -g --config '{"backends": ["pipelex_gateway"], "accept_gateway_terms": true}'

# Example: BYOK with OpenAI only:
mthds-agent init -g --config '{"backends": ["openai"]}'

# Example: BYOK with multiple backends:
mthds-agent init -g --config '{"backends": ["openai", "anthropic"], "primary_backend": "anthropic"}'
```

- `-g` targets the global `~/.pipelex/` directory. Without it, targets project-level `.pipelex/` (requires a project root).
- Config JSON schema: `{"backends": list[str], "primary_backend": str, "accept_gateway_terms": bool}`. All fields optional.
- When `pipelex_gateway` is in backends, `accept_gateway_terms` must be set.
- When 2+ backends are selected without `pipelex_gateway`, `primary_backend` is required.

### Step 4 — Set API Keys (BYOK only)

If the user chose BYOK (Option B), guide them to set environment variables for their chosen backends:

- **OpenAI**: `export OPENAI_API_KEY="sk-..."`
- **Anthropic**: `export ANTHROPIC_API_KEY="sk-ant-..."`

Recommend adding these to their shell profile (`~/.zshrc`, `~/.bashrc`, etc.) for persistence.

After the user confirms they've set the keys, run `mthds-agent doctor` again (outputs markdown) to verify everything is healthy.

### Step 5 — Confirm Success

Once the doctor reports a healthy configuration:

1. Confirm the setup is complete
2. Suggest trying `/mthds-run` on a method to test the configuration

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
