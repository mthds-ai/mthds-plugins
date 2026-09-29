---
name: mthds-inputs
description: Prepare inputs for MTHDS methods. Use when user says "prepare inputs", "create inputs", "use my files", "generate test data", "template", "synthesize inputs", "mock inputs", "I have a PDF/image/document to use", "make sample data", or wants to create inputs.json for running a .mthds pipeline. Handles user-provided files, synthetic data generation, placeholder templates, and mixed approaches. Defaults to automatic mode.
min_mthds_version: 0.22.1
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob

---

# Prepare Inputs for MTHDS methods

Prepare input data for running MTHDS method bundles. This skill is the single entry point for all input preparation needs: extracting a placeholder template, generating synthetic test data, integrating user-provided files, or any combination.

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

**Default**: Automatic.

**Input strategy detection heuristics** (evaluated in order):

| Signal | Strategy |
|--------|----------|
| User provides file paths, folder paths, or mentions "my data" / "this file" / "use these images" / "here's my PDF" | **User Data** (or Mixed if some inputs remain unfilled) |
| User says "test data" / "generate inputs" / "synthesize" / "fake data" / "sample data" | **Synthetic** |
| User says "template" / "schema" / "placeholder" / "what inputs does it need?" | **Template** |
| No clear signal (e.g., called after `/mthds-build` with no further context) | **Template**, then offer to populate |

**Interactive additions**: Ask about:
- Which user files map to which inputs (when ambiguous)
- Domain/industry context for realistic synthetic data
- Whether to generate edge cases or happy-path data
- Specific values or constraints for certain fields

---

Do not write `.mthds` files manually, do not do any other work. The CLI is required for validation, formatting, and execution — without it the output will be broken.

> **No backend setup needed**: This skill works without configuring inference backends or API keys. You can start building/validating methods right away.

---

## Process

### Step 1: Identify the Target Method

Determine the `.mthds` bundle and its output directory (`<output_dir>`). This is usually the directory containing `bundle.mthds` (e.g., `mthds-wip/pipeline_01/`).

The `inputs.json` file is saved directly in this directory (next to `bundle.mthds`):
- `<output_dir>/inputs.json`

