# Vibe Cheat Sheet — Writing `.mthds` Directly

A focused, copy-pasteable reference for hand-writing MTHDS code in a `bundle.mthds`.

## 1. Bundle Skeleton

```toml
domain = "snake_case_domain"          # required — namespace for all concepts and pipes
description = "What this bundle does" # optional
main_pipe = "main_pipe_code"          # optional but recommended — entry point

# system_prompt = """                 # optional — default system prompt for all PipeLLM pipes
# You are a careful assistant.
# """

[concept]
# Simple concepts go here (one-liner descriptions)

# [concept.StructuredConcept]
# Structured concepts go in their own table

[pipe.main_pipe_code]
# Each pipe gets its own [pipe.<pipe_code>] table
```

**Naming rules:**
- `domain` — `snake_case`, may have dots (e.g. `legal.contracts`). Reserved first segments: `native`, `mthds`, `pipelex`.
- Concept codes — `PascalCase`, singular, no adjectives (`Invoice`, not `Invoices` or `LargeInvoice`).
- Pipe codes — `snake_case`.
- Input names — `snake_case`.

**Ordering convention:** main pipe (controller) first, then sub-pipes in execution order. Concepts can come before or after pipes.

## 2. Concepts

Two ways to declare a concept. Pick one per concept.

### 2a. Simple Concept (no structure)

Use the flat `[concept]` table, one line per concept:

```toml
[concept]
Topic = "A subject or theme that can be used as the basis for a joke"
Joke = "A humorous one-liner intended to make people laugh"
```

A simple concept has no fields. It's just a named type.

### 2b. Concept that Refines a Native Concept

A refining concept gets a `[concept.<Code>]` table with `refines`:

```toml
[concept.Topic]
description = "A subject or theme that can be used as the basis for a joke"
refines = "Text"
```

Refinement means substitutability: any pipe that accepts `Text` also accepts `Topic`.

`refines` accepts:
- bare code: `"Text"`
- domain-qualified: `"legal.ContractClause"`
- cross-package: `"acme->legal.ContractClause"`

### 2c. Structured Concept (fields)

Define fields in a `[concept.<Code>.structure]` sub-table:

```toml
[concept.Invoice]
description = "A commercial invoice"

[concept.Invoice.structure]
invoice_number = { type = "text", description = "Unique identifier", required = true }
issue_date     = { type = "date", description = "Issue date", required = true }
total_amount   = { type = "number", description = "Total amount due", required = true }
notes          = { type = "text", description = "Free-text notes" }
```

**Constraint:** `refines` and `structure` are mutually exclusive — pick one.

### 2d. Field Blueprint Reference

| Attribute | Required | Description |
|-----------|----------|-------------|
| `description` | Yes | Human-readable description of the field. |
| `type` | Conditional | Field type. Required unless `choices` is given. |
| `required` | No | Default `false`. |
| `default_value` | No | Must match `type`. Not allowed on `concept` or `list`. |
| `choices` | No | List of allowed string values (enum-like). |
| `concept_ref` | Conditional | Required when `type = "concept"`. |
| `item_type` | Conditional | Required when `type = "list"`. |
| `item_concept_ref` | Conditional | Required when `item_type = "concept"`. |

**Supported field types** (use exactly these strings):

| Type | Default value example |
|------|----------------------|
| `"text"` | `"hello"` |
| `"integer"` | `42` |
| `"number"` | `3.14` |
| `"boolean"` | `true` |
| `"date"` | (datetime literal) |
| `"concept"` | not allowed |
| `"list"` | not allowed |

> **Not supported by this skill:** `dict` fields. Model the data as a structured concept instead.

### 2e. Concept References in Fields

```toml
[concept.Order.structure]
customer = { type = "concept", concept_ref = "Customer", description = "The buying customer" }
items    = { type = "list", item_type = "concept", item_concept_ref = "LineItem", description = "Order line items" }
tags     = { type = "list", item_type = "text", description = "Free-form tags" }
```

Rules:
- `concept_ref` only when `type = "concept"`.
- `item_concept_ref` only when `item_type = "concept"`.
- Bare codes resolve to the current bundle's domain. Use `domain.ConceptCode` for cross-domain refs.

### 2f. Choices (enum-like)

