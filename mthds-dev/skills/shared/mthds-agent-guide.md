# MTHDS Agent Guide

All skills in this plugin require `mthds-agent >= 0.10.0`. The Step 0 CLI Check in each skill enforces this — parse the output of `mthds-agent --version` and block execution if the version is below `0.10.0`.

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

FROM NOW ON, ASSUME THE CLIs ARE INSTALLED AND WORKING, and ONLY USE `mthds-agent` commands (including `mthds-agent plxt lint` / `mthds-agent plxt fmt` for linting and formatting).

### Tier 2 — Required only for running methods with live inference

Backend configuration (API keys, model routing) is **only** needed to run methods with live inference. It is **not** needed for: building, validating, editing, explaining, fixing, preparing inputs, or dry-running methods.

When a user needs to run methods with live inference, direct them to `/mthds-runner-setup` for guided configuration.

## Agent CLI

Agents must use `mthds-agent` exclusively. Output format varies by command:
- **JSON on stdout**: `run`, `inputs`, `init`, `install`, `package` commands
- **Markdown on stdout**: `validate` (success report — `# Validation passed`, with a `## Pending signatures` section when signatures remain), `models`, `check-model`, `doctor` commands (human/LLM-readable by default)
- **Raw TOML on stdout**: `concept`, `pipe` commands (return TOML directly, not wrapped in JSON)
- **Errors**: JSON on stderr with exit code 1 for the JSON-output commands above. **`validate` emits markdown errors on stderr by default** — it has independent `--format` (success/stdout) and `--error-format` (errors/stderr) controls; see "Lenient Validation" below. `plxt` passthrough commands emit raw text on stderr (see command table).

## Global Options

These options apply to **all** `mthds-agent` commands and must appear **before** the subcommand:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--runner` | `pipelex`, `api` | default runner | Selects which runner to use for the command |
| `--version` | — | — | Print version and exit |

### Runner Setup

After installing `mthds-agent`, set up the runner you need:

- **Local runner** (Pipelex — runs pipelines locally, requires backend API keys):
  ```bash
  mthds-agent runner setup pipelex
  ```
  This installs the Pipelex runner binary (managed by mthds-agent, not installed via uv/pip). To configure backends and API keys for local execution, run `mthds-agent init` afterwards (see `/mthds-runner-setup`).

- **API runner** (remote execution via the Pipelex API):
  ```bash
  mthds-agent runner setup api --api-key <your-api-key>
  # Optional: specify a custom API base URL (defaults to https://api.pipelex.com)
  mthds-agent runner setup api --api-key <your-api-key> --base-url <url>
  ```

Set which runner is used by default:
```bash
mthds-agent config set runner api       # or: pipelex
```

Use `--runner` to override the default per-command:
```bash
mthds-agent --runner pipelex validate bundle bundle.mthds -L dir/
```

## Building Methods

Use the /mthds-build skill for a guided 10-phase process: requirements → plan → concepts → structure → flow → review → pipes → assemble → validate → deliver. The concept and pipe CLI commands validate and return raw TOML; in Phase 8, deterministically assemble those validated fragments into `bundle.mthds` (not manual authoring), then write the file so lint/format/validate hooks run. Refine with /mthds-edit and /mthds-fix if the result needs adjustments.

## The Iterative Development Loop

1. **Build or Edit** the `.mthds` file (using /mthds-build or /mthds-edit)
2. **Validate** with `mthds-agent validate bundle file.mthds -L dir/`
   - If errors: fix them with /mthds-fix, then re-validate (repeat until clean)
3. **Run** with `mthds-agent run bundle <bundle-dir>/`
4. **Inspect output** and refine if needed — loop back to step 1

## Understanding JSON Output

### Success Format

The `mthds-agent run bundle` command has two output modes:

**Compact (default)**: The concept's structured JSON is emitted directly — no envelope, no metadata:

```json
{
  "clauses": [
    { "title": "Non-Compete", "risk_level": "high" },
    { "title": "Termination", "risk_level": "medium" }
  ],
  "overall_risk": "high"
}
```

This works directly with `jq` and other JSON tools.

**With memory (`--with-memory`)**: The full working memory envelope for piping to another method:

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

Other `mthds-agent` commands (`inputs`, etc.) output their JSON envelope with `"success": true`. `validate bundle` is the exception — it defaults to **markdown**; pass `--format json` to get its `"success": true` envelope (see "Lenient Validation" below).

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

Methods can be chained via Unix pipes using `--with-memory` to pass the full working memory between steps:

```bash
mthds-agent run method extract-terms --inputs data.json --with-memory \
  | mthds-agent run method assess-risk --with-memory \
  | mthds-agent run method generate-report
