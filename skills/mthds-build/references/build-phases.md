# Build Phases — Detailed Examples

Detailed examples and CLI commands for each phase of the 9-phase build process. See `mthds-build/SKILL.md` for the concise process.

## Phase 2: Bundle Overview

The bundle declares a `domain` and a `main_pipe`. All declared inputs flow into the main pipe (typically a PipeSequence), which orchestrates sub-pipes and produces the final output.

## Phase 5: Controller Flow Patterns

### Sequence Flow
Steps execute in order. Each step receives the prior step's result and produces its own:
Step 1 (PipeLLM) -> `analysis` -> Step 2 (PipeLLM) -> `refined` -> Step 3 (Compose) -> `output`

### Batch Flow (map operation)
PipeBatch takes an input list (`input_list_name`), fans out one invocation of the branch pipe per item, then collects all results into an output array.

### Parallel Flow
Input feeds into all branches simultaneously. Each branch runs independently, and all branch outputs merge into a single combined result.

### Condition Flow
Input is evaluated against an expression. The matching case routes to its corresponding pipe. Unmatched values route to the default pipe.

## Phase 7: Pipe Type CLI Examples

> **JSON spec field names** (use exactly these in `--spec` JSON):
> - `type` — pipe type (e.g. `"PipeLLM"`)
> - `pipe_code` — unique pipe identifier
> - `description` — **required** on every pipe. Short phrase describing what the pipe does.
> - `model` — (optional) model reference for PipeLLM, PipeExtract, PipeImgGen, PipeSearch. Omit to use defaults.

### PipeLLM
```bash
# Default model (omit "model" for standard tasks):
mthds-agent pipe --spec '{
  "type": "PipeLLM",
  "pipe_code": "summarize_document",
  "description": "Summarize document content",
  "inputs": {"document": "Document"},
  "output": "Summary",
  "prompt": "Summarize this document:\n\n@document"
}'

# Explicit model when specialized capabilities are needed:
mthds-agent pipe --spec '{
  "type": "PipeLLM",
  "pipe_code": "analyze_code",
  "description": "Analyze source code",
  "inputs": {"code": "Text"},
  "output": "Analysis",
  "model": "$engineering-code",
  "prompt": "Analyze this code:\n\n@code"
}'
```

### PipeSequence
```bash
mthds-agent pipe --spec '{
  "type": "PipeSequence",
  "pipe_code": "process_invoice",
  "description": "Full invoice processing",
  "inputs": {"document": "Document"},
  "output": "InvoiceData",
  "steps": [
    {"pipe": "extract_text", "result": "pages"},
    {"pipe": "analyze_invoice", "result": "invoice_data"}
  ]
}'
```

> **Step fields**: `pipe` and `result` are required on every step. Steps do not accept `inputs` — each step automatically sees the sequence's inputs and all previous `result` variables.

### PipeBatch
```bash
mthds-agent pipe --spec '{
  "type": "PipeBatch",
  "pipe_code": "process_all_items",
  "description": "Process each item in list",
  "inputs": {"items": "Item[]", "context": "Context"},
  "output": "Result[]",
  "branch_pipe_code": "process_single_item",
  "input_list_name": "items",
  "input_item_name": "item"
}'
```

**Note**: `input_item_name` must differ from both `input_list_name` and all keys in `inputs`. Convention: use a plural noun for the list (e.g., `"items"`) and its singular form for the item (e.g., `"item"`).

### PipeCondition
```bash
mthds-agent pipe --spec '{
  "type": "PipeCondition",
  "pipe_code": "route_by_type",
  "description": "Route based on document type",
  "inputs": {"document": "ClassifiedDocument"},
  "output": "ProcessedDocument",
  "expression": "document.doc_type",
  "outcomes": {"invoice": "process_invoice", "receipt": "process_receipt"},
  "default_outcome": "process_generic"
}'
```

> **Note**: The `default_outcome` field is **required** for PipeCondition, even when the outcomes appear exhaustive (e.g., a boolean-like `"yes"`/`"no"` split). It specifies the fallback pipe when no outcome matches. Set it to `"continue"` to pass the output through unchanged, or to one of the outcome pipes as a safe default.

### PipeCompose — Template mode (via CLI)
```bash
mthds-agent pipe --spec '{
  "type": "PipeCompose",
  "pipe_code": "format_report",
  "description": "Format final report",
  "inputs": {"summary": "Summary", "details": "Details"},
  "output": "Text",
  "target_format": "markdown",
  "template": "# Report\n\n$summary\n\n## Details\n\n@details"
}'
```

### PipeCompose — Construct mode (write directly to .mthds)
```toml
[pipe.build_output]
type = "PipeCompose"
description = "Assemble final output"
inputs = {analysis = "Analysis", items = "Item[]"}
output = "FinalOutput"

[pipe.build_output.construct]
summary = {from = "analysis.summary"}
score = {from = "analysis.score"}
items = {from = "items"}
label = {template = "Analysis for $analysis.name"}
version = "1.0"  # Static value
```

**Construct field methods:**
- `{from = "variable.path"}` — Reference input or nested field
- `{template = "text with $var"}` — String interpolation
- `"value"` or `123` — Static/fixed values

### PipeParallel
```bash
mthds-agent pipe --spec '{
  "type": "PipeParallel",
  "pipe_code": "analyze_all",
  "description": "Run analyses in parallel",
  "inputs": {"document": "Document"},
  "output": "CombinedAnalysis",
  "branches": [
    {"pipe": "analyze_sentiment", "result": "sentiment"},
    {"pipe": "extract_topics", "result": "topics"}
  ],
  "add_each_output": true,
  "combined_output": "CombinedAnalysis"
}'
```

