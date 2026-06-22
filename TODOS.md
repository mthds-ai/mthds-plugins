# Rewrite PipeImgGen / `ImgGenPrompt` docs in the skills + references

**Goal:** Bring this plugin's skill docs and reference docs in line with the pipelex change that (a) removes the native concept `native.ImgGenPrompt` and (b) corrects the mental model for how `PipeImgGen` consumes inputs. Stop the skills from teaching `ImgGenPrompt` as a concept, and teach the real model: `PipeImgGen` has a required `prompt` **template** and its declared `inputs` (text and/or image) are **injected into that template**.

**Status:** Not started (plan written; awaiting go-ahead to execute). Single-session, low risk, doc-only.

**Branch:** continue on `chore/remove-dead-img-gen-enum` (it already removed the dead `img_gen_input_not_text_compatible` error-hint row that pointed at `ImgGenPrompt` — this is the same cleanup theme), or branch off it. Do not work on `main`.

---

## Cold-start context (read this first)

### Why this change exists — the upstream pipelex fix

The authoritative change and its rationale live in `../pipelex/TODOS.md` ("Remove the `ImgGenPrompt` native concept"). Read it for the full story. The two facts that drive **our** doc edits:

1. **`native.ImgGenPrompt` is being removed.** It carried zero structural distinction from `Text` (the factory mapped it to `TextContent`). It was a built-in concept with no payload beyond its name. **Migration everywhere = `ImgGenPrompt` → `Text`.** After pipelex ships, any `.mthds` using `ImgGenPrompt` as a concept (input, output, or `refines`) fails validation. Our skills currently *tell users to write it*, so they're actively emitting a soon-to-be-dead concept.

