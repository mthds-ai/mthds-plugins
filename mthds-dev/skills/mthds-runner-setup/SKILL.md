---
name: mthds-runner-setup
description: Set up or reconfigure how methods reach AI models, with the user's own provider API keys or with a Pipelex API key on the hosted Pipelex API. Use when a live run fails because Pipelex was never initialised (the error says config files are missing) or because a provider API key is missing (the error says it could not get credentials for an inference backend), when the hosted Pipelex API refuses a run's Pipelex API key, when the runner is set to `api`, which cannot run a bundle, when the user wants to set up inference for the first time, says "set up pipelex", "configure backends", "configure inference", "set up API keys", "pipelex setup", "pipelex init", "pipelex login", "use the hosted API", or gets a config/credential error when running. Guides through bringing your own provider keys (OpenAI recommended) or running on the hosted Pipelex API.
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

You've built a method — now let's run it. Before a live inference run, the method needs a way to reach AI models, and there are two. Both go through the pipelex runner, which executes a run either on this machine or on the hosted Pipelex API:

- **Your own provider keys**: the method runs on this machine, and pipelex calls each AI provider with the user's own API key.
- **The hosted Pipelex API**: pipelex sends the method and its inputs to the hosted Pipelex API with a Pipelex API key, and this machine holds no provider key at all.

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

#### 1. Install the pipelex runner and make it the default

Methods that use the user's own keys run on the pipelex runner, and `mthds-agent init` is a command of that runner only. Install it (this does nothing when it is already installed) and make it the default:

```bash
mthds-agent runner setup pipelex
mthds-agent config set runner pipelex
```

#### 2. Choose the backends

Recommend **OpenAI** as the one key to start with: the default models of Pipelex's model deck are OpenAI models, so an OpenAI key alone runs the default language and image models. Among the backends below, only `openai` serves those defaults, so keep it in the list whenever the method's language or image pipes use the default models.

Other backends the user may enable beside it, each with its own key:

| Backend | Key variable | Notes |
|---------|--------------|-------|
| `openai` | `OPENAI_API_KEY` | Recommended: serves the default language and image models |
| `anthropic` | `ANTHROPIC_API_KEY` | |
| `mistral` | `MISTRAL_API_KEY` | Also serves the default OCR, which a method extracting text from images or scanned documents needs |
| `google` | `GOOGLE_API_KEY` | |
| `openrouter` | `OPENROUTER_API_KEY` | One key for models from many providers |

Ask which backends they want to enable, offering OpenAI alone as the default answer. When this skill started from a failed run whose error names a key variable, such as `MISTRAL_API_KEY`, propose the backend that reads that variable instead, adding `openai` only when the method also uses the default language or image models.

#### 3. Run init

`init` resets the configuration files it writes, the backends, the routing profiles and the model deck, to Pipelex's templates, discarding any edits made to them. So first check whether a configuration already exists:

```bash
ls "${PIPELEX_HOME:-$HOME/.pipelex}/inference/backends.toml" .pipelex/inference/backends.toml 2>/dev/null
```

When one does, read what it sets up before deciding anything. `mthds-agent doctor` does not read the Pipelex configuration, so this is a direct call to `pipelex-agent`, a read-only report that never prints a key:

```bash
pipelex-agent doctor
```

Its `Execution` line says where runs execute, and its `Backend Credentials` section lists each enabled backend with the key variables it is missing. Skip `init` and go to step 4 only when both of these hold:

- Runs execute on this machine: the `Execution` line says `local`, or is absent, as it is on a pipelex release older than 0.79.0, which runs everything on this machine.
- The enabled backends are the ones the user chose.

Then only the keys need adding. Otherwise `init` is needed: for a configuration whose `Execution` is `hosted`, which would keep sending runs to the hosted API, and for one that enables other backends, such as the configuration `pipelex init config` writes, which enables nearly every backend and would need a key for each. Tell the user that `init` resets those files, and run it only after their yes. If they decline, leave the configuration as it is and say what that means: runs keep executing where the `Execution` line says, and a run on this machine needs the key of every backend listed.

```bash
# OpenAI alone (recommended):
mthds-agent init -g --config '{"backends": ["openai"]}'

# Several backends, OpenAI tried first:
mthds-agent init -g --config '{"backends": ["openai", "anthropic", "mistral"], "primary_backend": "openai"}'
```

