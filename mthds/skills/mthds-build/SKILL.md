---
name: mthds-build
description: Build new AI method from scratch using the MTHDS standard (.mthds bundle files). Use when user says "create a pipeline", "build a workflow", "new .mthds file", "make a method", "design a pipe", or wants to create any new method from scratch. Guides the user through a 10-phase construction process.
min_mthds_version: 0.4.1
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Build AI Method using the MTHDS standard

Create new MTHDS bundles through an adaptive, phase-based approach. This skill guides you through drafting (markdown), structuring (CLI/JSON), and assembling complete .mthds bundles.

## Philosophy

1. **Drafting phases**: Generate human-readable markdown documents
2. **Structuring phases**: Use agent CLI commands for JSON-to-TOML conversion
3. **Flow overviews**: Summarize flow structure at each phase
4. **Iterative**: Refine at each phase before proceeding

## Mode Selection

### How mode is determined

1. **Explicit override**: If the user states a preference, always honor it:
   - Automatic signals: "just do it", "go ahead", "automatic", "quick", "don't ask"
   - Interactive signals: "walk me through", "help me", "guide me", "step by step", "let me decide"

2. **Skill default**: Each skill defines its own default based on the nature of the task.

3. **Request analysis**: If no explicit signal and no strong skill default, assess the request:
   - Detailed, specific requirements → automatic
   - Brief, ambiguous, or subjective → interactive

### Mode behavior

**Automatic mode:**
- State assumptions briefly before proceeding
- Make reasonable decisions at each step
- Present the result when done
- Pause only if a critical ambiguity could lead to wasted work

**Interactive mode:**
- Ask clarifying questions at the start
- Present options at decision points
- Confirm before proceeding at checkpoints
- Allow the user to steer direction

### Mode switching

- If in automatic mode and the user asks a question or gives feedback → switch to interactive for the current phase
- If in interactive mode and the user says "looks good, go ahead" or similar → switch to automatic for remaining phases

**Default**: Automatic for simple-to-moderate methods. Interactive for complex multi-step methods or when the user's request is ambiguous.

**Detection heuristics**:
- User provides a clear one-sentence goal → automatic
- User describes a complex multi-step process → interactive
- User mentions batching, conditions, or parallel execution → interactive
- User says "create a pipeline for X" with no elaboration → automatic

---

## Step 0 — Environment Check (mandatory, do this FIRST)

Run this command to check toolchain status:

