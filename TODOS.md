# TODOS — adapt mthds-plugins to pipelex 0.29.x output changes

This document is a working plan, designed to survive a cold-start handoff. Read this whole file before resuming.

## 0. Background — why we're doing this

Pipelex `v0.29.0` (2026-05-20) flipped agent CLI `run` / `validate` / `init` to **markdown by default** on both stdout and stderr (the success and error paths can be set independently via `--format` / `--error-format`). `models` / `check-model` / `doctor` were already markdown-default. `inputs` / `concept` / `pipe` / `install` / `package` are unaffected (still JSON / raw TOML). The `pipelex-agent validate bundle` graph flag was renamed `--format` → `--graph-format` in the same release. See `../pipelex/CHANGELOG.md:54-58` for the canonical wording.

This is good for skill agents (LLMs read markdown better than JSON) — but it has three consequences in this repo:

1. **The PostToolUse hook is silently broken on pipelex 0.29.x.** `templates/hooks/validate-mthds.sh.j2` parses the validate-bundle stderr as JSON. On 0.29.x stderr is markdown by default, the parse fails, the script falls into its "unexpected output, warn and pass" branch — meaning broken `.mthds` files no longer get blocked. Hook must opt back into JSON via `--error-format json`.
2. **Skill prose claims JSON-on-stdout for `run` / `validate` / `init`** in several places — wrong now. Agents using these skills will receive markdown and get confused if the skill tells them to parse JSON envelope fields like `main_stuff.json`.
3. **`/mthds-fix` iterates structured `validation_errors[]`** to look up per-error fix strategies. That contract needs JSON; the skill must opt back into `--format json` for its validate calls.

Cross-repo coupling: the `min_mthds_version` bump shipped from here must not predate the `mthds-agent` release that floors pipelex `>=0.29.1`. That mthds-agent release is tracked in `../mthds-js/TODOS.md`. **Do not release this plugin before mthds-js ships the floor bump and a tagged version is available on npm.**