With one backend named, `init` routes to that backend every model it supports. With two or more, `primary_backend` names the one tried first and is required. Without an `execution` field, `init` sets runs to execute on this machine. `-g` writes the global configuration, used in every project, in the home configuration directory: the directory `PIPELEX_HOME` names when that variable is set and not empty, else `~/.pipelex/`. Without it, `init` targets a project-level `.pipelex/`.

Inside a project with its own `.pipelex/pipelex.toml`, that file takes precedence over the global one. When it sets `execution = "hosted"` in its `[run]` table, a global `init` leaves runs in that project going to the hosted API, and `pipelex-agent doctor` still reports `Execution` as `hosted`. Tell the user, then set it to `local` in the project file with your file tools, which changes nothing else in it; a user who wants the project to stay hosted can instead pass `--local` on each run they want on this machine.

#### 4. Add the keys

`init` does not write the keys. Ask the user to add each enabled backend's key themselves, so the key stays out of this conversation, in one of these ways:

- Add a line per key to the home `.env`, `~/.pipelex/.env` (or the `.env` in `PIPELEX_HOME` when that variable is set), such as `OPENAI_API_KEY=sk-...`
- Export the variables in their shell profile (`~/.zshrc`, `~/.bashrc`)
- Run `pipelex init credentials` in their own terminal (not through Claude Code): it prompts for the missing key of each enabled backend and saves it to `~/.pipelex/.env`

Wait for the user to confirm the keys are in place.

#### 5. Verify

```bash
mthds-agent doctor
pipelex-agent doctor
```

`mthds-agent doctor` checks the toolchain and that the runner is `pipelex`. `pipelex-agent doctor` should show `Execution` set to `local` (on pipelex 0.79.0 or later) and every enabled backend under `Backend Credentials` with its credentials valid; the user can run `pipelex doctor` in their own terminal for the same report. It checks that each key variable is set, without printing the key or testing it with the provider, so the first live run is what proves a key works.

### Step 2B — Hosted Pipelex API

The hosted route runs on the same pipelex runner as the own-keys route: pipelex sends each run to the hosted Pipelex API instead of executing it here. It needs pipelex 0.79.0 or later, the first release with hosted runs and `pipelex login`. The API runner that `mthds-agent runner setup api` configures is not this route: it cannot run a bundle, and `mthds-agent run bundle` fails on it as an unknown command.

#### 1. Install pipelex 0.79.0 or later and make the pipelex runner the default

```bash
mthds-agent runner setup pipelex
mthds-agent config set runner pipelex
mthds-agent doctor
```

Read the `pipelex` version in the doctor's `Dependencies` table. Its `ok` status only says that pipelex meets `mthds-agent`'s own minimum, which may be older than 0.79.0, and neither `mthds-agent runner setup pipelex` nor `mthds-agent upgrade` moves a release that meets that minimum. If the version is below 0.79.0, upgrade pipelex, then run `mthds-agent doctor` again and check that the version is now 0.79.0 or later:

```bash
uv tool install --upgrade /workspace/pipelex/
```

#### 2. Get a Pipelex API key

First check which hosted API the key would go to. `pipelex login` checks the key with the API at the origin `PIPELEX_BASE_URL` names, else `https://api.pipelex.com`, and every hosted run goes to that same origin. A `.env` that pipelex loads, the home one or the one in the directory you run methods from, sets it over the shell. A base URL is not a secret, so the first command prints it; the second prints a fixed message for each `.env` that sets it, never a line of the file:

```bash
printenv PIPELEX_BASE_URL
for env_file in "${PIPELEX_HOME:-$HOME/.pipelex}/.env" .env; do grep -qE '^[[:space:]]*(export[[:space:]]+)?PIPELEX_BASE_URL[[:space:]]*=' "$env_file" 2>/dev/null && echo "$env_file sets PIPELEX_BASE_URL"; done
```

When `printenv` prints a URL other than `https://api.pipelex.com`, or a `.env` sets the variable, which a former self-hosted or staging setup may have left, tell the user that the login's key check and every hosted run would go to that origin, and ask them to unset it in their shell and its profile, or to remove the line from that `.env`, before they log in. A `.env` line they confirm says `https://api.pipelex.com` can stay.