```bash
~/.claude/plugins/marketplaces/mthds-plugins/bin/mthds-env-check "0.4.1" 2>/dev/null || ../mthds-plugins/bin/mthds-env-check "0.4.1" 2>/dev/null || echo "MTHDS_ENV_CHECK_MISSING"
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

---

## Phase 1: Understand Requirements

**Goal**: Gather complete information before planning.

Ask the user:
- What are the method's inputs? (documents, images, text, structured data)
- What outputs should it produce?
- What transformations are needed?
- Are there conditional branches or parallel operations?
- Should items be processed in batches?

**Output**: Requirements summary (keep in context)

---

## Phase 2: Draft the Plan

**Goal**: Create a pseudo-code narrative of the method.

Draft a plan in markdown that describes:
- The overall flow from inputs to outputs
- Each processing step with its purpose
- Variable names (snake_case) for inputs and outputs of each step
- Where structured data or lists are involved

**Rules**:
- Name variables consistently across steps
- Use plural names for lists (e.g., `documents`), singular for items (e.g., `document`)
- Don't detail types yet - focus on the flow

**Show bundle overview** — see [Build Phases](references/build-phases.md#phase-2-bundle-overview) for the overview description.

**Output**: Plan draft (markdown)

---

## Phase 3: Draft Concepts

**Goal**: Identify all data types needed in the method.

From the plan, identify input, intermediate, and output concepts.

For each concept, draft:
- **Name**: PascalCase, singular noun (e.g., `Invoice` not `Invoices`)
- **Description**: What it represents
- **Type**: Either `refines: NativeConcept` OR `structure: {...}`

**Native concepts** (built-in, do NOT redefine): `Text`, `Html`, `Image`, `Document`, `Number`, `Page`, `TextAndImages`, `ImgGenPrompt`, `JSON`, `SearchResult`, `Anything`, `Dynamic`. See [MTHDS Language Reference — Native Concepts](../shared/mthds-reference.md#native-concepts)

> **Note**: `Document` is the native concept for any document (PDF, Word, etc.). `Image` is for any image format (JPEG, PNG, etc.). File formats like "PDF" or "JPEG" are not concepts.

Each native concept has accessible attributes (e.g., `Image` has `url`, `public_url`, `filename`, `caption`...; `Document` has `url`, `public_url`, `filename`...; `Page` has `text_and_images` and `page_view`). See [Native Content Types](../shared/native-content-types.md) for the full attribute reference — essential for `$var.field` prompts and `construct` blocks.

**Concept naming rules**:
- No adjectives: `Article` not `LongArticle`
- No circumstances: `Argument` not `CounterArgument`
- Always singular: `Employee` not `Employees`

**Output**: Concepts draft (markdown)

---

## Phase 4: Structure Concepts

**Goal**: Convert concept drafts to validated TOML using the CLI.

Prepare JSON specs for all concepts, then convert them **in parallel** by making multiple concurrent tool calls. Each command outputs validated TOML directly — keep the output in context for assembly in Phase 8.

**Example** (3 concepts converted in parallel):
```bash
# Call all three in parallel (single response, multiple tool calls):
mthds-agent concept --spec '{"concept_code": "Invoice", "description": "A commercial invoice document", "structure": {"invoice_number": "The unique identifier", "vendor_name": {"type": "text", "description": "Vendor name", "required": true}, "total_amount": {"type": "number", "description": "Total amount", "required": true}}}'
mthds-agent concept --spec '{"concept_code": "LineItem", "description": "A single line item on an invoice", "structure": {"description": "Item description", "quantity": {"type": "integer", "required": true}, "unit_price": {"type": "number", "required": true}}}'
mthds-agent concept --spec '{"concept_code": "Summary", "description": "A text summary of content", "refines": "Text"}'
```

**Field types**: `text`, `integer`, `boolean`, `number`, `date`, `concept`, `list`

**Choices (enum-like constrained values)**:
```toml
status = {choices = ["pending", "processing", "completed"], description = "Order status", required = true}
score = {type = "number", choices = ["0", "0.5", "1", "1.5", "2"], description = "Score on a half-point scale"}
```
When `choices` is present, `type` defaults to `text` if omitted. You can also pair choices with `integer` or `number` types explicitly.

**Nested concept references** in structures:
```toml
field = {type = "concept", concept_ref = "my_domain.OtherConcept", description = "...", required = true}
items = {type = "list", item_type = "concept", item_concept_ref = "my_domain.OtherConcept", description = "..."}
```

**Output**: Validated concept TOML (raw TOML output, held in context for Phase 8)

> **Partial failures**: If some commands fail, fix the failing specs using the error message (`error_domain: "input"` means the spec is wrong). Re-run only the failed commands.

---

## Phase 5: Draft the Flow

**Goal**: Design the complete pipeline structure with controller selection.

### Controller Selection Guide

| Controller | Use When | Key Pattern |
|------------|----------|-------------|
| **PipeSequence** | Steps must execute in order | step1 → step2 → step3 |
| **PipeBatch** | Same operation on each list item | map(items, transform) |
| **PipeParallel** | Independent operations run together | fork → join |
| **PipeCondition** | Route based on data values | if-then-else |

### Operator Selection Guide

| Operator | Use When |
|----------|----------|
| **PipeLLM** | Generate text or structured objects with AI |
| **PipeExtract** | Extract content from PDF/Image/Web Page → Page[] |
| **PipeCompose** | Template text or construct objects |
| **PipeImgGen** | Generate images from text prompts |
| **PipeSearch** | Search the web for information → SearchResult |
| **PipeFunc** | Custom Python logic |

> **Critical — PipeCondition requires a `default_outcome` field**: The `default_outcome` field is **required** for PipeCondition, even when the outcomes appear exhaustive (e.g., a boolean-like `"yes"`/`"no"` split). Set it to `"continue"` to pass the output through unchanged, or to one of the outcome pipes as a safe default.

> **Critical — PipeImgGen requires a `prompt` field**: The `prompt` field is **required** for PipeImgGen. It is a template that defines the text sent to the image generation model — use `$variable` syntax to insert inputs. Examples:
> - Direct passthrough: `prompt = "$img_prompt"` — uses the input as-is
> - Template with context: `prompt = "A black and white sketch of $description"` — wraps the input in a richer prompt
>
> Even if the input already contains the full prompt text, you must still declare the `prompt` field. Without it, validation fails with `missing required fields: 'prompt'`.

> **Note**: `Page[]` outputs from PipeExtract automatically convert to text when inserted into prompts using `@variable`.

**Show detailed flow** — see [Build Phases](references/build-phases.md#phase-5-controller-flow-patterns) for all controller flow patterns.

**Output**: Flow draft with pipe contracts (markdown)

---

## Phase 6: Review & Refine

**Goal**: Validate consistency before structuring.

Check:
- [ ] Main pipe is clearly identified and handles method inputs
- [ ] Variable names are consistent across all pipes
- [ ] Input/output types match between connected pipes
- [ ] PipeSequence steps: each step has `result` (required) — no `inputs` field on steps (data flows through working memory)
- [ ] PipeSequence batch steps: `batch_as` (singular) differs from `batch_over` (plural)
- [ ] PipeSequence batch steps: `batch_over` supports dotted paths for nested attributes (e.g., `"search_result.sources"` to iterate over sources inside a SearchResult)
- [ ] PipeBatch branches receive singular items, not lists
- [ ] PipeBatch: `input_item_name` (singular) differs from `input_list_name` (plural) and all `inputs` keys
- [ ] PipeCondition has a `default_outcome` — required even when outcomes seem exhaustive
- [ ] PipeImgGen has a `prompt` field (template that references inputs, e.g., `prompt = "$description"` or `prompt = "A watercolor painting of $subject"`) — required even when the input IS the prompt
- [ ] PipeImgGen inputs are text-compatible (add PipeLLM if needed to craft the prompt first)
- [ ] No circular dependencies

**Confirm with user** before proceeding to structuring.

---

## Phase 7: Structure Pipes

**Goal**: Convert pipe drafts to validated TOML using the CLI.

**Omit `model` by default** — a default model is used automatically and handles most cases. Only set `model` when the pipe clearly needs a specialized model (e.g., vision, code analysis, high-quality image generation) or when the user explicitly requests a specific model. See [Model References](references/model-references.md) for the reference kinds and decision guide.

To look up available models when needed:
```bash
# get list of presets and model aliases:
mthds-agent models --type llm
mthds-agent models --type extract
mthds-agent models --type img_gen
mthds-agent models --type search
```

If the user asks for a specific model but the request is ambiguous, use `check-model` to resolve it:
```bash
mthds-agent check-model "<user's request>" --type llm
```

Prepare JSON specs for all pipes, then convert them **in parallel** by making multiple concurrent tool calls.

> **Required `--spec` JSON fields**: `type`, `pipe_code`, `description` (short phrase), and optionally `model` for PipeLLM, PipeExtract, PipeImgGen, PipeSearch.

> **PipeImgGen `prompt` is required**: The `prompt` field must be included in the `--spec` JSON. It is a template — use `$variable` to insert inputs. Examples: `"prompt": "$img_prompt"` (passthrough) or `"prompt": "A black and white sketch of $description"` (template with context). Omitting `prompt` causes a validation error.

For detailed CLI examples for each pipe type (PipeLLM, PipeSequence, PipeBatch, PipeCondition, PipeCompose, PipeParallel, PipeExtract, PipeImgGen, PipeSearch), see [Build Phases](references/build-phases.md#phase-7-pipe-type-cli-examples).

**Output**: Validated pipe TOML (raw TOML output, held in context for Phase 8)

> **Partial failures**: Fix failing specs using the error message. Re-run only the failed commands.

---

## Phase 8: Assemble Bundle

**Goal**: Combine all parts into a complete .mthds file.

**Save location**: Always save method bundles to `mthds-wip/`. Do not ask the user for the save location.

**Procedure**:

1. **Create the output directory**: `mkdir -p mthds-wip/<bundle_dir>/`
2. **Compose the `.mthds` file** by combining the CLI-validated TOML fragments from Phases 4 and 7 (this is deterministic assembly, not manual authoring), using this structure:

```toml
domain = "<domain>"
description = "<description>"
main_pipe = "<main_pipe_code>"

