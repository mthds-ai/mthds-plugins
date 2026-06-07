# `mthds-agent` Output Format Audit (working doc)

**Status: working doc.** Inline remarks (`> **Remark:**`) and open questions are intentional. The goal is to make every `mthds-agent` call in the plugin explicit — its consumer, what it reads from **stdout** (success) and **stderr** (errors), and whether the chosen output format is right — so we can decide what to fix. Discuss each `⚠`/`✗` case before changing it.

## The organizing rule — *format follows consumer*

`mthds-agent` (and the `pipelex-agent` it passes through to) can emit output as **JSON** or **markdown**, independently on the success stream and the error stream. The right choice depends on *who reads it*:

- **Software consumer → JSON.** A hook/script that extracts a field or branches on a value wants a stable schema, not prose to scrape.
- **LLM consumer → markdown.** An agent reading output to understand state or fix a file reads markdown more naturally *and* more cheaply (the JSON error envelope ships `error_source` stack frames, `hint`, `validation_errors`, etc. — token noise an LLM doesn't need).

> **Nuance (the one that bites):** a hook can be *software that still wants markdown errors*. Both PostToolUse hooks classify on `error_domain` by grepping the **markdown** error report, and the Claude hook also forwards that same markdown as the agent-facing block `reason`. So "software" does not automatically mean "JSON errors" — it means "whatever the code actually parses." Always check the consumer's parsing, not its category.

## The two output controls (and the inherit trap)

`validate bundle` (the command where this matters most) has **two independent** controls:

| Flag | Governs | Stream |
|------|---------|--------|
| `--format markdown\|json` | the **success** envelope | stdout |
| `--error-format markdown\|json` | the **error** report | stderr |

**Trap:** `--error-format` **inherits `--format`** when omitted. So `--format json` *alone* flips **both** streams to JSON. To get JSON success + markdown errors you must pin **both**: `--format json --error-format markdown`. (Canonical reference: `pipelex/cli/agent_cli/CLAUDE.md` §"Output format".)

`mthds-agent validate` forwards these flags verbatim to `pipelex-agent` via `.allowUnknownOption()` — no mthds-agent-side option exists.

## Default formats per command (empirically verified)

Verified against `mthds-agent 0.9.0` → editable `_recursive` pipelex (2026-06-08). **These are the no-flag defaults** — they decide whether a plain call is already LLM-friendly.

| Command | Default stdout (success) | Default stderr (errors) | Notes |
|---------|--------------------------|--------------------------|-------|
| `validate bundle` | **markdown** (`# Validation passed`, a `✅ … runnable` / `⚠️ … NOT yet runnable` verdict, `## Pending signatures (N)`) | **markdown** (`# Error: …`, `- **error_domain:** …`) | Same with or without `--allow-signatures`. **Not** JSON. `--format json` success envelope adds `is_runnable` (= `pending_signatures` empty) alongside `pending_signatures`. Verdict / `is_runnable` only on `validate bundle` (incl. `--pipe`), not `validate all` / `validate pipe`. |
| `inputs bundle` | **JSON** (`{ "success": true, "inputs": {…} }`) | (untested) | Output is structured data (a schema/template), so JSON is the natural form for any consumer. |
| `run bundle` | **JSON** (compact concept output; `--with-memory` → full envelope) | (untested — assume markdown, same pipelex two-stream) | stdout is the method *result* (data), not prose. |
| `concept` / `pipe` | **raw TOML** | JSON on stderr (per guide) | Agent splices the TOML into the bundle. |
| `models` / `check-model` | **markdown** | — | Human/LLM-readable lists. |
| `doctor` | **markdown** (supports `--format json`) | — | session-start hook overrides to `--format json`. |
| `bootstrap` / `update-check` / `mthds-env-check` | **status tokens** (`BOOTSTRAP_*`, `UP_TO_DATE …`, `MTHDS_AGENT_OUTDATED …`) | — | Bespoke line protocol, neither JSON nor markdown. |

> **Remark — the guide is wrong here.** `templates/skills/shared/mthds-agent-guide.md.j2` (the "Agent CLI" section, ~line 36) says *"JSON on stdout: `run`, `validate`, `inputs`, `init`, `install`, `package` commands."* For `validate bundle` that is **false** — its default success output is **markdown** (verified above). `inputs`/`run` do default to JSON. This line should be corrected so it doesn't mislead skill authors into thinking they must pass `--format markdown` to get markdown (they get it for free). → was **Finding F3** (✅ resolved 2026-06-08 — `validate` moved to the markdown-on-stdout bullet and the errors/JSON-output notes qualified).

---

## The audit — by consumer

### A. Software consumers (parse output programmatically)

#### A1 — Claude PostToolUse hook · `validate-mthds.sh.j2:111`
```
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --allow-signatures --format json --error-format markdown
```
- **stdout (success):** JSON. Parses `pending_signatures` via the `_jv` node helper → emits a non-blocking nudge. **JSON is correct** — software reading a specific field.
- **stderr (failure):** markdown. Greps `- **error_domain:** …` to classify (block on `input`/unknown, warn on `config`/`runtime`), and forwards the trimmed markdown as the block `reason` (read by the LLM). **markdown is correct** — it serves both the grep classifier *and* the downstream LLM.
- **Verdict: ✓ CORRECT.** The textbook case: JSON for the field the script needs, markdown for the error the LLM ultimately reads. Both streams pinned explicitly — robust.

#### A2 — SessionStart hook · `session-start.sh.j2:15`
```
mthds-agent doctor --format json
```
- **stdout:** JSON. Parses `dependencies[]` with node to print a version line. **JSON is correct** — software.
- **Verdict: ✓ CORRECT.**

#### A3 — Codex PostToolUse hook · mthds-js `src/agent/commands/codex-hook.ts:285` (`runPipelexValidate`)
```
pipelex-agent validate bundle <file> -L <libraryDir>            # no --allow-signatures, no format flags
```
- **stderr (failure):** relies on the **default** being markdown — greps `^- \*\*error_domain:\*\* *(\S+)` (`extractErrorDomain`, line 119), forwards markdown as the agent-facing reason. **markdown is what it needs** — but it gets it by default, not by pinning.
- **stdout (success):** not parsed (Codex hook only inspects output on failure; no `pending_signatures` nudge — deferred for v1).
- **Verdict: ⚠ FRAGILE + INCOMPLETE.**
  - *Fragile:* it depends on the *default* error format staying markdown. The Claude hook pins `--error-format markdown` explicitly; the Codex hook should too, so a future default flip can't silently break the `error_domain` regex.
  - *Incomplete:* still missing `--allow-signatures`, so it **blocks** signature-containing saves — this is **Phase 5** (not yet done). Recursive builds under Codex will fight this hook until then.
  - **Recommendation (fold into Phase 5):** `["validate","bundle",file,"-L",libraryDir,"--allow-signatures","--error-format","markdown"]`. No `--format json` (no success parse needed for v1; add it only if/when the Codex nudge lands). → **Finding F2.**

### B. LLM consumers (the agent reads the output)

#### B1 — `mthds-vibe` Step 1 (capture) · `SKILL.md.j2:84`
```
mthds-agent validate bundle …/bundle.mthds -L …/ --allow-signatures --graph
```
- Default markdown on both streams. LLM reads `# Validation passed` and (on error) the markdown error. **Verdict: ✓ CORRECT.**

#### B2 — `mthds-vibe` Step 2 (refine loop) · `SKILL.md.j2` Step 2 — **FIXED (Fix B applied 2026-06-08)**
```
mthds-agent validate bundle …/bundle.mthds -L …/ --allow-signatures --graph
```
- All markdown now. The LLM reads the backlog from the `## Pending signatures (N)` markdown section on stdout (success) and reads markdown errors on stderr (failure). `--format json` dropped, so Step 2 matches Steps 1 & 3 and never sends JSON errors to the LLM.
- **Verdict: ✓ CORRECT** (was ✗ — the `--format json` inherit trap had been flipping errors to JSON for the LLM).
- **Follow-up — ✅ SHIPPED (pipelex `../_recursive`, `feature/Support-recursive-design`; unreleased — verify against editable pipelex until it ships):** validate's success output now states runnability in plain English: `✅ … this method is runnable.` on a complete bundle, or a `## Pending signatures (N)` heading + `⚠️ … NOT yet runnable …` line + bullets while pending. The JSON envelope adds `is_runnable` (= `pending_signatures` empty). The `mthds-vibe` Step 2/3 prose and the agent guide's "Reading runnability and `pending_signatures`" section now point the LLM at the explicit ✅/⚠️ verdict instead of inferring "done" from section absence (both still equivalent). The Claude hook is unchanged — it reads the `pending_signatures` array to *list* placeholders, and `[[ -n "$PENDING" ]]` already equals `!is_runnable`. → was **Finding F1 (now resolved)**.

#### B3 — `mthds-vibe` Step 3 (finalize) · `SKILL.md.j2:138`
```
mthds-agent validate bundle …/bundle.mthds -L …/ --graph
```
- Default markdown both streams. LLM reads. **Verdict: ✓ CORRECT.**

#### B4 — Other skills' `validate bundle` (no format flags) · `mthds-build`, `mthds-check`, `mthds-edit`, `mthds-explain`, `mthds-fix`, `mthds-pkg`, `error-handling`
- All call validate with **no** `--format`/`--error-format` → markdown success + markdown errors, read by the LLM. **Verdict: ✓ CORRECT** (markdown default is exactly what an LLM wants; nothing to change).

#### B5 — `inputs bundle` · `mthds-vibe`, `mthds-build`, `mthds-edit`, `mthds-run`, `mthds-inputs`
- Default JSON stdout. The LLM shows the input schema/template to the user (and `/mthds-inputs` consumes it). **Verdict: ✓ ACCEPTABLE** — this is *structured data*, not an error or explanation; JSON is the natural shape for a schema regardless of consumer. (Not a "format follows consumer" case.)

#### B6 — `run bundle` · `mthds-run`, `mthds-vibe`, `mthds-build`, `mthds-edit`, `mthds-explain`, `mthds-inputs`
- Default compact concept JSON stdout = the method *result* (data the LLM displays / pipes via `--with-memory`). Errors: default (assume markdown). **Verdict: ✓ ACCEPTABLE** for stdout (data). *Open:* nobody parses `run` errors programmatically today, so markdown-default errors are fine; revisit only if a software consumer of `run` errors appears.

#### B7 — `concept` / `pipe` · `mthds-build`
- Raw TOML stdout — the agent splices the validated TOML into the bundle. **Verdict: ✓ CORRECT** (TOML is the artifact the agent needs verbatim).

#### B8 — `models` / `check-model` · `mthds-build`
- Markdown stdout. LLM reads. **Verdict: ✓ CORRECT.**

#### B9 — `doctor` · `mthds-run`, `mthds-runner-setup`
- Markdown stdout (LLM reads). Contrast with A2 (session-start hook) which uses `--format json` because *software* parses it. **Verdict: ✓ CORRECT** — same command, format correctly chosen per consumer in each context. A clean illustration of the rule.

#### B10 — Status-token commands: `bootstrap`, `update-check`, `mthds-env-check` · `preamble`, `mthds-upgrade`, env-check
- Emit a bespoke line protocol (`BOOTSTRAP_COMPLETE <json>`, `UP_TO_DATE …`, `MTHDS_AGENT_OUTDATED <i> <r>`). The LLM matches the leading token; some carry a JSON tail for detail. **Verdict: ✓ CORRECT** (a status protocol designed for exactly this).

#### B11 — `package` / `install` / `publish` / `share` · respective skills
- JSON/status stdout the LLM relays. **Verdict: ✓ ACCEPTABLE** (mostly status/data; not prose-errors-to-LLM). Not audited in depth — flag if a programmatic consumer appears.

---

## Findings (the cases to decide on)

| # | Where | Problem | Status / fix |
|---|-------|---------|--------------|
| ~~**F1**~~ | `mthds-vibe` Step 2 | `--format json` (no `--error-format`) → errors came back JSON to an LLM. | ✅ **RESOLVED 2026-06-08** — Fix B applied (dropped `--format json`; reads the markdown `## Pending signatures` section). |
| **F2** | Codex hook (mthds-js `codex-hook.ts:285`) | Relies on the *default* error format being markdown (no explicit pin); also still strict (no `--allow-signatures`). | OPEN — fold into **Phase 5**: `… --allow-signatures --error-format markdown`. |
| ~~**F3**~~ | `mthds-agent-guide.md.j2` ("Agent CLI" + "Understanding JSON Output") | Claimed *"JSON on stdout: … validate …"* — but `validate` defaults to **markdown**. Misleading. | ✅ **RESOLVED 2026-06-08** — moved `validate` to the markdown-on-stdout bullet, qualified the errors bullet (validate = markdown errors by default, two-stream controls), and corrected the "Understanding JSON Output" note (validate defaults to markdown; `--format json` for the envelope). |

> **Aside (out of scope, noted in passing):** `docs/codex-vs-claude-hooks.md` says the Codex hook runs *"plxt lint, plxt fmt only — Stage 3 disabled"*, but `codex-hook.ts` clearly has a Stage 3 (`runPipelexValidate` + `classifyStage3Result`), and the repo `CLAUDE.md` documents three stages. That doc is stale — fix when touching Codex docs.

## Open questions / to verify

- **`run bundle` error format** — untested. If a software consumer of `run` errors ever exists, pin it; today only LLMs read them, so markdown-default is fine.
- ~~**F1 fix choice (A vs B)**~~ — RESOLVED: **B** chosen and applied. Step 2 reads the markdown `## Pending signatures` section; guide updated to say an LLM reads markdown directly and JSON is for programmatic consumers. Pipelex handoff (explicit English runnability verdict + JSON `is_runnable`) has since **shipped** and is now consumed by the skill prose + guide (see B2 follow-up).
- **Should `inputs`/`run` data output ever be markdown for the LLM?** Probably not — they're data the agent forwards/displays, not prose it reasons over. Left as ✓ ACCEPTABLE; revisit only if it proves noisy in practice.