```toml
[concept.Order.structure]
status   = { choices = ["pending", "processing", "shipped", "delivered"], description = "Order status", required = true }
priority = { type = "text", choices = ["low", "medium", "high"], description = "Priority" }
score    = { type = "number", choices = ["0", "0.5", "1"], description = "Half-point score" }
```

When `choices` is set and `type` is omitted, type defaults to `text`. `choices` is only valid with `text`, `integer`, or `number`. Not valid with `boolean`, `date`, `concept`, or `list`.

## 3. Native Concepts (always available)

Use bare or qualified (`native.Text`) — bare wins on resolution. Never redeclare a native concept code.

| Code | When to use |
|------|-------------|
| `Text` | A string. |
| `Image` | A binary image (JPEG, PNG, ...). |
| `Document` | Any document (PDF, Word, web page URL). |
| `Page` | A single extracted page (`text_and_images`, `page_view`). |
| `Html` | HTML content. |
| `TextAndImages` | Mixed text + images. |
| `Number` | A numeric value. |
| `JSON` | A JSON value. |
| `SearchResult` | Web search output (`answer`, `sources`). |
| `Anything` | Any type. |
| `Dynamic` | Dynamically typed value. |

> File formats like "PDF" or "JPEG" are NOT concepts. Use `Document` and `Image` respectively.

## 4. Multiplicity

Applies to `inputs` values and `output`:

| Syntax | Meaning |
|--------|---------|
| `ConceptName` | Single item. |
| `ConceptName[]` | Variable-length list. |
| `ConceptName[N]` | Exactly N items. |

Examples: `Text`, `Text[]`, `Image[3]`, `legal.Clause[]`. Nesting is forbidden — no `Text[][]`.

## 5. Pipe Skeleton

Every pipe gets a `[pipe.<pipe_code>]` table with these base fields:

```toml
[pipe.my_pipe]
type        = "PipeLLM"         # one of the types below
description = "What it does"
inputs      = { x = "Text", y = "Document[]" }
output      = "Summary"
# ...plus type-specific fields
```

- `type`, `description`, `output` are required for every pipe.
- `inputs` is optional in the schema but almost always present. Keys are `snake_case`, values are concept refs with optional multiplicity. Keep on a single line.

## 6. Pipe Type Reference

### PipeLLM — generate text or structured output via an LLM

```toml
[pipe.summarize]
type        = "PipeLLM"
description = "Summarize a document"
inputs      = { document = "Document" }
output      = "Summary"
prompt      = """
Summarize the following document:

@document
"""
# system_prompt = "You are a careful summarizer."   # optional, overrides bundle-level
# model = "$writing-factual"                        # optional
```

**Type-specific fields:** `prompt` (almost always required), `system_prompt` (optional), `model` (optional).

**Multi-output:** `output = "Idea[3]"` (exactly 3), `output = "Idea[]"` (variable).

**Vision:** put an `Image` in `inputs` and reference it as `$image` or `@image` in the prompt.

### PipeSequence — execute steps in order

```toml
[pipe.process_invoice]
type        = "PipeSequence"
description = "Extract then analyze"
inputs      = { document = "Document" }
output      = "InvoiceData"
steps = [
    { pipe = "extract_text", result = "pages" },
    { pipe = "analyze_invoice", result = "invoice_data" },
]
```

**Step blueprint:**
- `pipe` — bare pipe code (no domain prefix).
- `result` — the working-memory name for this step's output.
- `batch_over` + `batch_as` — optional inline batch (see below). Must both be present or both absent.

**Inline batch step:**

```toml
steps = [
    { pipe = "process_item", batch_over = "items", batch_as = "item", result = "processed" },
]
```

`batch_as` (singular) MUST differ from `batch_over` (plural). `batch_over` supports dotted paths (e.g. `"search_result.sources"`).

**Steps have NO `inputs` field.** Each step automatically sees the sequence's inputs and all earlier steps' `result` values.

### PipeBatch — map one pipe over each item in a list

```toml
[pipe.process_all_documents]
type             = "PipeBatch"
description      = "Process each document in the list"
inputs           = { documents = "Document[]", context = "Context" }
output           = "Summary[]"
branch_pipe_code = "summarize_document"
input_list_name  = "documents"
input_item_name  = "document"
```

**Required:** `branch_pipe_code`, `input_list_name`, `input_item_name`.

