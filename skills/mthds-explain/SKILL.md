---
name: mthds-explain
min_mthds_version: 0.2.1
description: Explain and document MTHDS bundles. Use when user says "what does this pipeline do?", "explain this workflow", "explain this method", "walk me through this .mthds file", "describe the flow", "document this pipeline", "how does this work?", or wants to understand an existing MTHDS method bundle.
---

# Explain MTHDS bundles

Analyze and explain existing MTHDS method bundles in plain language.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.claude/plugins/marketplaces/mthds-plugins/bin/mthds-env-check "0.2.1" 2>/dev/null || ../mthds-plugins/bin/mthds-env-check "0.2.1" 2>/dev/null || true
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


Do not write `.mthds` files manually, do not do any other work. The CLI is required for validation, formatting, and execution — without it the output will be broken.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-pipelex-setup` when you're ready.

### Step 1: Read the .mthds File

Read the entire bundle file to understand its structure.

### Step 2: Identify Components

List all components found in the bundle:
- **Domain**: the `[domain]` declaration
- **Concepts**: all `[concept.*]` blocks — note which are custom vs references to native concepts
- **Pipes**: all `[pipe.*]` blocks — identify the main pipe and sub-pipes
- **Main pipe**: declared in `[bundle]` section

### Step 3: Trace Execution Flow

Starting from the main pipe, trace the execution path:
1. For **PipeSequence**: follow the `steps` array in order
2. For **PipeBatch**: identify `batch_over` and `batch_as`, then the inner pipe
3. For **PipeParallel**: list all branches
4. For **PipeCondition**: map condition → pipe for each branch
5. For **PipeLLM / PipeExtract / PipeImgGen / PipeSearch / PipeFunc**: these are leaf operations

### Step 4: Present Explanation

Structure the explanation as:

1. **Purpose**: one-sentence summary of what the method does
2. **Inputs**: list each input with its concept type and expected content
3. **Output**: the final output concept and what it contains
4. **Step-by-step flow**: walk through execution in order, explaining what each pipe does
5. **Key concepts**: explain any custom concepts defined in the bundle

### Step 5: Generate Flow Diagram

Create a text diagram showing the execution flow. Example:

```
main_sequence
  1. step_one (PipeLLM) -> intermediate_result
  2. step_two (PipeExtract) -> final_output

Inputs: input_a, input_b
Output: final_output
```

Adapt the format to the method structure (linear, branching, batched).

### Step 6: Optional — Validate

If the user wants to confirm the method is valid:
```bash
mthds-agent validate bundle <file>.mthds -L <bundle-dir>/
```

### Step 7: Optional — Visual Graph

For an interactive flowchart without running the method, use validate with `--graph`:
```bash
mthds-agent validate bundle <file>.mthds -L <bundle-dir>/ --graph
```

This generates `dry_run.html` next to the bundle — a static flowchart of the method structure.

For a live execution graph showing actual runtime data, use `/mthds-run`:
```bash
mthds-agent run bundle <bundle-dir>/
```

This produces `live_run.html` alongside the execution results.

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read when explaining what data flows through pipes (e.g., what attributes Page or Image content carries)
