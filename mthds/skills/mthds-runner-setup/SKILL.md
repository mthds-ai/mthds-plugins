---
name: mthds-runner-setup
description: Set up or reconfigure inference backends and API keys. Use when user gets InferenceSetupRequiredError, wants to set up inference for the first time, says "set up pipelex", "configure backends", "configure inference", "set up API keys", "pipelex setup", "pipelex init", or gets a config/credential error when running. Guides through Pipelex Gateway (recommended) or Bring Your Own Key setup.
min_mthds_version: 0.3.4
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# First-Run Inference Setup

You've built a method — now let's run it. Before your first live inference run, you need to configure how Pipelex connects to AI models. This is a one-time setup.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.claude/plugins/marketplaces/mthds-plugins/bin/mthds-env-check "0.3.4" 2>/dev/null || ../mthds-plugins/bin/mthds-env-check "0.3.4" 2>/dev/null || echo "MTHDS_ENV_CHECK_MISSING"
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


### Step 1 — Present Options

Use AskUserQuestion to present the inference setup choice:

- **Question**: "How would you like to connect to AI models?"
- **Header**: "Setup"
- **Options**:
  1. **Pipelex Gateway (Recommended)** — "One API key for all AI models — LLMs, OCR, document extraction, image generation. Free credits to get started."
  2. **Bring Your Own Key (BYOK)** — "Use your own API keys from providers like OpenAI or Anthropic."

Wait for the user's choice before proceeding.

### Step 2A — Pipelex Gateway Path

#### 1. Terms acceptance

Tell the user about the terms, then use AskUserQuestion to get their decision:

> To use the Pipelex Gateway, you need to accept the Terms of Service and Privacy Policy.
> Review the terms here: https://www.pipelex.com/privacy-policy
>
> By using Pipelex Gateway, anonymous telemetry is enabled to monitor service quality. We only collect technical data (model names, token counts, latency) — never your prompts, completions, or business data.

- **Question**: "Do you accept the Pipelex Gateway Terms of Service and Privacy Policy?"
- **Header**: "Terms"
- **Options**:
  1. **Accept** — "I accept the Terms of Service and Privacy Policy."
  2. **Decline** — "I'd rather use my own API keys (BYOK) instead."

- **If they accept**: proceed to the next step.
- **If they decline**: switch to Step 2B (BYOK) instead.

#### 2. Record acceptance

Run:

```bash
mthds-agent accept-gateway-terms
```

This records the acceptance and marks inference setup as complete.

#### 3. Get API key

Tell the user:

> Now you need a Pipelex Gateway API key. Run this command in the prompt below:
>
> ```
> ! mthds login
> ```
>
> This will open your browser to create an account (or log in) and automatically save the API key.

Wait for the user to confirm login is complete.

#### 4. Configure backends

Run:

```bash
mthds-agent init -g --config '{"backends": ["pipelex_gateway"]}'
```

Note: `accept_gateway_terms` is not needed here — it was already recorded by `accept-gateway-terms` in the previous step.

#### 5. Verify

Run:

```bash
mthds-agent doctor
```

If healthy, proceed to Step 3. If the API key is missing, remind the user to run `! mthds login` again.

### Step 2B — BYOK Path

#### 1. Guide API key setup

Tell the user to set up their API keys. Common providers:

- **OpenAI**: Add `OPENAI_API_KEY=sk-...` to `~/.pipelex/.env`
- **Anthropic**: Add `ANTHROPIC_API_KEY=sk-ant-...` to `~/.pipelex/.env`

They can also export them in their shell profile (`~/.zshrc`, `~/.bashrc`).

#### 2. Ask which providers they've configured

Ask which backends to enable.

#### 3. Run init

```bash
# Single backend example:
mthds-agent init -g --config '{"backends": ["openai"]}'

# Multiple backends example:
mthds-agent init -g --config '{"backends": ["openai", "anthropic"], "primary_backend": "anthropic"}'
```

When `pipelex_gateway` is not among the backends, `accept_gateway_terms` is not needed.
When 2+ backends are selected without `pipelex_gateway`, `primary_backend` is required.

#### 4. Configure credentials

Guide the user to add their API keys to `~/.pipelex/.env`:

- **OpenAI**: `OPENAI_API_KEY=sk-...`
- **Anthropic**: `ANTHROPIC_API_KEY=sk-ant-...`

If the user prefers an interactive setup, tell them to run `pipelex init inference` in their own terminal (not through Claude Code).

#### 5. Verify

Run `mthds-agent doctor` to confirm keys are valid and configuration is healthy.

### Step 3 — Success

Once the doctor reports healthy:

> Your inference setup is complete! You can now run your methods with live AI inference.

Then re-run the method that originally triggered this setup (if known), or suggest `/mthds-run`.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
