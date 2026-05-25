# Plan — validate hook rewrite (markdown-first + additionalContext warnings)

**Created:** 2026-05-26
**Status:** Active — paused for fresh-session cold start

---

## Cold-start resume guide (READ THIS FIRST)

You are picking this up in a fresh session. Here's the minimum you need to know to act:

**Repo:** `/Users/lchoquel/repos/Pipelex/mthds-plugins` — branch `fix/Pipelex-output-changes`.

**What's done already:**
- pipelex 0.30.1 is installed locally (`pipelex-agent --version` → `0.30.1`). It has the clean-stderr fix (no DEBUG telemetry preamble polluting the JSON envelope or markdown error output). Verified end-to-end on 2026-05-26.
- Working tree has a partial floor bump from 2026-05-25: `targets/defaults.toml` `min_mthds_version = "0.8.0"`, `targets/{prod,dev,codex}.toml` plugin version `0.11.3`, `.claude-plugin/marketplace.json` `0.11.3`, plus regenerated artifacts under `mthds/`, `mthds-dev/`, `mthds-codex/`. CHANGELOG has a draft v0.11.3 entry that will need rewriting.
- TODOS.md has a STATUS banner pointing at THIS plan doc; original Phases 1/2/5 are superseded.
- Three test bundles for hook verification are in `wip/`: `bad_bundle.mthds` (missing pipe ref), `bad_concept_ref.mthds` (native-concept clash + bad sigil), `bad_field_type.mthds` (bogus pipe type), `missing_input_in_prompt.mthds` (undeclared input).
- Earlier handoff at `wip/handoff-2026-05-25-pipelex-floor-bump.md` has historical context — read only if you need it.
- The pipelex 0.30.2 prompt (for a separate session in `../pipelex`) is at `wip/pipelex-0.30.2-prompt.md`.

**What's NOT done:**
- The actual hook rewrite (C.1 below).
- The hook test suite rewrite (C.2 below).
- Adjusting min_mthds_version to the published mthds-js 0.8.1 value (C.3 — confirm via `npm view mthds version`).
- The smaller bug fixes (C.5).
- CHANGELOG rewrite (C.6).
- Rebuild / verify / ship (C.7-C.8).

**Pre-flight checks before touching code:**

1. `cd /Users/lchoquel/repos/Pipelex/mthds-plugins && git status -sb` — confirm branch is `fix/Pipelex-output-changes` and the partial floor bump is still present in working tree.
2. `mthds-agent --version` — should report at least `0.8.0`. If `0.8.1` (or newer) is published per `npm view mthds version`, upgrade locally: `npm install -g mthds@latest`.
3. `pipelex-agent --version` — should report `0.30.1` or newer. If pipelex 0.30.2 has shipped (check `pip index versions pipelex` or PyPI), upgrade: `uv tool install --reinstall pipelex==<latest>`. Either version works for the hook rewrite — 0.30.2 just lets you skip the `## Error source` stripping in the hook (still safe to keep the strip as belt-and-suspenders).
4. `mthds-agent validate bundle wip/bad_bundle.mthds -L wip/ 2>/tmp/err.md; cat /tmp/err.md | head -20` — confirm you see clean markdown stderr starting with `# Error: <ErrorType>` and a `## Details` section with `- **error_domain:** input`. No `DEBUG` preamble. If `DEBUG` lines appear, pipelex is older than 0.30.1; upgrade.

**Where to start:** Section "C. mthds-plugins (release v0.11.3 — THIS REPO)" below, sub-section **C.1**. The plan is sequential within C; A and B are independent repo work tracked separately.

---

## Background — what changed and why this plan exists

This plan supersedes the original Phase 2 of `TODOS.md` (which assumed a JSON-based hook fix). The verification on 2026-05-25 and 2026-05-26 surfaced two new facts that reshape the work:

1. pipelex 0.30.1 ships clean stderr (no startup DEBUG preamble) — verified end-to-end.
2. The pipelex JSON envelope for `validate bundle` errors no longer populates `validation_errors[]` for the cases the hook is supposed to BLOCK on; it returns a single top-level `error_type` / `error_domain` / `message`. The markdown envelope is equivalently structured and equally agent-readable (and the markdown is the *better* shape for the agent to act on).
3. Both Claude Code and Codex PostToolUse hooks support `hookSpecificOutput.additionalContext` (string, 10k chars max on Claude Code) — a non-blocking, agent-facing channel. This lets us inform the agent of config/runtime warnings without forcing it to edit the bundle.