2. **The old "feed PipeImgGen an `ImgGenPrompt` concept" framing was always wrong.** Corrected model (quote this when rewriting):

   > `PipeImgGen` does **not** consume a dedicated "prompt concept". It has a required **`prompt` string template** (+ optional `negative_prompt`), and its declared `inputs` are **injected into that template**:
   > - **text inputs** (concept `Text`) are interpolated via `$var` / Jinja;
   > - **image inputs** (concept `Image`, single or list `Image[]`) are referenced in the prompt and injected — each referenced image becomes an `[Image N]` token passed to the generator alongside the rendered text (the **same vision pattern** as image inputs to `PipeLLM`; enables image-to-image / reference-image / editing, bounded by the model's `max_prompt_images`).
   >
   > `PipeImgGen`'s only concept constraints: declared image inputs must be `Image`-compatible, and the output must be `Image`-compatible.

   So the right way to teach `PipeImgGen` is: **write a `prompt` template, declare `Text` and/or `Image` inputs, reference them in the template.** No `ImgGenPrompt` concept anywhere in that flow. The `prompt` field stays required (that guidance is correct and must be preserved).

### The name-collision trap (critical — do NOT over-scope)

Three+ unrelated things share the "img gen prompt" string. **Only the concept is being removed.** Grep by context, not by substring:

| Token in our docs | What it is | Action |
|---|---|---|
| `ImgGenPrompt` (PascalCase, used as a concept in `inputs`/native-concept lists) | the native **concept** `native.ImgGenPrompt` | **REMOVE / migrate → `Text`** |
| `img_gen_prompt` (snake_case, in the Template Categories table) | `TemplateCategory.IMG_GEN_PROMPT` — Jinja2 category for prompt rendering | **KEEP — different thing** |
| `img_gen` (in `mthds-agent models --type img_gen`, `model = "$gen-image"`) | the image-generation **model type** | **KEEP** |
| `llm_output_cannot_be_image` → "Use PipeImgGen instead" | error-handling hint | **KEEP — still correct** |
| "image generation" prose, `#image-generation` anchors, `tests/unit/test_can_run_methods_flag.py` | unrelated feature text/tests | **KEEP** |

If you find yourself editing a `img_gen_prompt` Template-Categories row, an `img_gen` model-type line, or a model-references doc, STOP — you've drifted into the collision.

### Build-system mechanics (how edits propagate)

- **Source of truth = `templates/*.j2` (rendered) + canonical static references under `skills/<skill>/references/*.md` (copied verbatim).** Never edit the generated target dirs.
- Generated targets `mthds/`, `mthds-dev/`, `mthds-codex/`, `mthds-sandbox/` are produced by `scripts/gen_skill_docs.py` (`shutil.copytree` for references — they are **copies**, not symlinks, despite the legacy note in `CLAUDE.md`). They are checked in and freshness-gated by `make check-shared`.
- Workflow: edit source → `make build` (builds all targets via `--target all`) → `make check` → `make test`.
- `mthds-vibe` ships in all four targets; its reference `skills/mthds-vibe/references/vibe-cheat-sheet.md` is in scope.

### Coordination / dependency note (decide before landing)

- This is **doc-only** and safe to land independently of the pipelex release — worst case the docs briefly describe a concept the *currently pinned* runtime still accepts. The skills calling out `ImgGenPrompt` is the active bug; removing it is strictly an improvement.
- The plugin shells out to whatever `mthds-agent`/`pipelex` is on PATH. Once the pipelex version that removed `native.ImgGenPrompt` is published, consider bumping `min_mthds_version` (`targets/defaults.toml [vars]`, via the `/bump-mthds-version` skill) so the hook's validation matches the new docs. **Open question for the executor:** is that pipelex version released yet? If yes, bump in this change; if no, leave a note and bump later. Do not block the doc rewrite on it.

---

## Edit checklist

Exact source files and line numbers (lines drift after the first edit in a file — re-grep within the file if needed). Five source files total.

### A. Remove `ImgGenPrompt` from native-concept enumerations

- [ ] `templates/skills/shared/mthds-reference.md.j2:40` — drop `ImgGenPrompt` from the "Use directly without defining" list. No hardcoded count to fix (it's a bare comma list).
- [ ] `templates/skills/shared/native-content-types.md.j2:22` — delete the table row `| `ImgGenPrompt` | *(refines Text)* | `text` |`. (No detailed section exists for it, so nothing else to remove.)
- [ ] `templates/skills/mthds-build/SKILL.md.j2:120` — drop `ImgGenPrompt` from the "Native concepts (built-in, do NOT redefine)" list. Keep the "do NOT redefine" framing.
- [ ] `skills/mthds-vibe/references/vibe-cheat-sheet.md:149` — delete the native-concept table row `| `ImgGenPrompt` | A prompt for image generation. |`.

### B. Migrate `ImgGenPrompt` → `Text` in PipeImgGen examples

The three example pipes that declare `inputs = { img_prompt = "ImgGenPrompt" }`. These were always *text* prompts, so `Text` is correct.

- [ ] `templates/skills/shared/mthds-reference.md.j2:370` — `inputs = { img_prompt = "ImgGenPrompt" }` → `inputs = { img_prompt = "Text" }`.
- [ ] `skills/mthds-build/references/build-phases.md:187` — `"inputs": {"img_prompt": "ImgGenPrompt"}` → `"inputs": {"img_prompt": "Text"}`.
- [ ] `skills/mthds-vibe/references/vibe-cheat-sheet.md:385` — `inputs = { img_prompt = "ImgGenPrompt" }` → `inputs = { img_prompt = "Text" }`.

### C. Fix the framing + add image-input (image-to-image) coverage (the substantive rewrite)

Goal: every place that explains PipeImgGen reflects the corrected model — `prompt` template + injected `Text`/`Image` inputs. **Preserve** the "`prompt` is required" rule everywhere (it is still true and is a common-mistake guard). Keep additions compact — skills should not over-explain.

- [ ] `templates/skills/shared/mthds-reference.md.j2` PipeImgGen section (~364–386):
  - Keep the `prompt`-required note and aspect-ratio list.
  - After the `Text` example, add a short **image-input** variant showing `inputs = { ref = "Image" }` (and mention the list form `Image[]`), the image referenced in the `prompt` template, and one line: each referenced image is injected as an `[Image N]` token (image-to-image / reference image), bounded by the model's `max_prompt_images`.
  - Add `negative_prompt` to the optional-fields list (one line).
- [ ] `templates/skills/mthds-build/SKILL.md.j2`:
  - Lines ~196–200 ("Critical — PipeImgGen requires a `prompt` field") — keep as-is; optionally append one clause: declared `inputs` are injected into the `prompt` template (text interpolated, images injected as reference images).
  - Line ~225 Phase-6 checklist item "PipeImgGen inputs are text-compatible (add PipeLLM if needed…)" — **reword**: this is now too narrow. State that the `prompt` template references its declared inputs; text inputs are interpolated, and image inputs are allowed as reference images (image-to-image). Drop the implication that only text is permitted.
  - Line ~256 ("PipeImgGen `prompt` is required" `--spec` note) — keep; no concept change needed (examples already use `$img_prompt`, not a concept).
- [ ] `skills/mthds-build/references/build-phases.md` PipeImgGen `--spec` block (~181–193):
  - Keep the `prompt`-required note.
  - Optionally add a second `--spec` example with `"inputs": {"ref": "Image"}` and the image referenced in `prompt`, to show image-to-image authoring via the CLI.
- [ ] `skills/mthds-vibe/references/vibe-cheat-sheet.md` PipeImgGen section (~379–394):
  - Keep "Required: `prompt`" and the aspect-ratio list.
  - Add a compact image-input example (`inputs = { ref = "Image" }`, referenced in `prompt`) + one line on the `[Image N]` injection / `max_prompt_images` bound.
  - Lines ~448 and ~487 (prompt-shorthand applies-to list; the "don't omit `prompt`" gotcha) — leave unchanged; both are still correct.

### D. Build, check, verify

- [ ] `make build` — regenerate all four targets (`mthds/`, `mthds-dev/`, `mthds-codex/`, `mthds-sandbox/`). Confirm the generated copies picked up every edit.
- [ ] `make check` — shared freshness + lint/type + Claude + Codex packaging checks must pass (freshness fails if any generated copy is stale).
- [ ] `make test` — unit tests.
- [ ] Final grep — `rg -n '\bImgGenPrompt\b' .` (or excluding `mthds*/` generated dirs, then re-include to confirm regen). Expected: **zero** `ImgGenPrompt`-as-concept hits anywhere. Any remaining `img_gen_prompt` (TemplateCategory) and `img_gen` (model type) hits are expected and correct.

### E. Land

- [ ] Commit on the feature branch; push.
- [ ] Open PR. In the description, link `../pipelex/TODOS.md` as the upstream change and note this is the plugin-side doc sync (no runtime/code change here).
- [ ] If the pipelex version removing `native.ImgGenPrompt` is already published, bump `min_mthds_version` in this PR (see Coordination note); otherwise leave a follow-up.

---

## DO-NOT-TOUCH guardrail (restated — the collision traps)

If you edit any of these, STOP — wrong target:

- `img_gen_prompt` Template-Categories row — `templates/skills/shared/mthds-reference.md.j2:333` (the `TemplateCategory.IMG_GEN_PROMPT` Jinja2 category). **Stays.**
- `mthds-agent models --type img_gen` and `model = "$gen-image"` lines — `model-references.md`, `build-phases.md`, `SKILL.md.j2`. **Stay** (model type, not concept).
- `llm_output_cannot_be_image` → "Use PipeImgGen instead" — `error-handling.md.j2`, `mthds-fix/SKILL.md.j2`. **Stays** (correct hint).
- "image generation" prose, `#image-generation` anchors, `tests/unit/test_can_run_methods_flag.py`. **Stay.**
- The generated target dirs (`mthds/`, `mthds-dev/`, `mthds-codex/`, `mthds-sandbox/`) — never hand-edit; they are regenerated by `make build`.
