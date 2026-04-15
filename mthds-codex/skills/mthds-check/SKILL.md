---
name: mthds-check
description: Check and validate MTHDS bundles for issues. Use when user says "validate this", "check my workflow", "check my method", "does this .mthds make sense?", "review this pipeline", "any issues?", "is this correct?". Reports problems without modifying files. Read-only analysis.
min_mthds_version: 0.4.1
---

# Check MTHDS bundles

Validate and review MTHDS bundles based on the MTHDS standard without making changes.

## Process

### Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.codex/bin/mthds-env-check "0.4.1" 2>/dev/null || echo "MTHDS_ENV_CHECK_MISSING"
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


Do not write `.mthds` files manually, do not do any other work. The CLI is required for validation, formatting, and execution — without it the output will be broken.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away. Backend configuration is only needed to run methods with live inference — use `/mthds-runner-setup` when you're ready.

### Step 1: Read the .mthds File

Load and parse the method.

### Step 2: Run plxt Lint

Catch TOML syntax and schema errors before semantic validation. This skill is read-only and never triggers the PostToolUse hook, so lint must be run explicitly:

```bash
mthds-agent plxt lint <file>.mthds
```

If lint reports errors, include them in the final report and continue — semantic validation in the next step may reveal additional issues.

### Step 3: Run CLI Validation

Use `-L` pointing to the bundle's own directory to avoid namespace collisions. `--graph` generates a flowchart:

```bash
mthds-agent validate bundle <file>.mthds -L <bundle-directory>/ --graph
```

### Step 4: Parse the JSON Output

- If `success: true` — all pipes validated, report clean status
- If error — see [Error Handling Reference](../shared/error-handling.md) for error types and recovery

### Step 5: Cross-Domain Validation

When the bundle references pipes from other domains, use `--library-dir` (see [Error Handling — Cross-Domain](../shared/error-handling.md#cross-domain-validation)).

### Step 6: Analyze for Additional Issues

Manual review beyond CLI validation:
- Unused concepts (defined but never referenced)
- Unreachable pipes (not in main_pipe execution path)
- Missing descriptions on pipes or concepts
- Inconsistent naming conventions
- Potential prompt issues (missing variables, unclear instructions)

### Step 7: Report Findings

Report by severity:
- **Errors**: Validation failures from CLI (with `error_type` and `pipe_code`) and plxt lint errors
- **Warnings**: Issues that may cause problems (e.g., model availability)
- **Suggestions**: Improvements for maintainability
- **Flowchart**: If validation succeeded, mention the generated `dry_run.html` flowchart next to the bundle

### Step 8: Do NOT Make Changes

This skill is read-only.

## What Gets Checked

- TOML syntax and schema validation (via `mthds-agent plxt lint`)
- Concept definitions and references
- Pipe type configurations
- Input/output type matching
- Variable references in prompts
- Cross-domain references
- Naming convention compliance
- Model reference resolution (dry run)

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read when reviewing .mthds TOML syntax
- [Native Content Types](../shared/native-content-types.md) — read when checking `$var.field` references in prompts to verify the attribute exists on the content type