The new architecture: hook reads pipelex's markdown stderr verbatim, BLOCKs with the markdown as `reason` for input-domain errors (agent fixes the file), or emits `additionalContext` for config/runtime errors (agent and user both informed, no false-positive edits).

---

## Goals

- Restore the validation safety-net: broken `.mthds` files saved through Claude Code / Codex must be blocked, with actionable feedback to the agent.
- Use pipelex's markdown error envelope directly as the agent feedback — no JSON parsing, no fragile schema dependency.
- Surface non-blocking warnings (config/runtime errors) to BOTH the agent (via additionalContext) and the user (via stderr).
- Trim pipelex's markdown error output to be agent-friendly (drop the internal stack-trace section).
- Coordinate the three-repo release sequence so consumers get the floor bump and the working hook together.

---

## Decisions taken (locked in)

- **Markdown for agents, JSON for tooling.** pipelex's markdown error envelope is the canonical agent-facing artifact. JSON keeps richer diagnostic fields (`error_source`, structured per-error data) for programmatic callers.
- **Hook output format on Claude Code:** `hookSpecificOutput.additionalContext` (verified verbatim from https://code.claude.com/docs/en/hooks). 10k char cap. Block + additionalContext can both be set in the same response; both are honored.
- **Codex parity:** mthds-agent's existing Codex hook (`mthds-agent codex hook` in mthds-js) should gain the same additionalContext capability. Codex schema confirmed: `hookSpecificOutput.additionalContext` (string), agent sees it on next turn as a developer-role conversation item.
- **Backward compat is out of scope.** We pin to latest Claude Code / Codex floors as needed.
- **Sequence:** pipelex 0.30.2 → mthds-js 0.8.1 → plugin v0.11.3. mthds-js 0.8.1 is being cut now; pipelex 0.30.2 is independent and can ship in parallel.

### Claude Code PostToolUse hook output JSON shape (verbatim, verified 2026-05-26)

Source: https://code.claude.com/docs/en/hooks (PostToolUse output, lines 484-590).

**Block (existing behavior we'll keep for input-domain errors):**

```json
{"decision":"block","reason":"<markdown content shown to the agent>"}
```

**Non-blocking agent-facing context (new behavior we'll add for config/runtime warnings):**

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "<warning markdown — max 10000 chars>"
  }
}
```

**Both in the same response (block + extra context — supported, both honored):**

```json
{
  "decision": "block",
  "reason": "<block reason>",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "<extra info for the agent on top of the block>"
  }
}
```

**Key facts:**
- `additionalContext` is a STRING (not an array). Max **10,000 characters** on Claude Code. We'll truncate to 9500 with a `[truncated]` marker as a safety margin.
- `hookEventName` value MUST be `"PostToolUse"` exactly when used in a PostToolUse hook response.
- `systemMessage` (top-level string field) is user-only — does NOT reach the agent. Don't confuse it with `additionalContext`.
- stderr written by the hook with exit 0 → user terminal only, does NOT reach agent.
- Block precedence: the file Write/Edit already happened (PostToolUse fires after). The block signal tells the agent the result is rejected; the agent revises and tries again.

### Codex PostToolUse hook output JSON shape (for the mthds-js side, not this plugin)

Same path: `hookSpecificOutput.additionalContext` (string). Schema lives in `openai/codex` repo at `codex-rs/hooks/schema/generated/post-tool-use.command.output.schema.json`. mthds-js's `mthds-agent codex hook` (in `src/agent/commands/codex-hook.ts`) currently only emits the block variant; B-track will add the additionalContext channel there.

---

## Work breakdown

### A. pipelex (release 0.30.2)

Repo: `/Users/lchoquel/repos/Pipelex/pipelex/`

The markdown error envelope today includes a `## Error source` section with internal stack frames. Useless and confusing to an agent reading the error to fix a `.mthds` file. Drop or relocate.