User decision (2026-05-23) ratifying the framing above:
- ✅ Keep pipelex markdown default for skill agents (do not force `--format json` in passthrough).
- ✅ Fix the hook to require JSON explicitly (it's a bash script, not an agent).
- ✅ Rewrite skill docs to markdown-first for `run` / `validate` / `init`.
- ✅ Pin `--format json` in `/mthds-fix` (structured iteration is the contract there).
- ❌ Do not yet surface new envelope fields (`error_category`, `RemoteConfigStaleWarning`, etc.) — deferred.

### Affected files (audit, before any edits)

| # | File | Line(s) | What's wrong on 0.29.x | Fix bucket |
|---|---|---|---|---|
| H1 | `templates/hooks/validate-mthds.sh.j2` | 93 | `mthds-agent validate bundle` invoked without `--error-format json`; stderr is markdown; the Node parser at line 107 fails and the hook turns into a no-op for broken `.mthds` | Phase 2 |
| H2 | `templates/hooks/session-start.sh.j2` | 15 | Already passes `--format json` explicitly — **not affected** | — |
| D1 | `templates/skills/shared/mthds-agent-guide.md.j2` | 36-40 | Output-format table miscategorizes `run` / `validate` / `init` as JSON-on-stdout, errors as JSON-on-stderr | Phase 3 |
| D2 | `templates/skills/shared/mthds-agent-guide.md.j2` | 90-126 | "Understanding JSON Output" section is JSON-framed; should be markdown-first with JSON as the `--with-memory` sub-case | Phase 3 |
| D3 | `templates/skills/shared/mthds-agent-guide.md.j2` | 243 | `--format <format>` graph flag is now `--graph-format` (pipelex 0.29.0 breaking change visible through passthrough) | Phase 3 |
| D4 | `templates/skills/shared/mthds-agent-guide.md.j2` | 263, 269 | Reference rows for `run bundle` / `check-model` mention "compact output" / "markdown or JSON" — fine but should align with the new framing | Phase 3 |
| D5 | `templates/skills/mthds-run/SKILL.md.j2` | 9, 154-220 | Step 5 is built around parsing JSON; default is markdown which is already human-readable — agent should show stdout directly | Phase 3 |
| D6 | `templates/skills/mthds-check/SKILL.md.j2` | 50-53 | "Parse the JSON Output" — skill is read-only review; markdown is sufficient | Phase 3 |
| D7 | `templates/skills/mthds-build/SKILL.md.j2` | 311 | Claims "the JSON output includes the path in `graph_files`" — only true with `--format json`. In markdown mode the path appears in stderr logs | Phase 3 |
| F1 | `templates/skills/mthds-fix/SKILL.md.j2` | 25-33, 95-100 | Iterates `validation_errors[].error_type` — needs JSON. Pin `--format json` on validate calls in this skill | Phase 4 |
| V1 | `targets/defaults.toml` | `[vars] min_mthds_version` | Must be bumped to the mthds-agent version that floors pipelex `>=0.29.1` (TBD — set after mthds-js cuts the release) | Phase 5 |

### Key uncertainty to resolve in Phase 1

What does `pipelex-agent validate bundle <broken.mthds>` actually emit on stderr in markdown mode today? Specifically: does the markdown still embed `error_type` / `pipe_code` per validation error, or does it drop them in favor of prose? This drives whether `/mthds-fix` can stay markdown-friendly or **must** pin `--format json` (the current assumption is must-pin, but verifying is cheap).

## 1. Phase 1 — Verify & audit (read-only)

No edits. Goal: lock in the assumptions so later phases are mechanical.

- [ ] **1.1** Reproduce the hook breakage. Pick a known-broken `.mthds` file (or hand-write one with `missing_input_variable`). Run `mthds-agent validate bundle <file> -L <dir>/` with current mthds-agent + pipelex 0.29.x. Capture stderr to a file. Confirm `python3 -c "import json; json.load(open('err'))"` **fails** — proving the hook's `JSON.parse(stderr)` path is now broken.
- [ ] **1.2** Re-run the same command with `--error-format json` appended. Confirm stderr parses as JSON and the `validation_errors` array structure matches what `validate-mthds.sh.j2:120-138` expects (`e.pipe_code`, `e.message`).
- [ ] **1.3** Re-run a third time without `--error-format json` but capture markdown stderr. Inspect: does it still mention `error_type` and `pipe_code` per error? Record verbatim a sample of 2-3 errors. This decides whether `/mthds-fix` is markdown-tolerable (option B) or must pin JSON (option A — current assumption).
- [ ] **1.4** Confirm `--error-format json` is accepted by the mthds-agent version the user has installed locally. If their `mthds-agent --version` predates the pipelex 0.29.0 floor, the flag won't exist — skip this verification and note that Phase 2 depends on the mthds-js release landing first.
- [ ] **1.5** Grep `templates/` for any other call site to a markdown-default pipelex-agent command that parses JSON. Specifically: `grep -rn "JSON.parse\|json.load" templates/`. Confirm only `validate-mthds.sh.j2:31, 107` and `session-start.sh.j2:23, 38` show up — and that session-start is OK (already passes `--format json`).
- [ ] **1.6** Confirm the mthds-js work is unblocked or already in flight. Read `../mthds-js/TODOS.md` "Checkpoint 1 notes" — if Phase 1 there hasn't been executed, this repo's Phase 2 must wait (we depend on the floor bump release).

### CHECKPOINT 1 — STOP

Before Phase 2, fill in the section below. **Do not start Phase 2 until this section is filled in and reviewed.**

**Checkpoint 1 notes** (fill in during execution):

- Result of 1.1 (stderr-as-JSON parse fails? yes/no):
- Result of 1.2 (`--error-format json` produces parseable JSON with expected fields? yes/no):
- Result of 1.3 (markdown stderr carries `error_type` / `pipe_code`? quote samples):
- Result of 1.4 (`--error-format json` accepted by installed mthds-agent? yes/no, version):
- Result of 1.5 (other JSON-parse sites found? list):
- Result of 1.6 (mthds-js Phase 1 done? Floor bump release ETA?):

**Decisions taken at Checkpoint 1:**
- `/mthds-fix` strategy: pin `--format json` (option A) or trust markdown (option B):
- `min_mthds_version` target (must match mthds-js floor bump release):
- Any other JSON-parse site that needs fixing alongside the hook:

## 2. Phase 2 — Fix the PostToolUse hook

Goal: make the validate hook reliable on pipelex 0.29.x.

- [ ] **2.1** Edit `templates/hooks/validate-mthds.sh.j2:93`. Change:
  ```bash
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?
  ```
  to:
  ```bash
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --error-format json >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?
  ```
  Rationale: success path exits at line 96 without reading stdout, so we don't need `--format json` — only the error path matters and only stderr is read. Keep stdout as default (markdown) to minimize the surface change.
- [ ] **2.2** Add a one-line comment above the invocation explaining *why* `--error-format json` is required: "pipelex 0.29.0+ defaults stderr to markdown; the JSON parser below requires structured output." This prevents the flag from being "cleaned up" later.
- [ ] **2.3** Smoke-test locally: build, install the dev plugin variant, write a broken `.mthds` file via the Edit tool, and confirm the hook blocks with a structured `validation_errors`-derived message. Then write a valid `.mthds` file and confirm the hook exits 0 silently.
- [ ] **2.4** Run `make build` and inspect the rendered `mthds-dev/hooks/validate-mthds.sh` and `mthds/hooks/validate-mthds.sh` to confirm the flag landed. The two should differ only in template vars (install commands), not in the validate invocation.

### CHECKPOINT 2 — STOP

Before Phase 3, fill in below.

**Checkpoint 2 notes** (fill in during execution):

- Hook edit applied? (yes/no, summary):
- Smoke test result (block on broken / pass on valid):
- `make build` clean? Both rendered hook files contain `--error-format json`?
- Anything surprising:

**Recommended:** create an intermediate commit at this checkpoint. The doc/skill changes in Phase 3 are big and should land as their own commit so a bisect can isolate hook regressions from doc-only changes.

## 3. Phase 3 — Update skill docs (markdown-first)

Goal: align the prose in `templates/skills/` with the new default behavior. No behavioral change to commands, just docs.

- [ ] **3.1** `templates/skills/shared/mthds-agent-guide.md.j2:36-40`. Rewrite the output-format bullets:
  - `**Markdown on stdout (default), JSON with --format json**: run, validate, init`
  - `**JSON on stdout (always)**: inputs, install, package`
  - `**Raw TOML on stdout (always)**: concept, pipe`
  - `**Markdown on stdout (always)**: models, check-model, doctor`
  - `**Errors**: markdown on stderr by default; JSON with --error-format json (which defaults to whatever --format was set to). Exit code 1.`
- [ ] **3.2** Same file, lines 90-126 ("Understanding JSON Output"). Rename section to "Understanding Output". Reframe:
  - **Default**: stdout is markdown — already human/LLM-readable. Display it directly to the user.
  - **`--with-memory`** (for piping between methods): stdout is the JSON envelope (`main_stuff` + `working_memory`).
  - **`--format json`** (when programmatic structure is needed, rare for skill agents): stdout is the compact concept JSON.
- [ ] **3.3** Same file, line 243. Change `--format <format>` graph option to `--graph-format <format>`. Add a one-line note: "Renamed from `--format` in pipelex 0.29.0 — required for graph rendering on the new floor."
- [ ] **3.4** Same file, lines 263, 269. Update the command reference table:
  - `mthds-agent run bundle`: drop "compact output by default" wording; replace with "Markdown by default; `--with-memory` for the piping envelope; `--format json` for compact concept JSON."
  - `mthds-agent validate bundle`: clarify markdown-default; mention `--error-format json` for programmatic error handling.
- [ ] **3.5** `templates/skills/mthds-run/SKILL.md.j2`. Rewrite Step 5 around three modes:
  - **Default (markdown)**: show stdout directly. The CLI already formats the main concept for the user. No JSON unpacking needed.
  - **`--with-memory`**: existing JSON-envelope guidance (`main_stuff` vs `working_memory.root`) — keep mostly as-is, but reframe as the piping case, not the default.
  - **`--format json`** (rare): keep a short pointer for agents that genuinely need structured concept JSON.
  
  Delete the "compact mode" / "with-memory mode" dichotomy at lines 152-156 — the new framing replaces it. Also rewrite line 9 ("Execute MTHDS method bundles and interpret their JSON output") — drop "JSON".
- [ ] **3.6** `templates/skills/mthds-check/SKILL.md.j2:50-53`. Rewrite Step 4. Change "Parse the JSON Output" → "Read the Output". Replace bullets with: "On success, the CLI prints a green confirmation. On error, it prints the validation errors with `error_type` and `pipe_code` for each. Either way, summarize for the user." Reference error-handling.md for recovery — same as before.
- [ ] **3.7** `templates/skills/mthds-build/SKILL.md.j2:311`. Replace "The JSON output includes the path in `graph_files`" with "The path appears in the runtime output (and in stderr logs)." Same correction wherever `graph_files` is mentioned as a top-level JSON field (grep for it).
- [ ] **3.8** Grep the templates one more time for stale JSON-framing: `grep -rn "JSON.*stdout\|JSON output\|parse.*JSON\|\.json\b" templates/skills/`. Sweep any other lines that imply JSON is the default for `run` / `validate` / `init`.
- [ ] **3.9** Run `make build`. Diff the rendered `mthds/skills/` and `mthds-dev/skills/` against the previous build — sanity check that only intended files changed.

### CHECKPOINT 3 — STOP

Before Phase 4, fill in below.

**Checkpoint 3 notes** (fill in during execution):

- Files edited (with one-line summary of each change):
- Stale JSON-framing lines found by 3.8 and how each was handled:
- `make build` clean? Rendered diff matches intent?
- Any prose that turned out to be hard to rewrite — flag for follow-up:

## 4. Phase 4 — Pin `--format json` in `/mthds-fix`

Goal: make the fix-loop's structured iteration reliable. This is the one skill where markdown-default would break the contract.

This phase is gated on the **Checkpoint 1 decision** about option A (pin JSON) vs option B (trust markdown). If 1.3 found markdown carries `error_type` clearly enough to drive the fix-strategy table, switch to B and skip 4.1-4.2.

- [ ] **4.1** `templates/skills/mthds-fix/SKILL.md.j2:25-27`. Change the validate command in Step 1 to:
  ```bash
  mthds-agent validate bundle <file>.mthds -L <bundle-directory>/ --format json
  ```
  Add a one-line note above the command: "Pin `--format json` here — this skill iterates structured `validation_errors` to look up per-error fix strategies."
- [ ] **4.2** Same file, line 98 (Step 4 re-validate command). Apply the same `--format json` pin. And line 106 (`--graph` follow-up after success) — pin both `--format json` and check the `--graph` invocation works alongside `--graph-format` (post-rename) if reactflow is also requested.
- [ ] **4.3** `templates/skills/mthds-check/SKILL.md.j2:46`. Decision: does `/mthds-check` (read-only review) also need JSON? Default position: **no**, markdown is fine for a human-readable report. But if Checkpoint 1.3 shows markdown drops error metadata, reconsider. Document the decision here.
- [ ] **4.4** Run `make build`. Confirm the rendered `mthds-fix/SKILL.md` contains the `--format json` pin verbatim.

### CHECKPOINT 4 — STOP

**Checkpoint 4 notes** (fill in during execution):

- Option chosen (A pin / B trust markdown):
- Files edited:
- mthds-check decision (JSON pin or markdown):
- `make build` result:

## 5. Phase 5 — Version coordination & release prep

Goal: bump `min_mthds_version` to the mthds-agent floor that requires pipelex `>=0.29.1`. Do not release ahead of mthds-js.

- [ ] **5.1** Confirm the mthds-js floor-bump release has shipped to npm. Check `https://www.npmjs.com/package/mthds` for the new version, and confirm `npm view mthds version` reports it. Record the exact version string here.
- [ ] **5.2** Edit `targets/defaults.toml`. Change `[vars] min_mthds_version` to the version recorded in 5.1.
- [ ] **5.3** Run `make check` — this validates the freshness of build outputs and runs lint/type checks. Should be silent on success.
- [ ] **5.4** Run `make test` — unit tests.
- [ ] **5.5** Run the `internal-tools` integration tests if Docker is available (`make build && make agent-test` from the workspace root per the workspace `CLAUDE.md`). These exercise the install/upgrade pathway and would catch a min-version typo. If Docker is not running, ask the user to start it — do not skip.
- [ ] **5.6** Use `/release` skill (or follow its conventions manually): bump `targets/prod.toml`, `targets/dev.toml`, `targets/codex.toml` plugin versions; update `CHANGELOG.md` with a new section describing:
  - **Fixed**: PostToolUse validate hook no longer silently skips broken `.mthds` files on pipelex `0.29.0+` (now passes `--error-format json` to opt back into structured stderr).
  - **Changed**: `min_mthds_version` floor bumped to `<X.Y.Z>` to require the mthds-agent release that floors pipelex `>=0.29.1`. Cite the breaking changes from pipelex `v0.29.0` (agent CLI markdown default, `validate bundle --format → --graph-format`) that motivate the floor.
  - **Changed**: Skill docs (`mthds-agent-guide.md`, `mthds-run/SKILL.md`, `mthds-check/SKILL.md`, `mthds-build/SKILL.md`) rewritten to be markdown-first for `run` / `validate` / `init`.
  - **Changed**: `/mthds-fix` now pins `--format json` for its validate calls (its fix loop iterates structured `validation_errors`).
- [ ] **5.7** Create the release branch via `/release`. Do not merge until a human approves.

### CHECKPOINT 5 — STOP / ready to land

**Checkpoint 5 notes** (fill in during execution):

- mthds-agent version pinned as floor:
- `make check` / `make test` / integration tests results:
- CHANGELOG entry summary:
- Release branch name:
- Outstanding follow-ups for a future session:

**Hand-off when stopping mid-phase:**
- Branch state (clean / dirty, which files):
- Commits created in this session:
- Next concrete step to resume:
- Cross-repo blocker status (mthds-js release shipped? PR open?):

## 6. Out of scope for this round (don't do, but track)

Capture so they don't get lost.

- Surface new pipelex `v0.29.0` error envelope fields (`error_category`, `model`, `provider`, `retryable`) in `error-handling.md.j2` — wait until mthds-js plumbs them through `agent_error(...)`.
- Surface `RemoteConfigStaleWarning` in the docs once mthds-js routes the warning to the user. Same gate.
- Document the new `*ModelNotFoundError` family (`LLMModelNotFoundError`, `ImgGenModelNotFoundError`, `ExtractModelNotFoundError`, `SearchModelNotFoundError`) in `error-handling.md.j2` "Model & Config Errors" table, with the recovery hint "Run `mthds-agent check-model <ref> --type llm`". Cheap, useful, defer until mthds-js wires the hint registry.
- Document `PipeStructure` operator in `templates/skills/shared/mthds-reference.md.j2`. Useful for `/mthds-build` authors.
- Document the new `gemini-3.5-flash` entry — actually, no doc work needed since `mthds-agent models` surfaces it automatically. Just remember the model exists when authoring example methods.
- `--cost-report` / `--no-cost-report` from pipelex `v0.29.1` — flows through passthrough; no plugin change required. If `/mthds-run` ever grows a cost-aware mode, that's where it belongs.