```

When methods are installed as CLI shims, the same chain is:

```bash
extract-terms --inputs data.json --with-memory \
  | assess-risk --with-memory \
  | generate-report
```

- **`--with-memory`** on intermediate steps emits the full envelope (`main_stuff` + `working_memory`).
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
    live_run.html           # Execution graph from full run
    live_run_graph.json     # Graph spec JSON from full run
  pipeline_02/
    bundle.mthds
    ...
```

## Library Isolation

Pipelex loads `.mthds` files into a flat namespace. When multiple bundles exist in the project, pipe codes can collide. Use **directory mode** for `run` to auto-detect the bundle, inputs, and library dir, or pass `-L` explicitly for other commands:

```bash
# Validate (isolated)
mthds-agent validate bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/

# Run (directory mode: auto-detects bundle, inputs, and -L)
mthds-agent run bundle mthds-wip/pipeline_01/
```

## Lenient Validation — `--allow-signatures`

A bundle that contains `PipeSignature` pipes (contract-only headers, used by top-down/recursive building) fails **strict** validation by default. Pass `--allow-signatures` to validate **leniently** — reachable signatures are accepted, each minting a mock of its declared output:

```bash
mthds-agent validate bundle bundle.mthds -L dir/ --allow-signatures
```

`mthds-agent` forwards the flag verbatim to the pipelex CLI (`.allowUnknownOption()`), so no `mthds-agent`-side option is required.

- **Lenient (`--allow-signatures`)** — accepts a bundle whose dependency graph reaches signatures. Use it after each layer of a recursive build, while signatures still remain.
- **Strict (default)** — rejects any reachable signature. Passing strict validation is the gate that says *runnable*. Live execution always rejects signatures (`PipeSignatureNotExecutableError`).

On a bundle with **no** signatures, lenient and strict are identical — `--allow-signatures` is a no-op there.

### Reading runnability and `pending_signatures`

A successful `validate bundle` states, in plain English, whether the method is **runnable**, and lists the pipes still typed `PipeSignature` — the build's todo list: declared signatures with no concrete definition yet (namespaced `domain.code` refs; empty when the method is complete).

**Markdown (default) — an LLM reads this directly, no flags needed.** On success the output ends with a runnability verdict:

- **Runnable** (no signatures remain) — no `## Pending signatures` section, just:

  ```
  ✅ All pipes are concretely implemented — no `PipeSignature` placeholders remain. Strict validation will pass; this method is runnable.
  ```

- **Not yet runnable** — a `## Pending signatures (N)` heading, then the verdict, then one bullet per pending `domain.code` ref:

  ```
  ## Pending signatures (N)

  ⚠️ This method is NOT yet runnable — N pipe(s) are still `PipeSignature` placeholders and must be implemented before running:

  - `domain.code`
  ```

**JSON — for a *program* that extracts a field.** Pin **both** format streams: `validate bundle` has two independent controls — `--format` governs the **success** envelope on stdout, `--error-format` governs the **error** report on stderr — and `--error-format` *inherits* `--format` when omitted, so `--format json` alone flips errors to JSON too. Pin them explicitly for the read you want: `--error-format json` to parse structured errors too (this is what the PostToolUse hook does), or `--error-format markdown` to keep a machine-parseable success envelope while leaving errors as human-readable markdown on stderr:

```bash
mthds-agent validate bundle bundle.mthds -L dir/ --allow-signatures --format json --error-format markdown
```

The success JSON on stdout then carries:

