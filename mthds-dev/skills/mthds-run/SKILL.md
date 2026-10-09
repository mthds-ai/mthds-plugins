---
name: mthds-run
description: Run MTHDS methods and interpret results, on this machine or on the hosted Pipelex API. Use when user says "run this pipeline", "execute the workflow", "execute the method", "test this .mthds file", "try it out", "see the output", "dry run", "run it on the hosted API", or wants to execute any MTHDS method bundle and see its output.
min_mthds_version: 0.30.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Run MTHDS methods

Execute MTHDS method bundles, on this machine or on the hosted Pipelex API, and interpret their output.

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


Until the environment check passes, write no `.mthds` file and do no other work: the CLI is required for validation, formatting and execution, and without it the output will be broken.

### Step 1 — Pipelex Runtime Check (mandatory)

Running methods requires the Pipelex runtime to be installed and configured.
The preamble (Step 0) already verifies mthds-agent and its managed binaries are present
and up to date. This step checks the runner.

```bash
mthds-agent doctor  # outputs markdown
```

- **If the doctor shows the runner set to `api`**: STOP, for a live run and a dry run alike. The API runner cannot run a bundle: `mthds-agent run bundle` fails on it as an unknown command. Tell the user:

> Methods run through the pipelex runner, on this machine or on the hosted Pipelex API, and this machine is set to the API runner. Use `/mthds-runner-setup` to switch.

- **On the pipelex runner**, the doctor reads neither the provider keys nor where runs execute, so a missing key surfaces at the first live run instead, which Step 6 handles: a provider key on a run that executes on this machine, a Pipelex API key on a run that executes on the hosted Pipelex API. Any other issue the doctor reports, such as a missing or outdated binary, names its own fix: apply that fix rather than sending the user to `/mthds-runner-setup`.

- **If the user is requesting a dry run** (`--dry-run`): config issues are OK — a dry run executes on this machine and needs no backend configuration. Proceed. On a machine whose runs execute on the hosted Pipelex API by default, the dry run is refused with an error saying that `--dry-run` only applies to a run on this machine: add `--local` and run it again. Never write `--runner local`, which `mthds-agent` reads as its own option and refuses.

- **If healthy**: proceed to Step 2.

### Step 2: Identify the Target

| Target | Command |
|--------|---------|
| Pipeline directory (recommended) | `mthds-agent run bundle <bundle-dir>/` |
| Specific pipe in a directory | `mthds-agent run bundle <bundle-dir>/ --pipe my_pipe` |
| Bundle file directly | `mthds-agent run bundle bundle.mthds -L <bundle-dir>/` |
| Pipe by code from library | `mthds-agent run pipe my_pipe -L <library-dir>/` |
| Published method, by its address | `mthds-agent run method github.com/owner/repo[/name][@tag]` |
| Method saved on the Pipelex platform, by its catalog id (hosted API only) | `mthds-agent run method mt_abc123 --hosted` |

> **Directory mode** (recommended): Pass the pipeline directory as target. The CLI auto-detects `bundle.mthds`, `inputs.json`, and sets `-L` automatically — no need to specify them explicitly. This also avoids namespace collisions with other bundles.

> **Methods named by address or catalog id**: a run on the hosted Pipelex API resolves a published address or a catalog id there, and the catalog id works only there; it needs pipelex 0.79.0 or later. A run on this machine fetches a published method and reads a relative `--inputs` path from the fetched package's directory rather than from the working directory, so pass the inputs inline or as an absolute path.

### Step 3: Prepare Inputs and Check Readiness

#### Fast path — inputs just prepared

If inputs were already prepared during this conversation — via `/mthds-inputs` (user-data, synthetic, or mixed strategy), or by manually assembling `inputs.json` with real values earlier in this session — skip the schema fetch and readiness check. The inputs are ready. Proceed directly to Step 4 with a normal run.

