# Model References

The `model` field on pipe specs (PipeLLM, PipeExtract, PipeImgGen, PipeSearch) selects which model to use for that pipe.

## When to set `model`

The `model` field is **optional**. Omitting it uses sensible defaults that work for most cases.

**Set `model` only when:**
- The operation clearly needs a specialized model (e.g., vision capabilities, code analysis, high-quality image generation)
- The user explicitly asks for a specific model or provider

**Omit `model` when:**
- The pipe does a standard text generation, extraction, search, or image generation task
- No special model capabilities are needed
- The user has no model preference

## Reference Kinds

When you do set `model`, use one of these reference kinds:

| Kind | Sigil | Example | Use Case |
|------|-------|---------|----------|
| **Preset** | `$` | `$writing-creative` | Bundles model + settings (most common) |
| **Alias** | `@` | `@best-claude` | Stable names for retargeting |
| **Waterfall** | `~` | `~robust-llm` | Ordered fallback chains |
| **Handle** | (none) | `gpt-4o` | Direct model name |

Presets (`$`) are the recommended choice — they bundle a model with appropriate settings for a task.

## Discovering Available Models

Look up what's available in the current environment:

```bash
mthds-agent models                         # All models
mthds-agent models --type llm              # Filter by category
mthds-agent models --type extract
mthds-agent models --type img_gen
mthds-agent models --type search
mthds-agent models --backend openai        # Filter by provider
mthds-agent models --type llm -b anthropic # Combine both filters
```

## Validating an Ambiguous Request

If the user asks for a specific model but the request doesn't obviously match a known preset or alias, use `check-model` to resolve it:

```bash
mthds-agent check-model "$writing-creative" --type llm
mthds-agent check-model "@best-claude" --type llm
mthds-agent check-model "gpt-4o" --type llm
```

If the reference is invalid, `check-model` returns fuzzy suggestions ("Did you mean?") and wrong-sigil hints (e.g., "best-claude exists as @best-claude").

## Examples in .mthds Files

```toml
# Default model (omit the field entirely):
[pipe.summarize]
type = "PipeLLM"
inputs = { document = "Text" }
output = "Text"
prompt = "Summarize:\n\n@document"

# Explicit model when needed:
[pipe.analyze_code]
type = "PipeLLM"
inputs = { code = "Text" }
output = "Analysis"
model = "$engineering-code"
prompt = "Analyze this code:\n\n@code"
```

## Examples in `--spec` JSON

```bash
# Default model (omit "model" from the spec):
mthds-agent pipe --spec '{"type": "PipeLLM", "pipe_code": "summarize", ...}'

# Explicit model:
mthds-agent pipe --spec '{"type": "PipeLLM", "pipe_code": "analyze_code", "model": "$engineering-code", ...}'
```