**Constraints:**
- `input_item_name` MUST differ from `input_list_name`.
- `input_item_name` MUST NOT match any other key in `inputs`.
- For non-batched inputs (passed through to the branch), use singular types (e.g. `context = "Context"`, NOT `"Context[]"`).

### PipeParallel — run branches concurrently

```toml
[pipe.analyze_all_aspects]
type            = "PipeParallel"
description     = "Run sentiment and topics analyses in parallel"
inputs          = { document = "Document" }
output          = "Text"
add_each_output = true
branches = [
    { pipe = "analyze_sentiment", result = "sentiment" },
    { pipe = "extract_topics", result = "topics" },
]
```

**Required:** `branches`. At least one of `add_each_output = true` OR `combined_output = "ConceptCode"` MUST be set.

With `combined_output`, the result is bundled into the named concept whose field names MUST match the branches' `result` names.

### PipeCondition — route to a pipe based on an expression

```toml
[pipe.route_by_category]
type                       = "PipeCondition"
description                = "Route based on category"
inputs                     = { input_data = "CategorizedInput" }
output                     = "Text"
expression_template        = "{{ input_data.category }}"
default_outcome            = "process_medium"

[pipe.route_by_category.outcomes]
small  = "process_small"
medium = "process_medium"
large  = "process_large"
```

**Required:** `expression_template` (Jinja2) or `expression` (bare value) — exactly one. Plus `outcomes` and `default_outcome`.

`default_outcome` accepts a pipe code OR the special values `"fail"` (abort) or `"continue"` (pass-through, no sub-pipe).

> **Always set `default_outcome`**, even when outcomes appear exhaustive (e.g. yes/no). Validation rejects pipes without one.

### PipeCompose — template or construct output

**Template mode** (produces text):

```toml
[pipe.compose_email]
type        = "PipeCompose"
description = "Compose an email body"
inputs      = { customer = "Customer", deal = "Deal" }
output      = "Text"
template = """
Hi $customer.name,

Following up on $deal.product_name:

@deal.details
"""
```

**Construct mode** (assembles a structured concept field-by-field):

```toml
[pipe.build_invoice]
type        = "PipeCompose"
description = "Assemble an Invoice from order data"
inputs      = { order = "Order", customer = "Customer" }
output      = "Invoice"

[pipe.build_invoice.construct]
invoice_number = { template = "INV-$order.id" }
customer_name  = { from = "customer.name" }
total          = { from = "order.total" }
status         = "pending"     # literal
tags           = ["urgent"]    # literal list
```

Each construct field is one of:
- `{ from = "input.path" }` — variable reference.
- `{ template = "..." }` — Jinja2 template string with shorthands.
- A literal value (string, number, boolean, list).

**Output** in construct mode MUST be a single concept (no `[]` or `[N]`).

### PipeExtract — extract pages from a Document or Image

```toml
[pipe.extract_document]
type        = "PipeExtract"
description = "Extract content from a document"
inputs      = { document = "Document" }
output      = "Page[]"
# model = "@default-text-from-pdf"   # optional
```

**Constraints:**
- Exactly one input. Input concept SHOULD be `Document` (or refine it) or `Image`.
- Output MUST be `"Page[]"`.

For web pages, the input is still `Document` (the URL is in the `url` field). Use `model = "@default-extract-web-page"` if needed.

### PipeSearch — search the web

```toml
[pipe.search_topic]
type        = "PipeSearch"
description = "Search the web for information on a topic"
inputs      = { topic = "Text" }
output      = "SearchResult"
prompt      = "What is $topic?"
# from_date       = "2026-01-01"               # optional
# include_domains = ["reuters.com", "bbc.com"] # optional
# max_results     = 5                          # optional
```

**Required:** `prompt`. **Output** MUST be `SearchResult` or a concept that refines `SearchResult`.

### PipeImgGen — generate images

```toml
[pipe.generate_image]
type         = "PipeImgGen"
description  = "Generate an image from a prompt"
inputs       = { img_prompt = "Text" }
output       = "Image"
prompt       = "$img_prompt"
# model       = "$gen-image"           # optional
# aspect_ratio = "landscape_16_9"      # optional
```