> **Remote-storage rule (HARD).** In this environment `inputs.json` MUST reference every file by a **remote URI only** — a `pipelex-storage://` URI or an `https://` URL. **Never** a local path (not a relative `inputs/…` path, not an absolute path). The filesystem here is ephemeral and the runner is a different machine that cannot see local files and rejects local-path inputs, so a local path can never resolve at run time.
>
> For **every** file you generate or the user provides, upload it and use the returned URI:
> ```bash
> mthds-agent inputs upload <file>
> ```
> This prints a short `pipelex-storage://…` URI — put that exact string in the `url` field. A file you *generate* may be written to a local temp path first (that's just a staging step), but the **only** thing that ends up in `inputs.json` is the uploaded URI — never the temp path, and there's no need to keep an `<output_dir>/inputs/` copy.

### Step 2: Get Input Schema

Extract the input template from the method:

```bash
mthds-agent inputs bundle <bundle.mthds> -L <bundle-dir>/ [--pipe specific_pipe]
```

**Output format:**
```json
{
  "success": true,
  "pipe_code": "process_document",
  "inputs": {
    "document": {
      "concept": "native.Document",
      "content": {"url": "https://mock-xxxxxxxx.invalid/..."}
    },
    "context": {
      "concept": "native.Text",
      "content": {"text": "text_value"}
    }
  }
}
```

For error handling, see [Error Handling Reference](../shared/error-handling.md).

### Step 3: Choose Input Strategy

Based on the heuristics above and what the user has provided, follow the appropriate strategy:

- [Template Strategy](#template-strategy) — placeholder JSON, no real data
- [Synthetic Strategy](#synthetic-strategy) — AI-generated realistic test data
- [User Data Strategy](#user-data-strategy) — integrate user-provided files
- [Mixed Strategy](#mixed-strategy) — user files + synthetic for the rest

---

## Template Strategy

The fastest path. Produces a placeholder `inputs.json` that the user can fill in manually.

1. Take the `inputs` object from Step 2's output
2. For `url` fields, replace the mock URLs (e.g., `https://mock-xxxxxxxx.invalid/...`) with descriptive placeholders that explicitly tell the path resolution is relative to inputs.json, e.g:
  good: `<VARNAME-url-or-path-relative-to-this-inputs-file>` ✅ do this
  bad:  `<path-to-VARNAME>` ❌ don't do that
This placeholder means "replace with either a real URL, an absolute path, or a path relative to the saved `inputs.json` file itself," not relative to the current working directory.
This placeholder means "replace with either a real URL, an absolute path, or a path relative to the saved `inputs.json` file itself," not relative to the current working directory.
3. Save it to `<output_dir>/inputs.json` (next to `bundle.mthds`)
4. Report the saved file path and show the template content
5. Offer: "To populate this with realistic test data, re-run /mthds-inputs and ask for synthetic data. Or provide your own files."

---

## Synthetic Strategy

Generate realistic fake data tailored to the method's purpose.

### Identify Input Types

Parse the schema to identify what types of synthetic data are needed:

| Concept | Content Fields | Synthesis Method |
|---------|---------------|------------------|
| `native.Text` | `text` | Generate realistic text matching the method context |
| `native.Number` | `number` | Generate appropriate numeric values |
| `native.YesNo` | `yes_no` | Generate a boolean `true`/`false` answer |
| `native.Date` | `date`, `time?` | Generate ISO 8601 date/time values; never use epoch numbers |
| `native.Time` | `time` | Generate an ISO 8601 time of day; never use seconds-since-midnight numbers |
| `native.Image` | `url`, `caption?`, `mime_type?` | Use `synthesize_image` pipeline |
| `native.Document` | `url`, `mime_type?` | Use document generation skills or Python |
| `native.Page` | `text_and_images`, `page_view?` | Composite: text + optional images |
| `native.TextAndImages` | `text?`, `images?` | Composite: text + image list |
| `native.JSON` | `json_obj` | Generate structured JSON matching context |
| Custom structured | Per-field types | Recurse through structure fields |

**List types** (`Type[]` or `Type[N]`): Generate multiple items. Variable lists typically need 2-5 items; fixed lists need exactly N items.

### Generate Text Content

Create realistic text that matches the method's purpose:
- If the method processes invoices, generate invoice-like text
- If it analyzes reports, generate report-style content
- Match expected length (short prompts vs long documents)

### Generate Numeric Content

Generate sensible values within expected ranges based on the method context.

### Generate Structured Concepts

Fill each field according to its type and description.

### Generate File Inputs

When inputs require actual files (Image, Document), use the appropriate generation method. See [Document Generation](#document-generation) below.

### Assemble and Save

Create the complete `inputs.json` and save to `<output_dir>/inputs.json` (next to `bundle.mthds`). Any generated data file must be uploaded via `mthds-agent inputs upload <file>` and referenced in `inputs.json` by its returned `pipelex-storage://` URI — never a local path.

---

## User Data Strategy

Integrate the user's own files into the method's input schema.

### Step A: Inventory User Files

Collect all files the user has provided (explicit paths, folders, or files mentioned earlier in conversation). For each file, determine its type:

| Extension(s) | Detected Type | Maps To |
|--------------|---------------|---------|
| `.pdf` | PDF document | `native.Document` (mime: `application/pdf`) |
| `.docx`, `.doc` | Word document | `native.Document` (mime: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) |
| `.xlsx`, `.xls` | Spreadsheet | `native.Document` (mime: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) |
| `.pptx`, `.ppt` | Presentation | `native.Document` (mime: `application/vnd.openxmlformats-officedocument.presentationml.presentation`) |
| `.jpg`, `.jpeg` | JPEG image | `native.Image` (mime: `image/jpeg`) |
| `.png` | PNG image | `native.Image` (mime: `image/png`) |
| `.webp` | WebP image | `native.Image` (mime: `image/webp`) |
| `.gif` | GIF image | `native.Image` (mime: `image/gif`) |
| `.svg` | SVG image | `native.Image` (mime: `image/svg+xml`) |
| `.tiff`, `.tif` | TIFF image | `native.Image` (mime: `image/tiff`) |
| `.bmp` | BMP image | `native.Image` (mime: `image/bmp`) |
| `.txt` | Plain text | `native.Text` (read file content) |
| `.md` | Markdown text | `native.Text` (read file content) |
| `.json` | JSON data | `native.JSON` or custom structured concept |
| `.csv` | CSV data | `native.Text` (read as text) or `native.JSON` (parse to objects) |
| `.html`, `.htm` | HTML | `native.Html` |
| `http://...`, `https://...` | Web page URL | `native.Document` (mime: `text/html`) |

### Step B: Expand Folders

When the user provides a folder path:

1. List all files in the folder (non-recursive by default, recursive if user requests)
2. Filter to supported file types
3. Group files by detected type
4. Match to list-type inputs (`Image[]`, `Document[]`, etc.)

**Example**: User provides `./invoices/` containing 5 PDFs. The method expects `documents: Document[]`. Map all 5 PDFs to that list input.

### Step C: Match Files to Inputs

For each input variable in the schema, attempt to match user-provided files:

**Matching rules** (applied in order):

1. **Exact name match**: Input variable `invoice` matches a file named `invoice.pdf`
2. **Type match (single candidate)**: If only one input expects `native.Image` and the user provided exactly one image file, match them
3. **Type match (multiple candidates)**: If multiple inputs of the same type exist:
   - In **automatic mode**: match by name similarity (variable name vs filename)
   - In **interactive mode**: ask the user which file goes where
4. **Folder to list**: If a folder contains files of a single type and an input expects a list of that type, map the folder contents to that input
5. **Unmatched files**: Report them and ask if they should be ignored or mapped to a specific input
6. **Unfilled inputs**: After matching, any inputs still without data can be left as placeholders or filled with synthetic data (see [Mixed Strategy](#mixed-strategy))

### Step D: Upload Files to Remote Storage

For each user file, upload it and capture the returned `pipelex-storage://` URI:

```bash
mthds-agent inputs upload <path-to-user-file>
```

Reference that exact URI in `inputs.json` (see Step E). Do **not** copy files into an `<output_dir>/inputs/` subdirectory — a local path cannot resolve on the runner in this environment.

### Step E: Build Content Objects

For each matched file, construct the proper content object:

**Document input:**
```json
{
  "concept": "native.Document",
  "content": {
    "url": "pipelex-storage://<user>/assets/<uuid>.pdf",
    "mime_type": "application/pdf"
  }
}
```
The `url` is the exact string returned by `mthds-agent inputs upload <file>`.

**Web page Document input:**
```json
{
  "concept": "native.Document",
  "content": {
    "url": "https://example.com/article",
    "mime_type": "text/html"
  }
}
```

**Image input:**
```json
{
  "concept": "native.Image",
  "content": {
    "url": "pipelex-storage://<user>/assets/<uuid>.jpg",
    "mime_type": "image/jpeg"
  }
}
```

**Text input** (from `.txt` or `.md` file — read the file content):
```json
{
  "concept": "native.Text",
  "content": {
    "text": "<actual file content read from the .txt/.md file>"
  }
}
```

**Image list input** (from folder):
```json
{
  "concept": "native.Image",
  "content": [
    {"url": "pipelex-storage://<user>/assets/<uuid-1>.jpg", "mime_type": "image/jpeg"},
    {"url": "pipelex-storage://<user>/assets/<uuid-2>.jpg", "mime_type": "image/jpeg"},
    {"url": "pipelex-storage://<user>/assets/<uuid-3>.png", "mime_type": "image/png"}
  ]
}
```
Upload each file in the folder with `mthds-agent inputs upload <file>` and use the returned URIs.

### Step F: Assemble and Save

Combine all content objects into a single `inputs.json` and save to `<output_dir>/inputs.json` (next to `bundle.mthds`).

### Step G: Report

Show the user:
- Which files were matched to which inputs
- Any unfilled inputs (offer synthetic or placeholder)
- The final `inputs.json` content
- Path to the saved file

---

## Mixed Strategy

Combines user data with synthetic generation for any remaining gaps.

1. Follow [User Data Strategy](#user-data-strategy) Steps A-E to match user files
2. For each unfilled input, apply [Synthetic Strategy](#synthetic-strategy)
3. Assemble the complete `inputs.json` combining both sources
4. Report which inputs came from user data and which were synthesized

---

---

## Document Generation

Generate test documents based on the document type needed.

> **In this environment**, the code below writes the file to a local path only as a staging step. After generating each file, upload it and reference the returned URI in `inputs.json`:
> ```bash
> mthds-agent inputs upload <the-generated-file>
> ```
> The local path never appears in `inputs.json`.


### PDF Documents

> `reportlab` is a dependency of `pipelex` — always available, no additional installation needed.
> For how to invoke Python, see [Python Execution Reference](../shared/python-execution.md).

#### Basic PDF (canvas)

One page drawn with the canvas API, for letters, notes, notices and certificates. Coordinates are points (1/72 inch) up and right from the bottom-left corner; y is the text's baseline.

```bash
"$(uv tool dir)/pipelex/bin/python" << 'PYEOF'
import os
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

OUT = "<output_dir>/inputs/test_document.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4
CLINIC = "Wrenfield Veterinary Clinic"
ADDRESS = ["214 Sorrel Street, Aldenmoor Springs", "Tel. 555-0147"]
DATE = "October 6, 2026"
RECIPIENT = ["Ms. Dana Whitlock", "88 Quarry Hill Road", "Aldenmoor Springs"]
SUBJECT = "Vaccination reminder for Biscuit (patient WVC-30412)"
BODY = [
    "Dear Ms. Whitlock,",
    "Biscuit is due for her yearly rabies and DHPP boosters. We have booked her in with Dr. Pascoe on "
    "Thursday, October 22, 2026, at 10:15 a.m. Please bring her vaccination card.",
    "If this time does not suit you, call us at least a day ahead.",
    "Kind regards,",
]
SIGNER = "Dr. Imogen Pascoe, DVM"
# ==== END CONTENT ====

MARGIN = 72


def render(path):
    width, height = PAGE_SIZE
    room = width - 2 * MARGIN
    y = height - MARGIN
    # invariant=1: byte-identical reruns. No pagesize means A4.
    c = Canvas(path, pagesize=PAGE_SIZE, invariant=1)
    c.setTitle(SUBJECT)

    def put(text, font="Helvetica", size=11, gap=15, right=False):
        # The canvas never wraps, clips or adds pages: overflow would vanish silently.
        nonlocal y
        if c.stringWidth(text, font, size) > room or y < MARGIN:
            raise ValueError(f"Does not fit the page; shorten it or use Platypus: {text!r}")
        c.setFont(font, size)
        if right:
            c.drawRightString(width - MARGIN, y, text)
        else:
            c.drawString(MARGIN, y, text)
        y -= gap

    put(CLINIC, "Helvetica-Bold", 20, gap=18)
    for line in ADDRESS:
        put(line, size=9, gap=12)
    c.line(MARGIN, y, width - MARGIN, y)
    y -= 36
    put(DATE, right=True, gap=30)
    for line in RECIPIENT:
        put(line)
    y -= 15
    put(SUBJECT, "Helvetica-Bold", gap=26)
    for paragraph in BODY:
        for line in simpleSplit(paragraph, "Helvetica", 11, room):
            put(line)
        y -= 9
    y -= 24
    put(SIGNER, "Helvetica-Bold")
    put(CLINIC)
    c.save()


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

The canvas never wraps, so the script wraps paragraphs and fails rather than let text run off the page; real paragraph wrapping belongs in Platypus. `PAGE_SIZE = A4` gives A4.

#### Multi-page PDF (Platypus)

Headings and paragraphs that Platypus flows over numbered pages, for reports, policies, contracts and manuals; the title is also the PDF's title metadata.

```bash
"$(uv tool dir)/pipelex/bin/python" << 'PYEOF'
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

OUT = "<output_dir>/inputs/test_report.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4
SECTIONS_START_ON_NEW_PAGE = False
TITLE = "Building Condition Inspection Report"
DETAILS = [("Property", "Corran Quay Residences, 40 Tidewater Lane, Port Aldery"),
           ("Prepared for", "Corran Quay Owners' Association"),
           ("Inspected", "September 14, 2026, by Priya Ostrander, Halvard & Moss Building Surveyors")]
REFERENCE = "HM-2026-0388"
# Items are paragraphs or (subheading, paragraph) pairs.
SECTIONS = [
    ("Overview", [
        "We visually inspected the roof, elevations, garage, plant room and common parts of this block of 24 "
        "apartments, built in 1988.",
        "The building is in fair condition. The most serious findings are water entering at the north-east "
        "parapet and corroded railing brackets on six south balconies, which residents should not use until an "
        "engineer has assessed them. A fire door that no longer closes also needs prompt repair.",
    ]),
    ("Findings by area", [
        ("Roof and drainage: Fair", "The membrane has blistered near the north-east corner, where the parapet "
         "coping joints have opened. Three of the five outlets were partly blocked, and the fourth-floor "
         "corridor ceiling below the corner is stained and damp."),
        ("Elevations and balconies: Poor", "The brickwork is sound, but the railing brackets on six of the "
         "twelve south balconies are rusting where they enter the slab, and the concrete around two of them "
         "has cracked."),
        ("Structure: Good", "There is no sign of settlement or movement. The garage slab shows only fine "
         "shrinkage cracks."),
        ("Services: Fair", "The water heater, installed in 2009, is near the end of its life, and a plant-room "
         "valve is weeping."),
        ("Fire safety: Fair", "The alarm panel showed no faults and the extinguishers are in date, but the "
         "third-floor fire door to the east stairwell no longer closes on its own."),
    ]),
    ("Recommendations", [
        ("Within one week", "Keep residents off the six balconies and commission a structural engineer."),
        ("Within one month", "Repair the closer of the third-floor fire door."),
        ("Before winter", "Repoint the parapet coping, repair the membrane, clear the outlets, then repair the "
         "stained ceiling."),
        ("Within a year", "Replace the weeping valve and budget for a new water heater."),
    ]),
]
# ==== END CONTENT ====


def style(name, font="Times-Roman", size=11, **extra):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=size * 1.35, **extra)


TITLE_STYLE = style("title", "Helvetica-Bold", 22, spaceAfter=10)
# keepWithNext: no heading left alone at the foot of a page.
H1 = style("h1", "Helvetica-Bold", 15, spaceBefore=14, spaceAfter=6, keepWithNext=1)
H2 = style("h2", "Helvetica-Bold", 11.5, spaceBefore=8, spaceAfter=2, keepWithNext=1)
BODY = style("body", spaceAfter=7)


def para(text, style):
    # Paragraph parses markup: an unescaped "<" or "&" raises or loses text.
    return Paragraph(escape(text), style)


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(doc.leftMargin + 6, 40, f"{TITLE}, {REFERENCE}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin - 6, 40, f"Page {canvas.getPageNumber()}")


def render(path):
    story = [para(TITLE, TITLE_STYLE)]
    story += [Paragraph(f"<b>{escape(k)}:</b> {escape(v)}", BODY) for k, v in DETAILS]
    for number, (heading, items) in enumerate(SECTIONS):
        if number and SECTIONS_START_ON_NEW_PAGE:
            story.append(PageBreak())
        story.append(para(heading, H1))
        for item in items:
            story += [para(item[0], H2), para(item[1], BODY)] if isinstance(item, tuple) else [para(item, BODY)]
    # invariant=1: byte-identical reruns. No pagesize means A4.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

Add items to `SECTIONS` to lengthen it. Sections flow on; `SECTIONS_START_ON_NEW_PAGE = True` gives each a new page, `PAGE_SIZE = A4` an A4 page.

#### Table report (Platypus)

A titled table for price lists, schedules and results: here, lab results whose verdicts and highlights are computed from limits stated beneath it.

```bash
"$(uv tool dir)/pipelex/bin/python" << 'PYEOF'
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table

OUT = "<output_dir>/inputs/test_table.pdf"
if "<" in OUT or ">" in OUT:
    sys.exit(f"Refusing to run: OUT still holds a placeholder: {OUT}")
Path(OUT).parent.mkdir(parents=True, exist_ok=True)

# ==== CONTENT: edit only this block ====
# Built-in fonts: non-Latin-1 characters (emoji, subscripts) print as black boxes.
PAGE_SIZE = letter  # or A4; landscape(letter) when the columns cannot fit
LAB = "Oxbury Vale Water Testing Laboratory"
TITLE = "Drinking-water results, August 2026"
INFO = "Client: Marrowby District Water Board. Report OVW-26-0913."
COLUMNS = ["Sample", "Site", "Sampled"]
# (header, decimals shown, low limit, high limit); None means no limit.
MEASURES = [("pH", 1, 6.5, 9.0), ("Turbidity (NTU)", 1, None, 4.0),
            ("Nitrate (mg/L)", 1, None, 50.0), ("Lead (µg/L)", 1, None, 10.0)]
VERDICT = "Verdict"
COL_WIDTHS = [52, 108, 60, 34, 52, 44, 40, 46]  # points, one per column
SAMPLES = [
    ("L26-0801", "Ostry Reservoir outlet", "2026-08-11", (7.6, 0.4, 12.3, 0.8)),
    ("L26-0802", "Kestrel Lane standpipe", "2026-08-11", (7.5, 0.6, 12.9, 1.2)),
    ("L26-0803", "Marrowby Primary School, kitchen tap", "2026-08-11", (7.3, 0.3, 12.1, 2.4)),
    ("L26-0804", "14 Weaver's Row", "2026-08-12", (7.2, 0.4, 12.6, 14.2)),
    ("L26-0805", "Brackley Road hydrant", "2026-08-12", (7.5, 5.6, 12.8, 1.9)),
    ("L26-0806", "Fenwick Farm borehole", "2026-08-13", (6.3, 1.1, 61.4, 0.9)),
    ("L26-0807", "Low Moor pump house", "2026-08-13", (7.8, 0.2, 13.0, 0.6)),
    ("L26-0808", "Upper Heath estate", "2026-08-14", (7.6, 0.6, 12.0, 4.8)),
]
# ==== END CONTENT ====

NAVY, STRIPE, RULE = HexColor("#1F3B57"), HexColor("#EDF1F5"), HexColor("#B8C3CD")
FAIL_FILL, FAIL_INK = HexColor("#F7D6D2"), HexColor("#9A1B10")
# Paragraphs in cells ignore the table's FONT, TEXTCOLOR and ALIGN; their style rules.
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11)
HEAD = ParagraphStyle("head", CELL, fontName="Helvetica-Bold", textColor=white)
HEAD_RIGHT = ParagraphStyle("head_right", HEAD, alignment=TA_RIGHT)
TEXT = ParagraphStyle("text", CELL, fontSize=10, leading=14, spaceBefore=4)


def grid(last=-1):
    return [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, last), [white, STRIPE]),
        ("LINEBELOW", (0, 1), (-1, last), 0.25, RULE),
        ("BOX", (0, 0), (-1, last), 0.6, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]


def shown(value, decimals):
    # Judge values as printed: 4.04 shown as "4.0" must not fail a 4.0 limit.
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), ROUND_HALF_UP)


def limit(header, decimals, low, high):
    lo, hi = (None if v is None else shown(v, decimals) for v in (low, high))
    return f"{header} " + (f"at most {hi}" if lo is None else f"at least {lo}" if hi is None else f"{lo} to {hi}")


def render(path):
    # invariant=1: byte-identical reruns. No pagesize means A4.
    doc = SimpleDocTemplate(path, pagesize=PAGE_SIZE, title=TITLE, invariant=1)
    ncols, first = len(COLUMNS) + len(MEASURES) + 1, len(COLUMNS)
    frame = doc.width - 12  # 6 pt frame padding each side: 456 pt on Letter
    # A too-wide table runs off the page silently (Platypus checks only heights), so check the widths.
    if len(COL_WIDTHS) != ncols or sum(COL_WIDTHS) > frame:
        raise ValueError(f"Need {ncols} widths totalling at most {frame:.0f} pt")
    rows = [[Paragraph(escape(h), HEAD) for h in COLUMNS] + [Paragraph(escape(m[0]), HEAD_RIGHT) for m in MEASURES]
            + [Paragraph(escape(VERDICT), HEAD)]]
    # Highlights come after the stripes: backgrounds paint in command order.
    marks = grid() + [("ALIGN", (first, 1), (-2, -1), "RIGHT")]
    for r, (sample, site, date, values) in enumerate(SAMPLES, 1):
        if len(values) != len(MEASURES):
            raise ValueError(f"{sample} needs one value per measurement")
        printed = [shown(v, m[1]) for v, m in zip(values, MEASURES)]
        bad = [first + i for i, (p, (_, _, low, high)) in enumerate(zip(printed, MEASURES))
               if (low is not None and p < Decimal(str(low))) or (high is not None and p > Decimal(str(high)))]
        rows.append([sample, Paragraph(escape(site), CELL), date, *map(str, printed), "Fail" if bad else "Pass"])
        for c in (bad + [ncols - 1] if bad else []):
            marks += [("BACKGROUND", (c, r), (c, r), FAIL_FILL), ("TEXTCOLOR", (c, r), (c, r), FAIL_INK)]
    limits = "; ".join(limit(*m) for m in MEASURES)
    doc.build([
        Paragraph(escape(LAB), ParagraphStyle("lab", TEXT, fontName="Helvetica-Bold", fontSize=15, textColor=NAVY)),
        Paragraph(f"<b>{escape(TITLE)}</b>", TEXT),
        Paragraph(escape(INFO), TEXT),
        Table(rows, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT", style=marks, spaceBefore=10),
        Paragraph(f"<b>Limits:</b> {escape(limits)}. Highlighted values break a limit and fail the sample.", TEXT),
    ])


PART = str(Path(OUT).with_name(f".{Path(OUT).stem}.part{Path(OUT).suffix}"))
try:
    render(PART)
    os.replace(PART, OUT)
finally:
    Path(PART).unlink(missing_ok=True)
print(f"wrote {OUT}")
PYEOF
```

A table too wide for the page runs off it silently, so the widths are fixed and checked against the 456 pt Letter frame; use `landscape(letter)` when they cannot fit, `A4` for A4.

### Word Documents (DOCX)

**If `example-skills:docx` skill is available:**
```
Use the /docx skill to create a Word document with the following content:
[Describe the document content, structure, and formatting]
Save to: <output_dir>/inputs/<filename>.docx
```

**If skill is NOT available**, create using Python (see [Python Execution Reference](../shared/python-execution.md)):
```bash
uv run --with python-docx python << 'PYEOF'
from docx import Document

doc = Document()
doc.add_heading('Test Document', 0)
doc.add_paragraph('This is synthetic test content for method testing.')
# Add more content as needed
doc.save('<output_dir>/inputs/test_document.docx')
PYEOF
```

### Spreadsheets (XLSX)

**If `example-skills:xlsx` skill is available:**
```
Use the /xlsx skill to create a spreadsheet with the following data:
[Describe columns, rows, and sample data]
Save to: <output_dir>/inputs/<filename>.xlsx
```

**If skill is NOT available**, create using Python (see [Python Execution Reference](../shared/python-execution.md)):
```bash
uv run --with openpyxl python << 'PYEOF'
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws['A1'] = 'Column1'
ws['B1'] = 'Column2'
ws['A2'] = 'Value1'
ws['B2'] = 'Value2'
wb.save('<output_dir>/inputs/test_spreadsheet.xlsx')
PYEOF
```

---

**Fallback Strategy:**
1. For PDFs: use `reportlab` via pipelex's Python (`"$(uv tool dir)/pipelex/bin/python"`)
2. For DOCX/XLSX: use the `/docx` or `/xlsx` skill, or `uv run --with <package> python`
3. For any format: use public test file URLs as fallback
4. As last resort, ask user to provide test files

---

## Validate & Run

After assembling the inputs, confirm readiness:

> Inputs are ready. `inputs.json` has been saved with real values — no placeholders remain.

---

## Native Concept Content Structures

### Text
```json
{"text": "The actual text content"}
```

### Number
```json
{"number": 42}
```

### YesNo
```json
{"yes_no": true}
```

### Date
```json
{"date": "2026-07-08", "time": null}
```

### Date with time
```json
{"date": "2026-07-08", "time": "15:40:00+02:00"}
```

### Time
```json
{"time": "15:40:00+02:00"}
```

### Image
```json
{
  "url": "pipelex-storage://<user>/assets/<uuid>.jpg",
  "caption": "Optional description",
  "mime_type": "image/jpeg"
}
```

### Document
```json
{
  "url": "pipelex-storage://<user>/assets/<uuid>.pdf",
  "mime_type": "application/pdf"
}
```

### Document (Web Page)
```json
{
  "url": "https://example.com/article",
  "mime_type": "text/html"
}
```

### TextAndImages
```json
{
  "text": {"text": "Main text content"},
  "images": [
    {"url": "pipelex-storage://<user>/assets/<uuid>.png", "caption": "Figure 1"}
  ]
}
```

### Page
```json
{
  "text_and_images": {
    "text": {"text": "Page content..."},
    "images": []
  },
  "page_view": null
}
```

### JSON
```json
{"json_obj": {"key": "value", "nested": {"data": 123}}}
```

---

## Complete Examples

### Example 1: Template for a Haiku writer

**Method**: Haiku pipeline expecting `theme: Text`

```bash
mthds-agent inputs bundle mthds-wip/pipeline_01/bundle.mthds -L mthds-wip/pipeline_01/
```

Save the `inputs` from the output directly to `mthds-wip/pipeline_01/inputs.json`.

### Example 2: Synthetic data for an image analysis pipeline

**Method**: Image analyzer expecting `image: Image` and `analysis_prompt: Text`

1. Get schema, identify needs: test photograph + instruction text
2. Generate image via `synthesize_image.mthds` with category `photograph`
3. Write analysis prompt text matching the method context
4. Assemble:
```json
{
  "image": {
    "concept": "native.Image",
    "content": {
      "url": "pipelex-storage://<user>/assets/<uuid>.jpg",
      "mime_type": "image/jpeg"
    }
  },
  "analysis_prompt": {
    "concept": "native.Text",
    "content": {
      "text": "Analyze this street scene. Count visible people and describe the atmosphere."
    }
  }
}
```

### Example 3: User-provided invoice PDF

**Method**: Invoice processor expecting `invoice: Document` and `instructions: Text`

User says: "Use my file `~/documents/invoice_march.pdf`"

1. Get schema: needs `invoice` (Document) + `instructions` (Text)
2. Inventory: user provided `invoice_march.pdf` (PDF = Document type)
3. Match: `invoice_march.pdf` maps to `invoice` input (name similarity + type match)
4. Upload: `mthds-agent inputs upload ~/documents/invoice_march.pdf` → returns e.g. `pipelex-storage://<user>/assets/<uuid>.pdf`
5. Unfilled: `instructions` has no user file. Generate synthetic text: "Extract all line items, totals, and vendor information from this invoice."
6. Assemble:
```json
{
  "invoice": {
    "concept": "native.Document",
    "content": {
      "url": "pipelex-storage://<user>/assets/<uuid>.pdf",
      "mime_type": "application/pdf"
    }
  },
  "instructions": {
    "concept": "native.Text",
    "content": {
      "text": "Extract all line items, totals, and vendor information from this invoice."
    }
  }
}
```

### Example 4: Folder of images for batch processing

**Method**: Batch image captioner expecting `images: Image[]`

User says: "Use the photos in `./product-photos/`"

1. Get schema: needs `images` (Image[])
2. Expand folder: `./product-photos/` contains `shoe.jpg`, `hat.png`, `bag.jpg`
3. Upload each: `mthds-agent inputs upload ./product-photos/shoe.jpg` (repeat per file) → collect the returned `pipelex-storage://…` URIs
4. Assemble:
```json
{
  "images": {
    "concept": "native.Image",
    "content": [
      {"url": "pipelex-storage://<user>/assets/<uuid-1>.jpg", "mime_type": "image/jpeg"},
      {"url": "pipelex-storage://<user>/assets/<uuid-2>.png", "mime_type": "image/png"},
      {"url": "pipelex-storage://<user>/assets/<uuid-3>.jpg", "mime_type": "image/jpeg"}
    ]
  }
}
```

---

## Reference

- [Error Handling](../shared/error-handling.md) — read when CLI returns an error to determine recovery
- [MTHDS Agent Guide](../shared/mthds-agent-guide.md) — read for CLI command syntax or output format details
- [MTHDS Language Reference](../shared/mthds-reference.md) — read for concept definitions and syntax
- [Native Content Types](../shared/native-content-types.md) — read for the full attribute reference of each native content type when assembling input JSON