**Required**: Must set either `add_each_output: true` OR `combined_output` (or both).

### PipeExtract
```bash
mthds-agent pipe --spec '{
  "type": "PipeExtract",
  "pipe_code": "extract_pages",
  "description": "Extract text from document",
  "inputs": {"document": "Document"},
  "output": "Page[]"
}'
```

### PipeExtract (Web Page)
```bash
mthds-agent pipe --spec '{
  "type": "PipeExtract",
  "pipe_code": "extract_web_page",
  "description": "Extract content from web page",
  "inputs": {"web_page": "Document"},
  "output": "Page[]",
  "model": "@default-extract-web-page"
}'
```

### PipeImgGen
```bash
mthds-agent pipe --spec '{
  "type": "PipeImgGen",
  "pipe_code": "generate_image",
  "description": "Generate image from prompt",
  "inputs": {"img_prompt": "ImgGenPrompt"},
  "output": "Image",
  "prompt": "$img_prompt"
}'
```

> **Note**: The `prompt` field is **required** for PipeImgGen. It is a template that defines the text sent to the image generation model. Use `$variable` syntax to insert inputs. Examples: `"prompt": "$img_prompt"` (direct passthrough) or `"prompt": "A black and white sketch of $description"` (template with added context). Even if your input already contains the full prompt, you must still declare the `prompt` field.

### PipeSearch
```bash
mthds-agent pipe --spec '{
  "type": "PipeSearch",
  "pipe_code": "search_topic",
  "description": "Search the web for information",
  "inputs": {"topic": "Text"},
  "output": "SearchResult",
  "prompt": "What is the latest news on $topic?"
}'

# With optional date and domain filters:
mthds-agent pipe --spec '{
  "type": "PipeSearch",
  "pipe_code": "search_recent_news",
  "description": "Search specific sources for recent news",
  "inputs": {"topic": "Text"},
  "output": "SearchResult",
  "prompt": "What are the latest developments about $topic?",
  "from_date": "2026-01-01",
  "include_domains": ["reuters.com", "apnews.com", "bbc.com"],
  "max_results": 5
}'
```

**Search-then-batch pattern** — the canonical way to search, fetch each source page, and process them individually using `batch_over` with dotted paths:

```toml
# Controller: search, then batch-fetch and analyze each source
[pipe.research_topic]
type = "PipeSequence"
description = "Search the web, fetch each source, and analyze"
inputs = { topic = "Text" }
output = "Analysis[]"
steps = [
    { pipe = "search_topic", result = "search_result" },
    { pipe = "fetch_source", batch_over = "search_result.sources", batch_as = "document", result = "fetched_pages" },
    { pipe = "analyze_source", batch_over = "fetched_pages", batch_as = "pages", result = "analyses" }
]
```

Key points:
- `batch_over = "search_result.sources"` uses a dotted path to iterate over the `sources` list nested inside the SearchResult
- Each source is a `DocumentContent` with a `url` field — feed it directly to PipeExtract
- `batch_as = "document"` must match the branch pipe's input name
- Batching does NOT propagate — each step that should iterate needs its own `batch_over`

### Parallel Conversion Example (multiple pipes at once)
```bash
# Call all pipe commands in parallel (single response, multiple tool calls):
mthds-agent pipe --spec '{"type": "PipeLLM", "pipe_code": "summarize", "description": "Summarize document", "inputs": {"document": "Document"}, "output": "Summary", "prompt": "Summarize:\n\n@document"}'
mthds-agent pipe --spec '{"type": "PipeExtract", "pipe_code": "extract_pages", "description": "Extract text from document", "inputs": {"document": "Document"}, "output": "Page[]"}'
mthds-agent pipe --spec '{"type": "PipeLLM", "pipe_code": "analyze", "description": "Analyze content", "inputs": {"pages": "Page[]"}, "output": "Analysis", "prompt": "Analyze:\n\n@pages"}'
mthds-agent pipe --spec '{"type": "PipeSequence", "pipe_code": "main_pipe_code", "description": "Main orchestration", "inputs": {"document": "Document"}, "output": "Analysis", "steps": [{"pipe": "extract_pages", "result": "pages"}, {"pipe": "analyze", "result": "analysis"}]}'
```

## Phase 8: Assemble Bundle

Compose the `.mthds` file directly from the validated TOML fragments held in context (Phases 4 and 7). No intermediate files or CLI commands are needed — write the file using the **Write** tool to `mthds-wip/<bundle_dir>/bundle.mthds`, which triggers the PostToolUse hook for automatic lint/format/validate.

The `.mthds` file structure:

```toml
domain = "my_domain"
description = "What this method does"
main_pipe = "main_pipe_code"

[concept]
MyInput = "Description of input"
MyOutput = "Description of output"

[concept.StructuredConcept]
description = "A concept with fields"

[concept.StructuredConcept.structure]
field_name = "Field description"
typed_field = { type = "number", description = "...", required = true }

[pipe.main_pipe_code]
type = "PipeSequence"
description = "Main orchestration"
inputs = { input = "MyInput" }
output = "MyOutput"
steps = [
    { pipe = "step_one", result = "intermediate" },
    { pipe = "step_two", result = "final" }
]

[pipe.step_one]
type = "PipeLLM"
description = "First step"
inputs = { input = "MyInput" }
output = "Intermediate"
model = "$engineering-structured"
prompt = "@input"
```

> **Note**: The `model` field is optional. Omit it to use defaults. Set it only when a specialized model is needed (e.g., `model = "$engineering-code"` for code analysis) or when the user requests a specific model.