# Concept TOML from Phase 4
[concept.MyInput]
# ...

# Pipe TOML from Phase 7
[pipe.main_pipe_code]
# ...
```

3. **Write the file** using the **Write** tool to `mthds-wip/<bundle_dir>/bundle.mthds` — this triggers the PostToolUse hook for automatic lint/format/validate.

No intermediate files are needed. The `concept --spec` and `pipe --spec` commands (Phases 4 and 7) already validated each fragment — assembly is just combining them with the bundle header.

For the full `.mthds` file structure, see [Build Phases](references/build-phases.md#phase-8-assemble-bundle).

---

## Phase 9: Validate & Test

**Goal**: Ensure the bundle is valid and works correctly.

Always use `-L` pointing to the bundle's own directory to avoid namespace collisions with other bundles in the project.

```bash
# Validate and generate flowchart (isolated from other bundles)
mthds-agent validate bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/ --graph

# Generate example inputs
mthds-agent inputs bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/
```

On success, `dry_run.html` is saved next to the bundle. The JSON output includes the path in `graph_files`.

Fix any validation errors and re-validate.

---

## Phase 10: Deliver

**Goal**: Generate input template after a successful build.

After validation passes (Phase 9), generate the input template:

```bash
# Input template (extracts the input schema as JSON)
mthds-agent inputs bundle <mthds_file> -L <output_dir>/
```

Replace `<mthds_file>` and `<output_dir>` with actual paths from the build output.

### Present Results

After the command succeeds:

1. **Input schema**: Show the `inputs` JSON from the command output so the user can see what the method expects. **Do NOT save it to `inputs.json`** — input preparation is handled exclusively by `/mthds-inputs`.

2. **Flowchart**: Tell the user that an interactive flowchart (`dry_run.html`) was generated during validation next to the bundle.

3. **Next steps — test with mock inference**: Suggest a dry run to verify the method structure works:
   > To test this method with mock inference (no real inputs needed):
   > ```
   > mthds-agent run bundle <output_dir>/ --dry-run --mock-inputs
   > ```

4. **Next steps — prepare inputs and run**:
   > To prepare inputs for a real run, use `/mthds-inputs`. It can generate a placeholder template, create synthetic test data, or integrate your own files. Then:
   > ```
   > mthds-agent run bundle <output_dir>/
   > ```

   Replace `<output_dir>` with the actual output directory path used throughout the build.

> **NEVER write `inputs.json` manually.** If the user provides files, paths, or asks to run with real data, you MUST invoke `/mthds-inputs` — it handles path resolution (paths must be relative to `inputs.json`, not CWD), placeholder formatting, file copying, and multiple input strategies. Writing `inputs.json` by hand bypasses all of this and produces broken paths.

---

## Quick Reference

### Multiplicity Notation
- `Text` - single item
- `Text[]` - variable-length list
- `Text[3]` - exactly 3 items

### Prompt Variables
- `@variable` - Block insertion (multi-line, with delimiters)
- `$variable` - Inline insertion (short text)
- `@?variable` - Conditional block insertion (only renders if variable is truthy)
- `$var.field` - Access nested field (dotted paths work with all three patterns)
- Raw Jinja2 `{{ }}` / `{% %}` also supported
- These work in PipeLLM, PipeImgGen, PipeSearch, and PipeCompose templates

### Naming Conventions
- **Domain**: `snake_case`
- **Concepts**: `PascalCase`, singular
- **Pipes**: `snake_case`
- **Variables**: `snake_case`

---

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read when writing or modifying .mthds TOML syntax
- [Native Content Types](../shared/native-content-types.md) — read when using `$var.field` in prompts or `from` in construct blocks, to know which attributes each native concept exposes
- [Build Phases](references/build-phases.md) — read for detailed flow descriptions and CLI examples per phase
- [Model References](references/model-references.md) — read when choosing whether and how to set a model on a pipe