This applies when you just wrote or saw `inputs.json` being written with real content values. It does NOT apply after `/mthds-design`, which saves no inputs, or after `/mthds-inputs` with the template strategy.

#### Full check — cold start

If `/mthds-run` is invoked without prior input preparation in this session, perform the full readiness check:

Get the input schema for the target:

```bash
mthds-agent inputs bundle bundle.mthds --explicit
```

**Output:**
```json
{
  "success": true,
  "pipe_ref": "doc_processing.process_document",
  "inputs": {
    "document": {
      "concept": "native.Document",
      "content": {"url": "https://mock.invalid/url"}
    },
    "context": {
      "concept": "native.Text",
      "content": {"text": "text_value"}
    }
  }
}
```

Fill in the `content` fields with actual values. For complex inputs, use the /mthds-inputs skill.

#### Input Readiness Check

Before running, assess whether inputs are ready. This prevents runtime failures from placeholder values.

**No inputs required**: If `mthds-agent inputs bundle <file>.mthds` returns an empty `inputs` object (`{}`), inputs are ready — skip to Step 4.

**Inputs required**: If inputs exist, check `inputs.json` for readiness:

1. Does `inputs.json` exist in the bundle directory?
2. If it exists, scan all `content` values for placeholder signals:
   - **Template defaults**: `"text_value"` or any value matching the pattern `*_value`, and any URL under `https://mock.invalid/`
   - **Angle-bracket placeholders**: values containing `<...>` (e.g. `<path-to-cv.pdf>`, `<your-text-here>`)
   - **Non-existent file paths**: `url` fields pointing to local files that don't exist on disk

**Readiness result**:
- **Ready**: `inputs.json` exists AND all content values are real (no placeholders, referenced files exist) → proceed to Step 4 with normal run
- **Not ready**: `inputs.json` is missing, OR contains any placeholder values → proceed to Step 4 with dry-run fallback

### Step 4: Choose Run Mode

#### If inputs are not ready

Default to `--dry-run --mock-inputs` and inform the user:

> "The inputs for this pipeline contain placeholder values (not real data). I'll do a dry run with mock inputs to validate the pipeline structure."

After the dry run, use AskUserQuestion to present next steps:

- **Question**: "What would you like to do next?"
- **Header**: "Next step"
- **Options**:
  1. **Prepare real inputs** — "Use /mthds-inputs to fill in actual values, then re-run."
  2. **Provide files** — "Supply file paths for document/image inputs."
  3. **Keep dry run** — "Accept the dry-run result as-is."

#### Run modes reference

| Mode | Command | Use When |
|------|---------|----------|
| **Dry run + mock inputs** | `mthds-agent run bundle <bundle-dir>/ --dry-run --mock-inputs` | Quick structural validation, no real data needed, or inputs not ready |
| **Dry run with real inputs** | `mthds-agent run bundle <bundle-dir>/ --dry-run` | Validate input shapes without making API calls (auto-detects `inputs.json`) |
| **Full run** | `mthds-agent run bundle <bundle-dir>/` | Production execution (auto-detects `inputs.json`) |
| **Full run inline** | `mthds-agent run bundle <bundle-dir>/ --inputs '{"theme": ...}'` | Quick execution with inline JSON inputs |
| **Full run without graph** | `mthds-agent run bundle <bundle-dir>/ --no-graph` | Execute without generating graph visualization |
| **Full run with memory** | `mthds-agent run bundle <bundle-dir>/ --with-memory` | When piping output to another method |
| **Hosted run** | `mthds-agent run bundle <bundle-dir>/ --hosted` | Run on the hosted Pipelex API when runs execute on this machine by default (pipelex 0.79.0 or later, with a Pipelex API key) |
| **Run on this machine** | `mthds-agent run bundle <bundle-dir>/ --local` | Run here when runs execute on the hosted Pipelex API by default, as every dry run must |

> **Graph by default**: Execution graphs (`live_run.html` / `dry_run.html`) are generated automatically on a run on this machine. Use `--no-graph` to disable.