- `is_runnable` — boolean; `true` ⇔ `pending_signatures` is empty. The structured "is the method done / runnable?" signal — prefer it over inferring from the array length.
- `pending_signatures` — the array of namespaced refs still declared as `PipeSignature` (use it to drive *which* placeholders to implement next).
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

Execution graph visualizations are generated by default with every `mthds-agent run bundle` command. Use `--no-graph` to disable.

```bash
mthds-agent run bundle <bundle-dir>/
```

Graph files (`live_run.html` / `dry_run.html`) are written to disk next to the bundle. Live runs additionally produce `live_run_graph.json` (the graph spec). Their paths appear in runtime logs on stderr, not in compact stdout. When using `--with-memory`, `graph_files` is included in the returned JSON envelope.

## Agent CLI Command Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `mthds-agent init` | Initialize pipelex configuration (non-interactive) | `mthds-agent init -g --config '{"backends": ["openai"]}'` |
| `mthds-agent run bundle` | Execute a pipeline (compact output by default; use `--with-memory` for full envelope) | `mthds-agent run bundle <bundle-dir>/` |
| `mthds-agent validate bundle` | Validate a bundle (`--graph` for flowchart HTML; `--allow-signatures` for lenient/recursive validation) | `mthds-agent validate bundle bundle.mthds --graph` |
| `mthds-agent inputs bundle` | Generate example input JSON | `mthds-agent inputs bundle bundle.mthds` |
| `mthds-agent concept` | Validate and structure a concept from JSON spec (returns raw TOML) | `mthds-agent concept --spec '{...}'` |
| `mthds-agent pipe` | Validate and structure a pipe from JSON spec (returns raw TOML). Field names: `type`, `pipe_code`, and optionally `model`. Omit `model` to use defaults; set it only for specialized needs or explicit user requests | `mthds-agent pipe --spec '{"type": "PipeLLM", "pipe_code": "my_pipe", "prompt": "...", ...}'` |
| `mthds-agent models` | List available model presets, aliases (outputs markdown) | `mthds-agent models` / `mthds-agent models --type llm` / `mthds-agent models --type search` |
| `mthds-agent check-model` | Validate a model reference with fuzzy suggestions (outputs markdown or JSON) | `mthds-agent check-model "$writing-creative" --type llm` |
| `mthds-agent accept-gateway-terms` | Accept Pipelex Gateway terms and mark inference setup complete | `mthds-agent accept-gateway-terms` |
| `mthds-agent doctor` | Check config health and auto-fix (outputs markdown) | `mthds-agent doctor` |
| `mthds-agent install` | Install a method package from GitHub or local directory | `mthds-agent install org/repo --location local` |
| `mthds-agent package init` | Initialize METHODS.toml | `mthds-agent package init --address github.com/org/repo --version 1.0.0 --description "desc" -C <pkg-dir>` |
| `mthds-agent package list` | Display package manifest | `mthds-agent package list -C <pkg-dir>` |
| `mthds-agent package validate` | Validate METHODS.toml package manifest | `mthds-agent package validate -C <pkg-dir>` |
| `mthds-agent runner setup pipelex` | Install the local Pipelex runner (managed by mthds-agent) | `mthds-agent runner setup pipelex` |
| `mthds-agent runner setup api` | Set up the API runner for remote execution (defaults to https://api.pipelex.com) | `mthds-agent runner setup api --api-key <key> [--base-url <url>]` |
| `mthds-agent config set` | Set a config value (runner, base-url, api-key, telemetry, auto-upgrade, update-check) | `mthds-agent config set runner pipelex` |
| `mthds-agent config list` | List all config values | `mthds-agent config list` |
| `mthds-agent plxt lint` | Lint `.mthds`/`.toml` files for TOML syntax and schema errors (passthrough to plxt — raw text output on stderr, not JSON) | `mthds-agent plxt lint <file>.mthds` |
| `mthds-agent plxt fmt` | Auto-format `.mthds`/`.toml` files (passthrough to plxt — raw text output on stderr, not JSON) | `mthds-agent plxt fmt <file>.mthds` |