- [ ] **A.1** Locate the markdown error formatter in pipelex (likely under `pipelex/cli/agent_cli/` or a shared markdown error renderer). Find where the `## Error source` section is emitted.
- [ ] **A.2** Decide: drop the `## Error source` section entirely from markdown, OR gate it behind a verbose/debug flag. Recommended: drop entirely. JSON output (`--error-format json`) keeps `error_source` for programmatic consumers; markdown is for humans / LLMs.
- [ ] **A.3** Implement the change. Update any pipelex tests that snapshot the markdown error format.
- [ ] **A.4** Bump pipelex version to 0.30.2. Update `pipelex/CHANGELOG.md` with a `### Changed` entry describing the markdown trim.
- [ ] **A.5** Run pipelex's `make agent-check` and `make agent-test` (or equivalents) — both must be clean.
- [ ] **A.6** Publish pipelex 0.30.2 to PyPI.

### B. mthds-js (release 0.8.1)

Repo: `/Users/lchoquel/repos/Pipelex/mthds-js/`

mthds-js 0.8.1 is being released right now per user (2026-05-26). Need to confirm what it ships and whether the Codex hook gets the additionalContext upgrade as part of this release or a follow-up.

- [ ] **B.1** Confirm what mthds-js 0.8.1 includes — at minimum, raising the pipelex/pipelex-agent floor to `>=0.30.1` (already verified working with the clean-stderr fix). Check `mthds-js/CHANGELOG.md` and `package.json`.
- [ ] **B.2** Decide: does mthds-js 0.8.1 also update `mthds-agent codex hook` (in `src/agent/commands/codex-hook.ts` per earlier research) to use `hookSpecificOutput.additionalContext` for warnings? If yes, ensure it's in the release. If no, plan a follow-up 0.8.2 — but the plugin can ship without it on the Claude side.
- [ ] **B.3** Confirm mthds-js 0.8.1 published to npm: `npm view mthds version` returns `0.8.1`.
- [ ] **B.4** Confirm `mthds-agent --version` reports 0.8.1 on a fresh `npm install -g mthds@latest`.

### C. mthds-plugins (release v0.11.3 — THIS REPO)

Repo: `/Users/lchoquel/repos/Pipelex/mthds-plugins/` — branch `fix/Pipelex-output-changes` (already partially staged from 2026-05-25).

#### C.1. Rewrite the validate hook (markdown + additionalContext)

- [ ] **C.1.1** Edit `templates/hooks/validate-mthds.sh.j2`. Replace Stage 3 (currently lines ~87-157, starting after the `STAGE 3:` comment banner) with the markdown-based decision tree below.
- [ ] **C.1.2** Stage 3 new shape (pseudocode — bash + a small Node helper for the additionalContext JSON):

  ```bash
  # =====================================================================
  # STAGE 3: mthds-agent validate bundle — semantic validation
  # Markdown stderr is the canonical agent-facing artifact. BLOCK on
  # input-domain errors (agent fixes the bundle); emit additionalContext
  # for config/runtime errors (agent informed, no false-positive edits).
  # =====================================================================
  PARENT_DIR=$(dirname "$FILE_PATH")
  EXIT_CODE=0
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?

  if [[ "$EXIT_CODE" -eq 0 ]]; then exit 0; fi

  # Strip pipelex's internal stack trace (## Error source section to EOF).
  # Stopgap until pipelex 0.30.2 drops the section from markdown; safe
  # no-op once it does.
  ERR_MD=$(sed '/^## Error source/,$d' "$TMPERR")

  # Extract error_domain from the "## Details" section.
  # Format pipelex emits: `- **error_domain:** input`
  DOMAIN=$(printf '%s\n' "$ERR_MD" | sed -n 's/^- \*\*error_domain:\*\* *//p' | head -1 | tr -d '[:space:]')

  case "$DOMAIN" in
    config|runtime)
      # Environment issue, not a bundle issue. Inform agent + user, do not block.
      # User sees stderr; agent sees additionalContext.
      printf '[mthds-hook] Validation warning (domain=%s) for %s:\n%s\n' "$DOMAIN" "$FILE_PATH" "$ERR_MD" >&2
      node -e "
  const md = process.argv[1];
  const MAX = 9500;
  const ctx = md.length > MAX ? md.slice(0, MAX) + '\n\n[truncated, ' + (md.length - MAX) + ' chars omitted]' : md;
  process.stdout.write(JSON.stringify({hookSpecificOutput:{hookEventName:'PostToolUse',additionalContext:'Validation warning for ' + process.argv[2] + ' (' + process.argv[3] + ' domain — environment issue, do not edit the file):\n\n' + ctx}}) + '\n');
  " "$ERR_MD" "$FILE_PATH" "$DOMAIN"
      exit 0
      ;;
    *)
      # input-domain (or unknown/empty — default to block for safety).
      # BLOCK reason is the full trimmed markdown — agent reads it and fixes the bundle.
      _block "Validation failed for $FILE_PATH:

  $ERR_MD"
      exit 0
      ;;
  esac
  ```

  Notes for implementation:
  - The existing `_block()` helper at the top of the file (line ~33) already does the right thing: `process.stdout.write(JSON.stringify({decision:'block',reason:...}))`. Reuse it.
  - The existing `_jv()` helper and the entire Stage 3 Node decision script (lines ~100-155 in the current file) are deleted.
  - `TMPOUT` / `TMPERR` / the trap on EXIT (line ~57-59) stay — both stages still need them.
  - Stages 1 and 2 are untouched.

