# MTHDS Agent Guide

All skills in this plugin require `mthds-agent >= 0.30.0`. The Step 0 CLI Check in each skill enforces this — parse the output of `mthds-agent --version` and block execution if the version is below `0.30.0`.

## IMPORTANT PREREQUISITES

Before working, or if there is any doubt about the CLI, check the following in order.

### Tier 1 — Required for all skills (low friction)

The preamble already confirmed `mthds-agent` is installed and at the required version. Now bootstrap the remaining toolchain (`uv`, `pipelex-agent`, `plxt`) — no API keys or backend configuration required:

```bash
mthds-agent bootstrap
```

**Interpret the output:**

- `BOOTSTRAP_NOT_NEEDED` → All tools already installed. Proceed.
- `BOOTSTRAP_COMPLETE <json>` → Tools were installed. The JSON shows version transitions (e.g. `{"installed":{"pipelex":"missing->0.22.0"}}`). Announce what was installed, then proceed.
- `BOOTSTRAP_PARTIAL <json>` → Some tools installed, some failed. Report failures to the user with the JSON details. Proceed with what's available.
- `BOOTSTRAP_FAILED <json>` → All installs failed. Show the JSON to the user and suggest manual recovery. Do not proceed.

> **Note**: `pipelex-agent` is needed for validation and building; `plxt` is needed for linting and formatting. Neither requires API keys or backend configuration.