> **Where a run executes**: the `[run] execution` setting of the Pipelex configuration decides, `local` unless `/mthds-runner-setup` set it to `hosted`, and `--hosted` or `--local` on a run overrides it. Write those two flags, never `--runner hosted` or `--runner local`: `mthds-agent` reads `--runner` as its own option and refuses those values. A pipelex older than 0.79.0 has no hosted runs and refuses both flags as unknown options: a hosted run then needs pipelex upgraded with `uv tool install --upgrade /workspace/pipelex/`, while a run on this machine needs neither flag. A hosted run sends the bundle's `.mthds` files, with those of its `-L` library directories, and uploads the local files named at document and image inputs. It sends no Python and no package manifest, so a method whose `PipeFunc` functions or structures live in Python files, or whose `METHODS.toml` declares dependencies, must run on this machine.

### Inline JSON for Inputs

The `--inputs` flag accepts both file paths and inline JSON. The CLI auto-detects: if the value starts with `{`, it is parsed as JSON directly. This is the fastest path — no file creation needed for simple inputs.

```bash
# Inline JSON
mthds-agent run bundle <bundle-dir>/ --inputs '{"theme": {"concept": "native.Text", "content": {"text": "nature"}}}'

# File path (auto-detected in directory mode)
mthds-agent run bundle <bundle-dir>/
```

### Step 5: Present Results

After a successful run, **always show the actual output to the user** — never just summarize what fields exist.

#### Output format modes

`mthds-agent run` prints Markdown by default: a `# Pipeline run complete` heading, then a `## Result` section. Pass `--format json` to get JSON on stdout instead, which a program or a piped method needs. Either way, the run has two output modes:

- **Compact (default)**: the concept's structured JSON — no envelope, no `success` wrapper. This is the primary output of the method's main concept. In Markdown it sits in a fenced `json` block under `## Result`; with `--format json` it is the whole of stdout, ready to parse.
- **With memory (`--with-memory`)**: `main_stuff` (with `json`, `markdown`, `html` renderings) + `working_memory` (all named stuffs and aliases). In Markdown, `## Result` shows the `main_stuff.markdown` rendering, followed by the output file and graph paths; with `--format json`, stdout is the whole envelope. Use this, with `--format json`, when piping output to another method.

A run on this machine writes the `output_file` and `graph_files` to disk as side effects; their paths are in the `--with-memory` output, not in compact output.

**A run on the hosted Pipelex API writes nothing to disk**: no output file and no graph. Its `main_stuff` carries the result in `json` alone, with `markdown` and `html` left empty, so the Markdown output falls back to that JSON: show `main_stuff.json`. The id of the run on the hosted API, `pipeline_run_id`, is in the `--with-memory` envelope, and in the error report of a run that failed after the hosted API accepted it; report it to the user, since it names the run on the Pipelex platform.

#### 5a. Determine what to show

**In compact mode** (default), the output is the concept JSON directly. Show the fields to the user:

```json
{
  "clauses": [...],
  "overall_risk": "high"
}
```

**In `--with-memory` mode**, the output structure depends on the pipe architecture:

```
main_stuff is always the primary output for a completed run:
    → a value, or an explicit absence document for optional outputs
```

| Pipe Type | `main_stuff` present? | What to show |
|-----------|----------------------|--------------|
| PipeLLM, PipeCompose, PipeExtract, PipeImgGen, PipeSearch | Always | `main_stuff` |
| PipeSequence | Always (last step) | `main_stuff` |
| PipeBatch | Always (list) | `main_stuff` |
| PipeCondition | Always | `main_stuff` |
| PipeParallel | Always (combined result) | `main_stuff` |

#### 5b. Show the output content

**In compact mode**: show the JSON fields directly. For structured concepts, format for readability.

**In `--with-memory` mode**:

