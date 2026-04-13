# Native Content Types Reference

Each native concept maps to a content class with specific attributes. Understanding these attributes helps when:

- Writing `$var.field` references in prompts or PipeCompose templates
- Building `construct` blocks with `from = "input.field"`
- Interpreting pipeline outputs (e.g., what comes out of PipeExtract)
- Preparing input JSON for `mthds-agent run`

## Content Type Summary

| Native Concept | Content Class | Key Attributes |
|----------------|---------------|----------------|
| `Text` | TextContent | `text` |
| `Number` | NumberContent | `number` |
| `Image` | ImageContent | `url`, `filename`, `caption`, `mime_type`, `size` |
| `Document` | DocumentContent | `url`, `public_url`, `filename`, `mime_type`, `title`, `snippet` |
| `Html` | HtmlContent | `inner_html`, `css_class` |
| `TextAndImages` | TextAndImagesContent | `text` (TextContent), `images` (list of ImageContent) |
| `Page` | PageContent | `text_and_images` (TextAndImagesContent), `page_view` (ImageContent) |
| `JSON` | JSONContent | `json_obj` |
| `ImgGenPrompt` | *(refines Text)* | `text` |
| `SearchResult` | SearchResultContent | `answer`, `sources` (list of DocumentContent) |
| `Anything` | *(any content)* | depends on actual content |
| `Dynamic` | DynamicContent | user-defined fields |

## Detailed Attribute Reference

### Text — `TextContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | The text content |

**Access**: `$var` or `$var.text` in prompts.

---

### Number — `NumberContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `number` | `int \| float` | The numeric value |

**Access**: `$var` or `$var.number` in prompts.

---

### Image — `ImageContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Image location: storage URL, HTTP/HTTPS URL, or base64 data URL |
| `filename` | `str \| None` | no | Original filename (auto-populated from URL if not set) |
| `caption` | `str \| None` | no | Image caption or description |
| `mime_type` | `str \| None` | no | MIME type (e.g., `image/jpeg`, `image/png`) |
| `size` | `ImageSize \| None` | no | Pixel dimensions: `size.width` and `size.height` |
| `public_url` | `str \| None` | no | Public HTTPS URL for display |
| `source_prompt` | `str \| None` | no | The prompt used to generate this image (if AI-generated) |

**Access**: `$image.filename`, `$image.caption`, `$image.url` in prompts. Use `$image` alone in PipeLLM prompts for vision (image is sent to the LLM as a visual input).

---

### Document — `DocumentContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Document location: storage URL, HTTP/HTTPS URL (including web page URLs for extraction), or base64 data URL |
| `public_url` | `str \| None` | no | Public HTTPS URL for display |
| `mime_type` | `str \| None` | no | MIME type (defaults to `application/pdf`) |
| `filename` | `str \| None` | no | Original filename (auto-populated from URL if not set) |
| `title` | `str \| None` | no | Title of the document or source |
| `snippet` | `str \| None` | no | Text snippet or excerpt from the document |

**Access**: `$document.filename`, `$document.url` in prompts. Documents cannot be sent directly to LLMs — use PipeExtract first to get Page[] content. For web page URLs, use PipeExtract with `@default-extract-web-page` model.

---

### Html — `HtmlContent`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `inner_html` | `str` | yes | The inner HTML content |
| `css_class` | `str` | yes | CSS class for the wrapping div |

**Access**: `$html.inner_html` in prompts.

---

### TextAndImages — `TextAndImagesContent`

Composite content holding text and associated images. Typically produced by PipeExtract.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | `TextContent \| None` | no | The text portion (has `.text` attribute) |
| `images` | `list[ImageContent] \| None` | no | List of images extracted alongside the text |

**Access**: `$var.text` gets the TextContent, `$var.images` gets the image list. When used with `@var` in a prompt, the text is auto-rendered.

---

### Page — `PageContent`

Represents a single page extracted from a document. Produced by PipeExtract when output is `Page[]`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `text_and_images` | `TextAndImagesContent` | yes | The text and images extracted from the page |
| `page_view` | `ImageContent \| None` | no | Screenshot/visual render of the page |

**Access**: When `@page` is used in a PipeLLM prompt, the text content is auto-rendered and images are sent as visual inputs. `$page.text_and_images.text.text` drills to the raw text.

---

### JSON — `JSONContent`

| Attribute | Type | Description |
|-----------|------|-------------|
| `json_obj` | `dict[str, Any]` | The JSON object (must be a valid JSON-serializable dict) |

**Access**: `$var.json_obj` in prompts. Fields within the JSON object can be accessed with dot notation if the concept is structured.

---

### SearchResult — `SearchResultContent`

Represents the result of a web search query. Produced by PipeSearch.