Then ask the user to run this in their own terminal (not through Claude Code), so the key stays out of this conversation:

```
pipelex login
```

It opens the Pipelex app in their browser, where they sign in or create an account, and the app hands a new key back to the command. On a machine with no browser, `pipelex login --paste` asks instead for a key the user creates in the Pipelex app at [app.pipelex.com](https://app.pipelex.com). Either way the command checks the key with the hosted API, saves it as `PIPELEX_API_KEY` in `~/.pipelex/.env` (in the `.env` of `PIPELEX_HOME` when that variable is set), and never prints it. Never ask for the key in this conversation.

A user who already exports a Pipelex API key as `PIPELEX_API_KEY` in their shell can skip this step, provided no `.env` file sets another one: pipelex reads `~/.pipelex/.env`, then a `.env` in the current directory, over the shell.

Wait for the user to confirm the key is saved. Then check that no `.env` in the directory you run methods from shadows it: pipelex loads that file after `~/.pipelex/.env`, so a `PIPELEX_API_KEY` line there, an empty or old key included, is what every run sends. This check prints a fixed message, never the value:

```bash
grep -qE '^[[:space:]]*(export[[:space:]]+)?PIPELEX_API_KEY[[:space:]]*=' .env 2>/dev/null && echo ".env sets PIPELEX_API_KEY"
```

When it reports the line, never read or print that file's value: ask the user to look at it themselves and, unless it already holds their new key, to remove the line or replace its value. `pipelex login` gives the same warning when the user runs it from that directory.

#### 3. Send runs to the hosted API

Like the own-keys route, `init` resets the configuration files it writes to Pipelex's templates. So first check whether the home configuration directory already holds one:

```bash
ls "${PIPELEX_HOME:-$HOME/.pipelex}/pipelex.toml" 2>/dev/null
```

When it finds one, tell the user and run `init` only after their yes. If they would rather keep their files, for instance to keep a working own-keys setup for `--local` runs, set `execution = "hosted"` in the `[run]` table of the file `ls` listed, at the path it printed, with your file tools instead, adding the table when it is missing: that changes nothing else.

Make the hosted API where runs execute by default:

```bash
mthds-agent init -g --config '{"execution": "hosted"}'
```

This writes `execution = "hosted"` in the `[run]` table of `pipelex.toml` in the home configuration directory, which is the directory `PIPELEX_HOME` names when that variable is set and not empty, else `~/.pipelex`, so every run goes to the hosted API unless it passes `--local`, and its report says whether a Pipelex API key is set. A hosted setup configures no backend, so `init` refuses `backends` and `primary_backend` beside `"execution": "hosted"`.

Inside a project with its own `.pipelex/pipelex.toml`, that file takes precedence over the global one, and the one a project-level `init` writes says `execution = "local"`: set it to `hosted` there too when the user works in such a project.

To keep runs on this machine by default and send only some of them to the hosted API, skip this step and pass `--hosted` on those runs, such as `mthds-agent run bundle <bundle-dir>/ --hosted`. Write `--hosted` and `--local`, never `--runner hosted` or `--runner local`: `mthds-agent` reads `--runner` as its own option, which names its runner, `pipelex` or `api`, and refuses any other value.

#### 4. Verify

`mthds-agent doctor` does not read the Pipelex configuration, so this is a direct call to `pipelex-agent`, a read-only report that never prints a key:

```bash
pipelex-agent doctor
```

The report should show `Execution` set to `hosted` and a healthy `Pipelex API Key` section; the user can run `pipelex doctor` in their own terminal for the same report. When it says no Pipelex API key is set, the user has not finished `pipelex login`: ask them to run it. The doctor checks only that a key is set and looks like a Pipelex API key (`plx_sk_…`); the hosted API checks the key itself at the first run, and refuses a rejected one with a 401 or a 403 whose hint says to run `pipelex login`. A 403 whose message names something the request may not do, rather than the key, is not a key problem, and a new key does not fix it. When runs stay local by default and `--hosted` is passed per run, the report shows `local` and no key section, and the first hosted run is the check.

### Step 3 — Success

Once the setup is verified:

> Your inference setup is complete! You can now run your methods with live AI inference.

Then re-run the method that originally triggered this setup (if known), or suggest `/mthds-run`.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