- [ ] **C.1.3** Truncate additionalContext to 9500 chars (safe margin under Claude Code's 10k cap). Already in the pseudocode via the Node helper. Pipelex error messages can be long when they pack multiple validation errors.
- [ ] **C.1.4** Keep stages 1 (`plxt lint`) and 2 (`plxt fmt`) unchanged.
- [ ] **C.1.5** Update the file's header comment block (lines 1-8) to reflect the new behavior — specifically, drop the line that says stage 3 "blocks or warns" and replace with "blocks on input-domain errors; emits agent additionalContext for config/runtime errors." Also update the line that says "Uses Node.js for JSON parsing" — Node is now only used to emit the additionalContext JSON, not to parse pipelex stderr.

#### C.2. Rewrite the hook test suite

- [ ] **C.2.1** Rename `tests/unit/test_hook_json_logic.py` → `tests/unit/test_hook_markdown_logic.py` (or similar — reflects the new format).
- [ ] **C.2.2** Rewrite all test cases:
  - Markdown stderr with `error_domain: input` and an `# Error: ...` header → expect BLOCK with the trimmed markdown as reason.
  - Markdown stderr with `error_domain: config` → expect exit 0 + JSON output with `additionalContext` set + stderr warning to user.
  - Markdown stderr with `error_domain: runtime` → expect exit 0 + additionalContext + stderr warning.
  - Markdown stderr with no `## Details` section / no error_domain → expect BLOCK (default to safety).
  - Empty stderr with non-zero exit → expect BLOCK with a generic "validation failed" reason.
  - Markdown with `## Error source` section → confirm it's stripped from BOTH block reason AND additionalContext.
  - Long markdown (>10k chars) → confirm additionalContext is truncated to 9500 chars with a "[truncated]" marker.
- [ ] **C.2.3** Ensure `make test` is green.

#### C.3. Floor bump (mthds-js)

- [ ] **C.3.1** Edit `targets/defaults.toml`: bump `min_mthds_version` from `"0.7.0"` to `"0.8.1"` (the published mthds-js version that floors pipelex `>=0.30.1`).
- [ ] **C.3.2** Working tree currently has it at `"0.8.0"` from 2026-05-25 — overwrite to `"0.8.1"`.

#### C.4. Plugin version bump

- [ ] **C.4.1** `targets/prod.toml`, `targets/dev.toml`, `targets/codex.toml`: `version = "0.11.2"` → `"0.11.3"`. Already done in working tree; keep.
- [ ] **C.4.2** `.claude-plugin/marketplace.json`: `metadata.version = "0.11.2"` → `"0.11.3"`. Already done; keep.

#### C.5. Smaller confirmed bugs (per code review on 2026-05-25)

- [ ] **C.5.1** `TODOS.md` lines 18-22: delete or rewrite the "Upstream status (updated 2026-05-25)" subsection — it claims pipelex 0.30.0 and mthds-js 0.8.0 are unpublished; both are published. Replace with a note pointing to this plan doc.
- [ ] **C.5.2** `templates/skills/shared/mthds-agent-guide.md.j2:243`: change `--format <format>` (graph flag) to `--graph-format <format>`. pipelex 0.29.0 renamed this flag; current floor is pipelex `>=0.30.1`.
- [ ] **C.5.3** `templates/skills/shared/mthds-agent-guide.md.j2:246`: reword the `graph_files` claim — change "The JSON output includes `graph_files`..." to be markdown-first: "The path to the generated graph appears in the stderr logs; when `--format json` is set, it's also in the JSON envelope as `graph_files`."
- [ ] **C.5.4** `docs/build-targets.md:46`: refresh stale example `min_mthds_version = "0.3.3"` to current canonical value (`"0.8.1"`).

#### C.6. CHANGELOG rewrite

- [ ] **C.6.1** Edit `CHANGELOG.md`. The current draft entry for v0.11.3 (added 2026-05-25) says the floor bump is sufficient and "no skill, hook, or script invocations needed adapting beyond the floor." That sentence is now provably false — the hook needed a substantial rewrite. Rewrite the entry as:
  - `### Fixed` — PostToolUse validate hook no longer silently passes broken `.mthds` files. Rewrote Stage 3 to use pipelex's markdown error envelope directly: BLOCKs on input-domain errors with the markdown as the agent-actionable reason; uses Claude Code's `hookSpecificOutput.additionalContext` to surface config/runtime warnings to the agent without blocking.
  - `### Changed` — `min_mthds_version` bumped to `0.8.1`. mthds-js 0.8.1 floors pipelex/pipelex-agent at `>=0.30.1`, which routes logs to stderr cleanly (was stdout pollution in pre-0.30) and suppresses startup telemetry-debug noise in the agent CLI's stderr (fixed in pipelex 0.30.1).
  - `### Changed` — Skill doc `mthds-agent-guide.md` updated for the pipelex 0.29 graph flag rename (`--format` → `--graph-format`) and markdown-first framing of error output.
- [ ] **C.6.2** Update CHANGELOG date to 2026-05-27 (or whenever the PR actually lands).

#### C.7. Rebuild and verify

- [ ] **C.7.1** `make build` — regenerate all three target trees (prod, dev, codex).
- [ ] **C.7.2** `make check` — must be silent on success.
- [ ] **C.7.3** `make test` — all unit tests pass.
- [ ] **C.7.4** Smoke test the rendered hook against `wip/bad_bundle.mthds`:
  - Manually invoke the rendered `mthds-dev/hooks/validate-mthds.sh` against a broken `.mthds`.
  - Confirm stdout emits `{"decision":"block","reason":"..."}` with markdown content.
  - Repeat for a valid `.mthds` — confirm exit 0 with no stdout output.
- [ ] **C.7.5** If Docker available: `make agent-test` from workspace root for internal-tools integration tests.

#### C.8. Ship

- [ ] **C.8.1** Show diff to user before any commit.
- [ ] **C.8.2** Commit on `fix/Pipelex-output-changes` branch. Squash or keep two commits (TODOS plan + bump+hook) per user preference.
- [ ] **C.8.3** Push and open PR to `main`. Title: `fix: rewrite validate hook for pipelex 0.30+ + floor bump to mthds-js 0.8.1`. Description should explain the hook architecture change, link to this plan doc, and note that it depends on mthds-js 0.8.1.

---

## Sequencing

```
pipelex 0.30.2     (independent — drop stack trace from markdown)
                          │
mthds-js 0.8.1     ──────►│  (in progress per user)
                          │     pins pipelex >=0.30.1 (or .2)
                          ▼
mthds-plugins v0.11.3     (this PR — uses mthds-js 0.8.1 floor, ships hook rewrite)
```

mthds-js 0.8.1 is the gate for the plugin release. pipelex 0.30.2 is independent — plugin can ship its hook with the stopgap stack-trace stripping; once 0.30.2 ships, the stripping becomes a no-op.

---

## Verification commands

Re-runnable test bundles in `wip/`:

| Bundle | Bug | Expected hook decision |
|---|---|---|
| `wip/bad_bundle.mthds` | Pipe references missing pipe (`build_scorecard_oops`) | BLOCK |
| `wip/bad_concept_ref.mthds` | Concept named `Document` clashes with native + bad sigil | BLOCK |
| `wip/bad_field_type.mthds` | `type = "PipeNotARealType"` | BLOCK |
| `wip/missing_input_in_prompt.mthds` | Prompt uses `@undeclared` not in inputs | BLOCK |

Smoke test once the hook is rewritten:

```bash
cd /tmp && rm -rf hook_verify && mkdir hook_verify && cd hook_verify
cp /Users/lchoquel/repos/Pipelex/mthds-plugins/wip/bad_bundle.mthds ./

# Simulate the PostToolUse hook input
PAYLOAD='{"tool_input":{"file_path":"'"$(pwd)"'/bad_bundle.mthds"}}'
echo "$PAYLOAD" | /Users/lchoquel/repos/Pipelex/mthds-plugins/mthds-dev/hooks/validate-mthds.sh

# Expected:
# - exit 0
# - stdout: {"decision":"block","reason":"# Error: LibraryError\n\n..."}
# - stderr: empty (or info-level only)
```

For the warning path (config/runtime), it's harder to trigger from `validate bundle` directly — validation is local and rarely needs config. May need to mock or skip the config/runtime smoke test, relying on unit tests for that branch.

---

## Out of scope (deferred)

Things that remain in the original `TODOS.md` and are NOT part of this release:

- TODOS Phase 3 (skill doc markdown-first rewrite for `/mthds-run`, `/mthds-check`, etc.) — quality-of-life, not a safety regression. Separate PR.
- TODOS Phase 4 (`/mthds-fix` skill pinning `--format json`) — `/mthds-fix` is interactive; misparse is loud, not silent. Separate PR.
- Codex hook updates beyond mthds-js 0.8.1 — if mthds-js 0.8.1 doesn't include the `additionalContext` upgrade for `mthds-agent codex hook`, it ships in 0.8.2 as a follow-up. Plugin's Claude-side hook is the priority.

---

## References

- Claude Code hook docs: https://code.claude.com/docs/en/hooks (lines 484-590 cover PostToolUse output format incl. additionalContext)
- Codex hook schema: `codex-rs/hooks/schema/generated/post-tool-use.command.output.schema.json` in the openai/codex repo
- Earlier handoff (2026-05-25): `./wip/handoff-2026-05-25-pipelex-floor-bump.md` — context on why pipelex 0.30.1 was needed and what was already done
- Original 5-phase plan: `./TODOS.md` — preserved for posterity; Phases 1-2-5 are subsumed by this plan; Phases 3-4 are deferred
- Cold-start prompt for pipelex 0.30.2 (A-track): `./wip/pipelex-0.30.2-prompt.md` — copy/paste into a fresh session in `/Users/lchoquel/repos/Pipelex/pipelex/`
- pipelex repo: `/Users/lchoquel/repos/Pipelex/pipelex/`
- mthds-js repo: `/Users/lchoquel/repos/Pipelex/mthds-js/`

---

## Suggested first commands on resume (cold start)

```bash
cd /Users/lchoquel/repos/Pipelex/mthds-plugins

# 1. Confirm branch + working tree
git status -sb | head -5

# 2. Confirm tool versions
mthds-agent --version
pipelex-agent --version
plxt --version

# 3. Confirm mthds-js 0.8.1 (or newer) is published
npm view mthds version

# 4. Sanity-check the hook still reproduces the bug we're fixing
cd /tmp && rm -rf hook_verify && mkdir hook_verify && cd hook_verify
cp /Users/lchoquel/repos/Pipelex/mthds-plugins/wip/bad_bundle.mthds ./
mthds-agent validate bundle bad_bundle.mthds -L ./ >stdout.txt 2>stderr.txt
echo "exit=$?"
head -20 stderr.txt        # should be clean markdown starting with "# Error:"
python3 -c "import json; json.load(open('stderr.txt'))" 2>&1 | head -3
# Expected: json.load FAILS (markdown isn't JSON) — that's the bug C.1 fixes.

# 5. Open the hook template and the test suite to size up the work
cd /Users/lchoquel/repos/Pipelex/mthds-plugins
wc -l templates/hooks/validate-mthds.sh.j2 tests/unit/test_hook_json_logic.py
```

If all the above looks right, jump to section C.1 and start editing.