| Attribute | Type | Description |
|-----------|------|-------------|
| `answer` | `str` | The synthesized answer text from the search |
| `sources` | `list[DocumentContent]` | List of source citations (each is a DocumentContent with `url`, `title`, `snippet`) |

Each source is a `DocumentContent` with:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | Source URL |
| `title` | `str \| None` | no | Source title |
| `snippet` | `str \| None` | no | Relevant excerpt from the source |

**Access**: `$result.answer` for the answer text, `$result.sources` for the source list. When used with `@result` in a prompt, the answer and sources are auto-rendered.

**Pattern — fetch source content**: Since sources are `DocumentContent`, you can feed them into PipeExtract with `@default-extract-web-page` to extract the full page into `Page[]` content (pages can contain images and text, most often formatted as markdown). Use `batch_over` with dot notation to iterate over all sources in a PipeSequence:

```toml
# Step 1: Search the web
[pipe.search_topic]
type = "PipeSearch"
description = "Search the web for information"
inputs = { topic = "Text" }
output = "SearchResult"
model = "$standard"
prompt = "What is $topic?"

# Step 2: Extract full content from a single source URL
[pipe.fetch_source]
type = "PipeExtract"
description = "Fetch full page content from a source URL"
inputs = { document = "Document" }
output = "Page[]"
model = "@default-extract-web-page"

# Step 3: Analyze the fetched content
[pipe.analyze_source]
type = "PipeLLM"
description = "Analyze the fetched source content"
inputs = { pages = "Page[]" }
output = "SourceAnalysis"
prompt = """
Analyze the following web page content:

@pages
"""

# Controller: search, then batch-fetch and analyze each source
[pipe.research_topic]
type = "PipeSequence"
description = "Search the web, fetch each source, and analyze"
inputs = { topic = "Text" }
output = "SourceAnalysis[]"
steps = [
    { pipe = "search_topic", result = "search_result" },
    { pipe = "fetch_source", batch_over = "search_result.sources", batch_as = "document", result = "fetched_pages" },
    { pipe = "analyze_source", batch_over = "fetched_pages", batch_as = "pages", result = "analysis" }
]
```

The key insight: `batch_over = "search_result.sources"` uses dot notation to iterate over the `sources` list inside the SearchResult. Each source is a `DocumentContent` with a `url` field, so it can be passed directly to PipeExtract as a web page URL. Batching does not propagate automatically — each step that should iterate needs its own `batch_over`.

---

### ListContent (multiplicity `[]`)

When a concept has `[]` multiplicity (e.g., `Page[]`, `Image[]`), the content is a `ListContent` wrapping a list of items:

| Attribute | Type | Description |
|-----------|------|-------------|
| `items` | `list[StuffContent]` | The list of content items |
| `nb_items` | `int` (property) | Number of items in the list |

ListContent supports iteration (`for item in list_content`), indexing (`list_content[0]`), and `len()`.

---

## Common Patterns

### PipeExtract output chain

PipeExtract produces `Page[]` — a list of pages. Each page contains `text_and_images` (text + images from OCR/extraction) and optionally `page_view` (a screenshot). To use extracted content in an LLM prompt:

```toml
# Extract pages from a document
[pipe.extract_pages]
type = "PipeExtract"
inputs = { document = "Document" }
output = "Page[]"

# Extract pages from a web page URL
[pipe.extract_web_content]
type = "PipeExtract"
inputs = { web_page = "Document" }
output = "Page[]"
model = "@default-extract-web-page"

# Analyze the extracted pages — @pages auto-renders all page text
[pipe.analyze]
type = "PipeLLM"
inputs = { pages = "Page[]" }
output = "Analysis"
prompt = """
Analyze this document:

@pages
"""
```

### Accessing nested fields in PipeCompose

```toml
[pipe.build_summary.construct]
source_file = { from = "document.filename" }
image_count = { template = "$report.images" }
page_text = { from = "page.text_and_images.text.text" }
```

### Input JSON structure for each type

```json
{
  "my_text": {"concept": "native.Text", "content": {"text": "Hello"}},
  "my_number": {"concept": "native.Number", "content": {"number": 42}},
  "my_image": {"concept": "native.Image", "content": {"url": "/path/to/img.jpg", "mime_type": "image/jpeg"}},
  "my_document": {"concept": "native.Document", "content": {"url": "/path/to/doc.pdf"}},
  "my_json": {"concept": "native.JSON", "content": {"json_obj": {"key": "value"}}},
  "my_search_result": {"concept": "native.SearchResult", "content": {"answer": "The answer text", "sources": [{"url": "https://example.com", "title": "Source 1", "snippet": "Relevant excerpt"}]}}
}
```