FROM NOW ON, ASSUME THE CLIs ARE INSTALLED AND WORKING, and ONLY USE `mthds-agent` commands (including `mthds-agent plxt lint` / `mthds-agent plxt fmt` for linting and formatting). The exceptions are two `pipelex-agent` commands that `mthds-agent` does not forward: `pipelex-agent doctor`, a read-only report of the Pipelex configuration (where runs execute, the Pipelex API key, each enabled backend's credentials) that `mthds-agent doctor` does not read, and `pipelex-agent migrate`, which the error handling reference calls for.

### Tier 2 — Required only for running methods with live inference

Inference setup (provider API keys and model routing, or a Pipelex API key) is **only** needed to run methods with live inference. It is **not** needed for: building, validating, editing, explaining, fixing, preparing inputs, or dry-running methods.

When a user needs to run methods with live inference, direct them to `/mthds-runner-setup` for guided configuration: it sets up the pipelex runner either with their own provider keys, for runs on this machine, or with a Pipelex API key, for runs on the hosted Pipelex API.

## Agent CLI

Agents must use `mthds-agent` exclusively, with the two `pipelex-agent` exceptions above. Output format varies by command:
- **JSON on stdout**: `inputs`, `install`, `package` commands
- **Markdown on stdout**: `run` (`# Pipeline run complete`, then the result under `## Result`; see "Understanding Run Output" below), `init`, `validate` (success report — `# Validation passed`, with a `## Pending signatures` section when signatures remain), `models`, `check-model`, `doctor` commands (human/LLM-readable by default; `--format json` gives JSON)
- **Errors**: on stderr with exit code 1. The JSON-output commands above report errors in JSON. **The commands that print markdown by default also report errors in markdown** — `run`, `init` and `validate` have independent `--format` (success/stdout) and `--error-format` (errors/stderr) controls, and `--error-format` follows `--format` when omitted; see "Lenient Validation" below. `plxt` passthrough commands emit raw text on stderr (see command table).

## Global Options

These options apply to **all** `mthds-agent` commands and must appear **before** the subcommand:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--runner` | `pipelex`, `api` | the configured runner, `pipelex` unless set | Selects `mthds-agent`'s runner for the command. `mthds-agent` reads this option wherever it appears and refuses any other value, so it never reaches pipelex: to choose where a pipelex run executes, use `--hosted` or `--local` (see below) |
| `--version` | — | — | Print version and exit |

### Runner Setup

After installing `mthds-agent`, set up the runner you need:

- **Pipelex runner** (the default, which runs methods):
  ```bash
  mthds-agent runner setup pipelex
  ```
  This installs pipelex with `uv tool` when it is missing, or upgrades it when it is older than the minimum `mthds-agent` requires, and configures nothing. `mthds-agent init` then writes the Pipelex configuration, and keys are added by the user, never by `init`: see `/mthds-runner-setup`.

  A run on the pipelex runner executes in one of two places:
  - **On this machine** (the default), where pipelex calls each AI provider with the user's own keys.
  - **On the hosted Pipelex API**, where pipelex sends the method and its inputs with the Pipelex API key in `PIPELEX_API_KEY`, which the user gets by running `pipelex login` in their own terminal. This needs pipelex 0.79.0 or later.

  The `[run] execution` setting of the Pipelex configuration picks the default, `local` or `hosted` (`mthds-agent init -g --config '{"execution": "hosted"}'` sets it), and `--hosted` or `--local` on a run overrides it. Pass those two flags, never `--runner hosted` or `--runner local`: `mthds-agent` consumes `--runner` as its own option and refuses those values.

- **API runner** (calls a Pipelex API server directly):
  ```bash
  mthds-agent runner setup api --api-key <your-api-key>
  # Optional: specify a custom API base URL (defaults to https://api.pipelex.com)
  mthds-agent runner setup api --api-key <your-api-key> --base-url <url>
  ```
  It validates bundles, projects inputs and lists models on that server, but it cannot run a bundle: `mthds-agent run bundle` fails on it as an unknown command, and `run method` is not supported. To run methods on the hosted Pipelex API, use the pipelex runner with hosted execution.

Set which runner is used by default:
```bash
mthds-agent config set runner pipelex       # or: api
```

Use `--runner` to override the default per-command:
```bash
mthds-agent --runner pipelex validate bundle bundle.mthds -L dir/
```

## Building Methods

Use the /mthds-design skill: it captures the method's contract, writes the bundle's TOML directly with the agent's file tools — in one pass for a shallow graph, or stepwise through `PipeSignature` headers for a deep one — and validates it until it is runnable. Writing through the file tools lets the lint, format and validate hooks run. Refine with /mthds-edit and /mthds-fix if the result needs adjustments.

## The Iterative Development Loop

1. **Design or Edit** the `.mthds` file (using /mthds-design or /mthds-edit)
2. **Validate** with `mthds-agent validate bundle file.mthds -L dir/`
   - If errors: fix them with /mthds-fix, then re-validate (repeat until clean)
3. **Run** with `mthds-agent run bundle <bundle-dir>/`
4. **Inspect output** and refine if needed — loop back to step 1

## Understanding Run Output

### Success Format

`mthds-agent run bundle` prints Markdown by default: a `# Pipeline run complete` heading, then the result under `## Result`. Pass `--format json` for JSON on stdout, which `jq`, other JSON tools and a piped method need. The command has two output modes:

**Compact (default)**: The concept's structured JSON — no envelope, no metadata. In Markdown it sits in a fenced `json` block under `## Result`; with `--format json` it is emitted directly:

```json
{
  "clauses": [
    { "title": "Non-Compete", "risk_level": "high" },
    { "title": "Termination", "risk_level": "medium" }
  ],
  "overall_risk": "high"
}
```

**With memory (`--with-memory`)**: The full working memory envelope for piping to another method; with `--format json` it is emitted as is, and in Markdown `## Result` shows its `main_stuff.markdown`:

```json
{
  "main_stuff": {
    "json": "<concept as JSON string>",
    "markdown": "<concept as Markdown string>",
    "html": "<concept as HTML string>"
  },
  "working_memory": {
    "root": { ... },
    "aliases": { ... }
  }
}
```

On a run on this machine, the envelope also carries `output_file` and `graph_files`, the files the run wrote next to the bundle. **A run on the hosted Pipelex API writes nothing to disk**: its `main_stuff` carries the result in `json` alone, with `markdown` and `html` left empty, so the Markdown output falls back to that JSON, and its envelope carries `pipeline_run_id`, the run's id on the hosted API, in place of the file paths.

`inputs` outputs its JSON envelope with `"success": true`. `validate bundle` defaults to **markdown**; pass `--format json` to get its `"success": true` envelope (see "Lenient Validation" below).

### Error Handling

For all error types, recovery strategies, and error domains, see [Error Handling Reference](error-handling.md).

## Inputs

### `--inputs` Flag

The `--inputs` flag on `mthds-agent run bundle` accepts **both** file paths and inline JSON. The CLI auto-detects: if the value starts with `{`, it is parsed as JSON directly.

```bash
# File path
mthds-agent run bundle bundle.mthds --inputs inputs.json

# Inline JSON (no file creation needed)
mthds-agent run bundle bundle.mthds --inputs '{"theme": {"concept": "native.Text", "content": {"text": "nature"}}}'
```

Inline JSON is the fastest path for agents — skip file creation for simple inputs.

### stdin (Piped Input)

When `--inputs` is not provided and stdin is not a TTY (i.e., data is piped), JSON is read from stdin:

```bash
echo '{"text": {"concept": "native.Text", "content": {"text": "hello"}}}' | mthds-agent run bundle <bundle-dir>/
```

**`--inputs` always takes priority** over stdin. If both are present, stdin is ignored.

When stdin contains a `working_memory` key (from upstream `--with-memory` output), the runtime automatically extracts stuffs from the working memory and resolves them as inputs.

## Piping Methods

Methods can be chained via Unix pipes using `--with-memory --format json` to pass the full working memory between steps:

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

- **`--with-memory --format json`** on intermediate steps emits the full envelope (`main_stuff` + `working_memory`) as JSON, which is what stdin reads; the default Markdown output cannot be piped.
- The **final step** omits `--with-memory` to produce compact output (concept JSON only).
- **Name matching**: upstream stuff names are matched against downstream input names. Method authors should name their outputs to match downstream expectations.

## Working Directory Convention

All generated files go into `mthds-wip/`, organized per pipeline:

```
mthds-wip/
  pipeline_01/              # Automated build output
    bundle.mthds
    inputs.json             # Input template
    inputs/                 # Synthesized input files
      test_input.json
    test-files/             # Generated test files (images, PDFs)
      photo.jpg
    dry_run.html            # Graph HTML (generated by `validate --graph` or `run --dry-run`)
    live_run.html           # Execution graph from a full run on this machine
    live_run_graph.json     # Graph spec JSON from a full run on this machine
  pipeline_02/
    bundle.mthds
    ...
```

A run on the hosted Pipelex API writes none of the run files.

## Library Isolation

Pipelex loads `.mthds` files into a flat namespace. When multiple bundles exist in the project, pipe codes can collide. Use **directory mode** for `run` to auto-detect the bundle, inputs, and library dir, or pass `-L` explicitly for other commands:

```bash
# Validate (isolated)
mthds-agent validate bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/

# Run (directory mode: auto-detects bundle, inputs, and -L)
mthds-agent run bundle mthds-wip/pipeline_01/
```

## Lenient Validation — `--allow-signatures`

A bundle that contains `PipeSignature` pipes (contract-only headers, used by stepwise design) still validates: a signature is never a validation error, and the verdict lists the pending ones. Pass `--allow-signatures` to validate **leniently**, which changes only how validation runs — each signature is dry-run too, minting a mock of its declared output:

```bash
mthds-agent validate bundle bundle.mthds -L dir/ --allow-signatures
```

`mthds-agent` forwards the flag verbatim to the pipelex CLI (`.allowUnknownOption()`), so no `mthds-agent`-side option is required.

- **Lenient (`--allow-signatures`)** — mock-runs each signature, and a valid bundle exits 0 whether or not it is runnable. Use it after each layer of a stepwise design, while signatures still remain.
- **Strict (default)** — leaves signatures out of the dry run, and on the pipelex runner a valid bundle that is not yet runnable exits 1. The `✅ … this method is runnable.` line of a strict validation is the gate that says *runnable*. Live execution always rejects signatures (`PipeSignatureNotExecutableError`).

On a bundle with **no** signatures, lenient and strict are identical — `--allow-signatures` is a no-op there.

### Reading runnability and `pending_signatures`

A successful `validate bundle` states, in plain English, whether the method is **runnable**, and lists the pipes still declared as signatures — the build's todo list: contract-only headers with no concrete definition yet (namespaced `domain.code` refs; empty when the method is complete).

**Markdown (default) — an LLM reads this directly, no flags needed.** On success the output ends with a runnability verdict:

- **Runnable** (no signatures remain) — no `## Pending signatures` section, just:

  ```
  ✅ All pipes are concretely implemented — no `PipeSignature` placeholders remain. Strict validation will pass; this method is runnable.
  ```

- **Not yet runnable** — the verdict, then a `## Pending signatures (N)` heading and one bullet per pending `domain.code` ref:

  ```
  ⚠️ This method is NOT yet runnable — N pipes are still `PipeSignature` placeholders and must be implemented before running:

  ## Pending signatures (N)

  - `domain.code`
  ```

**JSON — for a *program* that extracts a field.** Pin **both** format streams: `validate bundle` has two independent controls — `--format` governs the **success** envelope on stdout, `--error-format` governs the **error** report on stderr — and `--error-format` *inherits* `--format` when omitted, so `--format json` alone flips errors to JSON too. Pin them explicitly for the read you want: `--error-format json` to parse structured errors too (this is what the PostToolUse hook does), or `--error-format markdown` to keep a machine-parseable success envelope while leaving errors as human-readable markdown on stderr:

```bash
mthds-agent validate bundle bundle.mthds -L dir/ --allow-signatures --format json --error-format markdown
```

The success JSON on stdout then carries:

- `is_runnable` — boolean; `true` ⇔ `pending_signatures` is empty. The structured "is the method done / runnable?" signal — prefer it over inferring from the array length.
- `pending_signatures` — the array of namespaced refs still declared as contract-only signatures (use it to drive *which* placeholders to implement next).
- plus `validated_pipes`, `total_pipes`.

**Scope:** the runnability verdict and `is_runnable` / `pending_signatures` appear **only on `validate bundle`** (including `validate bundle --pipe`). `validate all` and `validate pipe` don't compute them — don't key off these fields there.

## Package Management

The `mthds-agent package` commands manage MTHDS package manifests (`METHODS.toml`).

Use these commands to initialize packages, list manifests, and validate them.

All `mthds-agent package` commands accept `-C <path>` (long: `--package-dir`) to target a package directory other than CWD. This is essential when the agent's working directory differs from the package location:

```bash
mthds-agent package init --address github.com/org/repo --version 1.0.0 --description "My package" -C mthds-wip/restaurant_presenter/
mthds-agent package validate -C mthds-wip/restaurant_presenter/
```

> **Note**: `mthds-agent package validate` validates the `METHODS.toml` package manifest — not `.mthds` bundle semantics. For bundle validation, use `mthds-agent validate bundle`.

## Generating Visualizations

Agents can generate execution graph visualizations for human review.

### Validation Graphs

The `--graph` flag on `mthds-agent validate bundle` generates an interactive HTML flowchart (`dry_run.html`) next to the bundle — the fastest way to visualize method structure (no API keys or backends needed).

```bash
mthds-agent validate bundle bundle.mthds -L dir/ --graph
```

Additional options:
- `--graph-format <format>` — Output format for the graph (default: `reactflow`)
- `--direction <dir>` — Graph layout direction (e.g., `TB` for top-to-bottom, `LR` for left-to-right)

The path to the generated graph appears in the stderr logs; when `--format json` is set, it's also in the JSON envelope as `graph_files`.

### Execution Graphs

Execution graph visualizations are generated by default with every `mthds-agent run bundle` command that runs on this machine. Use `--no-graph` to disable.

```bash
mthds-agent run bundle <bundle-dir>/
```

Graph files (`live_run.html` / `dry_run.html`) are written to disk next to the bundle. Live runs additionally produce `live_run_graph.json` (the graph spec). Their paths are not in compact output: when using `--with-memory`, `graph_files` is included in the returned envelope. A run on the hosted Pipelex API writes no graph.

## Agent CLI Command Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `mthds-agent init` | Initialize the Pipelex configuration (non-interactive; pipelex runner only; writes no keys). `--config` takes `execution` (`"local"`, the default, or `"hosted"`, which needs pipelex 0.79.0 or later and refuses `backends`), `backends` and `primary_backend`; it resets the configuration files it writes | `mthds-agent init -g --config '{"backends": ["openai"]}'` / `mthds-agent init -g --config '{"execution": "hosted"}'` |
| `mthds-agent run bundle` | Execute a pipeline (markdown by default, `--format json` for JSON; compact output unless `--with-memory`; `--hosted` or `--local` for where it runs) | `mthds-agent run bundle <bundle-dir>/` |
| `mthds-agent validate bundle` | Validate a bundle (`--graph` for flowchart HTML; `--allow-signatures` for lenient validation of a stepwise design) | `mthds-agent validate bundle bundle.mthds --graph` |
| `mthds-agent inputs bundle` | Generate example input JSON (`--explicit` wraps each input in its `{concept, content}` envelope) | `mthds-agent inputs bundle bundle.mthds --explicit` |
| `mthds-agent models` | List available model presets, aliases (outputs markdown) | `mthds-agent models` / `mthds-agent models --type llm` / `mthds-agent models --type search` |
| `mthds-agent check-model` | Validate a model reference with fuzzy suggestions (outputs markdown or JSON; pipelex runner only) | `mthds-agent check-model '$writing-creative' --type llm` |
| `mthds-agent doctor` | Check the toolchain and the mthds configuration; never writes (outputs markdown) | `mthds-agent doctor` |
| `mthds-agent install` | Install a method package from GitHub or local directory | `mthds-agent install org/repo --location local` |
| `mthds-agent package init` | Initialize METHODS.toml | `mthds-agent package init --address github.com/org/repo --version 1.0.0 --description "desc" -C <pkg-dir>` |
| `mthds-agent package list` | Display package manifest | `mthds-agent package list -C <pkg-dir>` |
| `mthds-agent package validate` | Validate METHODS.toml package manifest | `mthds-agent package validate -C <pkg-dir>` |
| `mthds-agent runner setup pipelex` | Install pipelex with `uv tool`, or upgrade it when it is older than the minimum `mthds-agent` requires | `mthds-agent runner setup pipelex` |
| `mthds-agent runner setup api` | Set up the API runner, which validates, projects inputs and lists models on a Pipelex API server but cannot run a bundle (defaults to https://api.pipelex.com) | `mthds-agent runner setup api --api-key <key> [--base-url <url>]` |
| `mthds-agent config set` | Set a config value (runner, base-url, api-key, telemetry, auto-upgrade, update-check) | `mthds-agent config set runner pipelex` |
| `mthds-agent config list` | List all config values | `mthds-agent config list` |
| `mthds-agent plxt lint` | Lint `.mthds`/`.toml` files for TOML syntax and schema errors (passthrough to plxt — raw text output on stderr, not JSON) | `mthds-agent plxt lint <file>.mthds` |
| `mthds-agent plxt fmt` | Auto-format `.mthds`/`.toml` files (passthrough to plxt — raw text output on stderr, not JSON) | `mthds-agent plxt fmt <file>.mthds` |