**Required:** `prompt` (even if it's just a passthrough like `"$img_prompt"`). Declared `inputs` are injected into the `prompt` template.

**Image-to-image:** declare an `Image` (or `Image[]`) input and reference it in the `prompt`:

```toml
inputs = { ref = "Image", instruction = "Text" }
prompt = "Apply this change to $ref: $instruction"
```

Each referenced image is injected as an `[Image N]` token (reference image), bounded by the model's `max_prompt_images`.

**Aspect ratio values:** `square`, `landscape_4_3`, `landscape_3_2`, `landscape_16_9`, `landscape_21_9`, `portrait_3_4`, `portrait_2_3`, `portrait_9_16`, `portrait_9_21`.

### PipeFunc — call a registered Python function

```toml
[pipe.capitalize_text]
type          = "PipeFunc"
description   = "Uppercase the input text"
inputs        = { text = "Text" }
output        = "Text"
function_name = "my_package.text_utils.capitalize"
```

Only use this when the user has a registered function. Otherwise prefer PipeCompose or PipeLLM.

### PipeSignature — a contract-only header (forward declaration)

A `PipeSignature` declares a pipe by its **contract only** — `description`, `inputs`, `output`, and an optional `signature_for` hint — with **no implementation**. It is the C-style *forward declaration* that top-down (recursive) building relies on: commit to what a pipe takes and returns before writing how it works.

```toml
[pipe.summarize_doc]
type          = "PipeSignature"
description   = "Produce a summary of a document (contract only)."
inputs        = { doc = "Document" }
output        = "Summary"
signature_for = "PipeLLM"   # optional hint: the intended implementation type
```

**Rules:**
- **No implementation fields** — no `prompt`, `steps`, `branch_pipe_code`, `outcomes`, etc. The signature is purely the contract.
- `inputs` and `output` are declared **explicitly**, exactly as any pipe — pipes never infer `inputs` from prompt sigils. Multiplicity (`[]`, `[N]`) works as usual.
- `signature_for` records the *intended* next-level type. It is a **hint, not a binding contract** — the implementation may override it. It may **not** be `"PipeSignature"`. Omit it if unsure.

**`signature_for` → operator or controller** (the next-level decision when you expand a signature):
- **Operator (leaf)** — a single step: `PipeLLM`, `PipeExtract`, `PipeSearch`, `PipeImgGen`, `PipeCompose`, `PipeFunc`. Replace the signature with the concrete operator; that branch is done.
- **Controller (composite)** — multiple steps, iteration, branching, or parallelism: `PipeSequence`, `PipeBatch`, `PipeParallel`, `PipeCondition`. Replace the signature with the controller, wire its sub-pipes, and forward-declare each not-yet-built sub-pipe as its own `PipeSignature`.

**Header ↔ definition contract.** A concrete pipe satisfies a signature of the same code when their `inputs`/`output` match **by concept identity** — bare↔qualified (`Brief` ≡ `thisdomain.Brief`) and native (`Text` ≡ `native.Text`) spellings are equivalent, multiplicity compared structurally. Spelling need not be byte-identical, but both sides must declare `inputs`/`output` explicitly. A definition whose contract differs from its header is a hard error.

**Lenient vs strict validation:**

```bash
# Lenient — accepts reachable signatures (each mints a mock of its declared output).
# Use after each layer while signatures still remain.
mthds-agent validate bundle bundle.mthds -L dir/ --allow-signatures --graph

# Strict (default) — rejects any reachable signature. Passing == runnable.
mthds-agent validate bundle bundle.mthds -L dir/ --graph
```

A successful validate reports `pending_signatures` — the library-wide list of pipes still typed `PipeSignature` (empty when the method is complete). It is the build's todo list. Live execution of a signature always fails (`PipeSignatureNotExecutableError`), so finalize to strict before running.

## 7. Prompt Template Shorthands

Applies to: `prompt` (PipeLLM, PipeImgGen, PipeSearch), `system_prompt` (PipeLLM), `template` (PipeCompose), and `{ template = "..." }` in construct fields.

| Shorthand | Expands to | Use |
|-----------|-----------|-----|
| `$variable` | `{{ variable\|format() }}` | Inline substitution. |
| `@variable` | `{{ variable\|tag("variable") }}` | Block insertion (put on its own line). |
| `@?variable` | `{% if variable %}{{ variable\|tag("variable") }}{% endif %}` | Conditional block. |

- Dotted paths work: `$user.name`, `@doc.summary`.
- Dollar amounts (`$100`) and version-like strings (`@2.0`) are NOT matched — must start with a letter or underscore.
- Trailing dots are treated as punctuation: `$amount.` → `{{ amount|format() }}.`
- Raw Jinja2 (`{{ ... }}`, `{% ... %}`) always works alongside the shorthands.

**Validation:** every variable in a prompt MUST be a declared input (root name), and every declared input MUST be referenced in the prompt at least once.

**Structured inputs auto-expand:** `@theme` formats ALL fields of `theme`. Don't manually enumerate fields unless you need a specific one inline (`$theme.palette.primary`).

## 8. Cross-Domain References

| Item | Same-domain | Cross-domain |
|------|-------------|--------------|
| Concept | `"Invoice"` | `"finance.Invoice"` |
| Pipe (in `steps`, `branches`, `outcomes`, `branch_pipe_code`) | `"extract_text"` | `"finance.extract_text"` |

When the bundle stays in one domain (the common case), use bare names everywhere.

## 9. Formatting Rules

- Keep `inputs = { ... }` on a single line.
- Use double-quoted strings; triple-quoted `"""..."""` for multi-line prompts.
- Put the main pipe (controller) before its sub-pipes for top-down readability.
- Don't redeclare a native concept code.

## 10. Common Mistakes to Avoid

- ❌ `inputs` field on a `PipeSequence` step — steps see the sequence's inputs automatically.
- ❌ Adjectives or circumstances in concept names (`LongArticle`, `CounterArgument`).
- ❌ Plural concept names (`Invoices` — use `Invoice` plus multiplicity).
- ❌ Domain prefix on pipe references when staying in-domain (`finance.extract_text` → `extract_text`).
- ❌ Omitting `prompt` on `PipeImgGen` because "the input is already a prompt" — `prompt = "$img_prompt"` is still required.
- ❌ Omitting `default_outcome` on `PipeCondition` because outcomes "look exhaustive" — still required.
- ❌ `combined_output` on `PipeParallel` without matching field names in the target concept.
- ❌ Using `dict` field type — unsupported in this skill.
- ❌ Using `PipeStructure` — not in the builder subset; use `PipeLLM` with a structured output concept instead.
- ❌ `default_value` on `concept`- or `list`-typed fields — not allowed.
- ❌ Referencing a variable in a prompt without declaring it in `inputs` — validation will fail.
- ❌ Declaring an `input` that no prompt references — also rejected.
- ❌ Adding implementation fields (`prompt`, `steps`, …) to a `PipeSignature` — it is contract-only.
- ❌ `signature_for = "PipeSignature"` — must name a real implementation type, or omit it entirely.
- ❌ A definition whose `inputs`/`output` contract differs from its header's — they must match by concept identity.

## 11. End-to-End Example

```toml
domain      = "joke_generation"
description = "Generating one-liner jokes from topics"
main_pipe   = "generate_jokes_from_topics"

[concept.Topic]
description = "A subject or theme that can be used as the basis for a joke"
refines     = "Text"

[concept.Joke]
description = "A humorous one-liner intended to make people laugh"
refines     = "Text"

[pipe.generate_jokes_from_topics]
type        = "PipeSequence"
description = "Generate 3 joke topics and create a joke for each"
output      = "Joke[]"
steps = [
    { pipe = "generate_topics", result = "topics" },
    { pipe = "batch_generate_jokes", result = "jokes" },
]

[pipe.generate_topics]
type        = "PipeLLM"
description = "Generate 3 distinct topics suitable for jokes"
output      = "Topic[3]"
prompt      = "Generate 3 distinct and varied topics for crafting one-liner jokes."

[pipe.batch_generate_jokes]
type             = "PipeBatch"
description      = "Generate a joke for each topic"
inputs           = { topics = "Topic[]" }
output           = "Joke[]"
branch_pipe_code = "generate_joke"
input_list_name  = "topics"
input_item_name  = "topic"

[pipe.generate_joke]
type        = "PipeLLM"
description = "Write a clever one-liner joke about the given topic"
inputs      = { topic = "Topic" }
output      = "Joke"
prompt      = "Write a clever one-liner joke about $topic. Be concise and witty."
```
