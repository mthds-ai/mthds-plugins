---
name: mthds-runner-setup
description: Set up or reconfigure how methods reach AI models, with the user's own provider API keys or with a Pipelex API key on the hosted Pipelex API. Use when a live run fails because Pipelex was never initialised (the error says config files are missing) or because a provider API key is missing (the error says it could not get credentials for an inference backend), when the runner has no API key, when the user wants to set up inference for the first time, says "set up pipelex", "configure backends", "configure inference", "set up API keys", "pipelex setup", "pipelex init", "use the hosted API", or gets a config/credential error when running. Guides through bringing your own provider keys (OpenAI recommended) or running on the hosted Pipelex API.
min_mthds_version: 0.30.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Inference Setup

You've built a method — now let's run it. Before a live inference run, the method needs a way to reach AI models, and there are two:

- **Your own provider keys**: the method runs on this machine with the local Pipelex runner, which calls each AI provider with the user's own API key.
- **The hosted Pipelex API**: the method runs on the hosted Pipelex API with a Pipelex API key, and this machine holds no provider key at all.

Building, validating, editing, explaining and dry-running need neither. This is a one-time setup, and running this skill again switches from one to the other.

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
[ -n "$_best_f" ] && exec "$_best_f" "0.30.0"
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


### Step 1 — Present Options

Use AskUserQuestion to present the inference setup choice:

- **Question**: "How would you like your methods to reach AI models?"
- **Header**: "Setup"
- **Options**:
  1. **Your own provider keys** — "Run methods on this machine with your own API keys from providers such as OpenAI. One OpenAI key runs the default models."
  2. **Hosted Pipelex API** — "Run methods on the hosted Pipelex API with a Pipelex API key. No provider keys needed."

Wait for the user's choice before proceeding.

### Step 2A — Your Own Provider Keys

#### 1. Install the local runner and make it the default

Methods that use the user's own keys run on the pipelex runner, and `mthds-agent init` is a command of that runner only. Install it (this does nothing when it is already installed) and make it the default:

```bash
mthds-agent runner setup pipelex
mthds-agent config set runner pipelex
```

#### 2. Choose the backends

Recommend **OpenAI** as the one key to start with: the default models of Pipelex's model deck are OpenAI models, so an OpenAI key alone runs the default language and image models. Among the backends below, only `openai` serves those defaults, so keep it in the list.

Other backends the user may enable beside it, each with its own key:

| Backend | Key variable | Notes |
|---------|--------------|-------|
| `openai` | `OPENAI_API_KEY` | Recommended: serves the default language and image models |
| `anthropic` | `ANTHROPIC_API_KEY` | |
| `mistral` | `MISTRAL_API_KEY` | Also serves the default OCR, which a method extracting text from images or scanned documents needs |
| `google` | `GOOGLE_API_KEY` | |
| `openrouter` | `OPENROUTER_API_KEY` | One key for models from many providers |

Ask which backends they want to enable, offering OpenAI alone as the default answer.

#### 3. Run init

```bash
# OpenAI alone (recommended):
mthds-agent init -g --config '{"backends": ["openai"]}'

# Several backends, OpenAI tried first:
mthds-agent init -g --config '{"backends": ["openai", "anthropic", "mistral"], "primary_backend": "openai"}'
```

With one backend named, `init` routes to that backend every model it supports. With two or more, `primary_backend` names the one tried first and is required. `-g` writes the global `~/.pipelex/` configuration, used in every project; without it, `init` targets a project-level `.pipelex/`.

#### 4. Add the keys

`init` does not write the keys. Ask the user to add each enabled backend's key themselves, so the key stays out of this conversation, in one of these ways:

- Add a line per key to `~/.pipelex/.env`, such as `OPENAI_API_KEY=sk-...`
- Export the variables in their shell profile (`~/.zshrc`, `~/.bashrc`)
- Run `pipelex init credentials` in their own terminal (not through Claude Code): it prompts for the missing key of each enabled backend and saves it to `~/.pipelex/.env`

Wait for the user to confirm the keys are in place.

#### 5. Verify

```bash
mthds-agent doctor
```

The doctor checks the toolchain and that the runner is `pipelex`, but it does not read provider keys. To check the keys, the user can run `pipelex doctor` in their own terminal, which reports the credentials of each enabled backend. Otherwise the first live run checks them: a missing key fails with an error saying it could not get credentials for an inference backend, naming the variable to set.

### Step 2B — Hosted Pipelex API

#### 1. Get a Pipelex API key

The user needs a Pipelex API key. If they do not have one yet, they create one in their console at [app.pipelex.com](https://app.pipelex.com).

#### 2. Save the key

Ask the user to run this in their own terminal (not through Claude Code), so the key stays out of this conversation:

```
mthds runner setup api
```

It asks for the API base URL, then for the API key with masked input, saves both to `~/.mthds/config`, and offers to make `api` the default runner. Tell the user the base URL for the hosted API is `https://api.pipelex.com`: when a custom URL was configured before, such as a self-hosted runner, the prompt is pre-filled with that one and keeping it would send the hosted key there.

If the user would rather hand the key to you, save it with the hosted base URL named explicitly, since without `--base-url` the command keeps whatever base URL is already configured:

```bash
mthds-agent runner setup api --base-url https://api.pipelex.com --api-key <their-api-key>
```

Wait for the user to confirm the key is saved.

#### 3. Make the API runner the default

```bash
mthds-agent config set runner api
```

#### 4. Verify

```bash
mthds-agent doctor
```

The configuration should show `runner` set to `api`, `base-url` set to `https://api.pipelex.com` and `api-key` configured; the doctor warns when the runner is `api` and no API key is configured, but it does not check which base URL is set. If `base-url` names another host, set it with `mthds-agent config set base-url https://api.pipelex.com`.

### Step 3 — Success

Once the setup is verified:

> Your inference setup is complete! You can now run your methods with live AI inference.

Then re-run the method that originally triggered this setup (if known), or suggest `/mthds-run`.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