- Show `main_stuff.markdown` directly — this is the human-readable rendering. Display it as-is so the user sees the full output. On a hosted run it is empty: show `main_stuff.json` instead.
- For structured concepts with fields, also show `main_stuff.json` formatted for readability.
- If `main_stuff` is an absence document (`absent: true`), show the absence reason and provenance instead of treating it as missing output.

**For dry runs**: Show the same output but clearly label it as mock/simulated data.

#### 5c. Output file

- A run on this machine saves the full JSON output next to the bundle (`live_run.json` or `dry_run.json`).
- The output file path is in the `--with-memory` output, not in compact output.
- A hosted run saves no output file.

#### 5d. Present graph files

- A run on this machine generates graph visualizations by default (`live_run.html` / `dry_run.html`). Use `--no-graph` to disable.
- Live runs on this machine also write `live_run_graph.json` (the graph spec) next to the bundle.
- The graph file paths are in the `--with-memory` output, not in compact output.
- A hosted run writes no graph.

#### 5e. Mention intermediate results

- If the pipeline has multiple steps, briefly note key intermediate values from `working_memory` (e.g., "The match analysis intermediate step scored 82/100").
- Offer: "I can show the full working memory if you want to inspect any intermediate step."

#### 5f. Suggest next steps

- Re-run with different inputs
- Adjust prompts or pipe configurations if output quality needs improvement

### Step 6: Handle Errors

**If a live run fails because inference is not set up**: on a run that executes on this machine, either the runtime was never initialised and the error says config files are missing and suggests `pipelex init config`, or the error says it could not get credentials for an inference backend and names the missing variable, such as `OPENAI_API_KEY`. On a machine where inference was never set up, this is the user's first live inference run — congratulate them on reaching this milestone, then **immediately begin the `/mthds-runner-setup` flow inline** (do not ask the user to type it separately). Follow the full process from that skill to set up their own provider keys or the hosted Pipelex API, then re-run the method.

**If a hosted run is refused for its Pipelex API key**: the hosted API answers a missing or rejected `PIPELEX_API_KEY` with a 401 (`http_status` 401 in the error), whose hint says to run `pipelex login`. Ask the user to run `pipelex login` in their own terminal (not through Claude Code), or `pipelex login --paste` on a machine with no browser, which saves a new key to `~/.pipelex/.env`, then re-run the method. Never ask for the key in this conversation. A key exported in the shell does not replace one saved in `~/.pipelex/.env` or in a `.env` in the current directory, which pipelex reads over the shell.

For all other error types and recovery strategies, see [Error Handling Reference](../shared/error-handling.md).

### Execution Graphs

Execution graph visualizations are generated by default alongside the output of a run on this machine. Use `--no-graph` to disable.

```bash
mthds-agent run bundle <bundle-dir>/
```

Graph files (`live_run.html` / `dry_run.html`) are written to disk next to the bundle. Live runs additionally produce `live_run_graph.json` (the graph spec). Their paths are not in compact output: when using `--with-memory`, `graph_files` is included in the returned envelope. A run on the hosted Pipelex API writes no graph.

### Piping Methods

The run command accepts piped JSON on stdin when `--inputs` is not provided. This enables chaining methods:

```bash
mthds-agent run method extract-terms --inputs data.json --with-memory --format json \
  | mthds-agent run method assess-risk --with-memory --format json \
  | mthds-agent run method generate-report
```

When methods are installed as CLI shims, the same chain is:

```bash
extract-terms --inputs data.json --with-memory --format json \
  | assess-risk --with-memory --format json \
  | generate-report
```

- Use `--with-memory --format json` on intermediate steps to pass the full working memory envelope: stdin is read as JSON, and the default Markdown output is not.
- The final step omits `--with-memory` to produce compact output.
- `--inputs` always overrides stdin when both are present.
- Upstream stuff names are matched against downstream input names. Method authors should name their outputs to match the downstream's expected input names.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read for .mthds syntax documentation
- [Native Content Types](../shared/native-content-types.md) — read when interpreting pipeline outputs or preparing input JSON, to understand the attributes of each content type
