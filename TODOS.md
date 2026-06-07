# Recursive Method Building — Implementation Plan

Implementation tracker for the recursive (stepwise-refinement) rewrite of `mthds-vibe`. The full rationale, methodology, worked example, and decisions live in [wip/recursive/design.md](wip/recursive/design.md). **Read that first** — this file is the execution checklist, not the spec.

Companion docs: [wip/deferred-issues.md](wip/deferred-issues.md) (things intentionally postponed), [wip/revisit-vibe-scope-limits.md](wip/revisit-vibe-scope-limits.md).

## How to use this file

- Work top to bottom. Check boxes as you land each item (`- [x]`).
- **⛔ CHECKPOINTs are hard stops.** At each one: run the stated verification, then fill in its "Record before continuing" block with what you actually did/found, so a fresh session can resume cold. Do not blow past a checkpoint with unfilled context.
- Keep the "Files touched" map and "Open questions" / "Decisions log" current as you go.
- Source of truth is always the `.j2` template; never edit generated `mthds/` or `mthds-dev/` output directly. After any template/`targets/*.toml` edit: `make build`, then `/reload-plugins` to dogfood.

---

## ⚠️ Gating external dependency — read before starting

The **additive multi-file model** (a `PipeSignature` header reconciling with a concrete definition in a sibling file, cross-file concept resolution, and `pending_signatures` on validate) depends on pipelex **Part A + Part B**, which are **unreleased**. They live on the pipelex worktree branch `feature/Support-recursive-design` (`/Users/lchoquel/repos/Pipelex/_recursive`, plan: `_recursive/TODOS.md`, follow-ups: `_recursive/HANDOFF-recursive-followups.md`).

Current local state (verified at plan time):
- `pipelex --version` → **0.31.0** (a *released* build). 0.31.0 has lenient validation (`PipeSignature` + `--allow-signatures`) **but NOT** Part A+B reconciliation. The local `pipelex` is **not** the worktree — `~/.local/bin/pipelex`, not an editable uv-tool pointer.
- `mthds-agent` calls `pipelex` / `pipelex-agent` **by bare name** through `PATH`. So the plugin will exercise whatever `pipelex` resolves to.

Consequence:
- **All plugin work below can be built and dogfooded locally** *once* `pipelex` is repointed at the `_recursive` worktree (Phase 0).
- **Prod release waits** on: (a) the pipelex release that carries Part A+B (`> 0.31.0`), and (b) the matching `mthds-agent` version. The `min_mthds_version` bump (Phase 6) is the only step that hard-blocks on that release. Everything else proceeds now.

---

## Source-file map (where the work lands)

Plugin (this repo, `mthds-plugins/`):
- Claude hook template: `templates/hooks/validate-mthds.sh.j2` (Stage 3 at lines ~89–155; the `mthds-agent validate bundle ... -L "$PARENT_DIR/"` call is line ~97).
- Codex hook config template: `templates/hooks/codex-hooks.json.j2` (command is just `mthds-agent codex hook`; logic is in mthds-js).
- Orchestrator skill template: `templates/skills/mthds-vibe/SKILL.md.j2` (single-pass body to be replaced).
- Vibe cheat sheet (static asset, source of truth for syntax): `skills/mthds-vibe/references/vibe-cheat-sheet.md`.
- Shared CLI reference: `templates/skills/shared/mthds-agent-guide.md.j2`.
- Build renderer: `scripts/gen_skill_docs.py` (note `HOOK_TEMPLATES_BY_PLATFORM`, `SHARED_TEMPLATES`, `setup_static_assets`, freshness `check_freshness`). **No `agents/` support exists yet — Phase 3 adds it.**
- Packaging checks: `scripts/check.py` (`check_codex_no_claude_artifacts` etc.).
- Targets: `targets/defaults.toml` (`min_mthds_version = "0.9.0"`), `targets/{prod,dev,codex}.toml`.
- Build/check entry points: `Makefile` (`make build`, `make check`, `make agent-test`).

Codex hook logic (sibling repo, `mthds-js/`):
- `src/agent/commands/codex-hook.ts` — `runPipelexValidate()` (lines ~282–295) builds `["validate","bundle",file,"-L",libraryDir]`; Stage 3 wiring at ~368–393; markdown-stderr classification in `classifyStage3Result()` (~147–176).
- Tests: `tests/unit/agent/codex-hook.test.ts`.
- `codex apply-config`: `src/agent/commands/codex-config.ts` (context only — not changed here).

Pipelex runtime (sibling worktree, reference only — **already shipped**, do not re-implement):
- `/Users/lchoquel/repos/Pipelex/_recursive` on `feature/Support-recursive-design`.

---

## Phase 0 — Preflight: local runtime + version-floor recon (no plugin code)

Goal: make the local toolchain actually run the additive model, and pin down the open version question, before touching templates.

- [x] Repoint the local `pipelex` runtime at the worktree so the additive (Part A+B) flow is live locally:
      `uv tool install --force --editable /Users/lchoquel/repos/Pipelex/_recursive`
      Then verify: `pipelex --version`, and `grep editable ~/.local/share/uv/tools/pipelex/uv-receipt.toml` (confirms source is the worktree). This also repoints `pipelex-agent` / `pipelex-dev`, which is what the hooks invoke. (Revert later with `uv tool install --force pipelex`.) See the "Iterating on a local pipelex runtime" section of the workspace `CLAUDE.md`.
- [x] Smoke-test the primitive end-to-end by hand (no plugin yet): write a tiny two-file library in a scratch dir — a root `bundle.mthds` with one `PipeSignature` main pipe, plus a sibling concrete definition file of the same code referencing a sibling-declared concept — and confirm:
      - `mthds-agent validate bundle <root> -L <dir>/ --allow-signatures` passes (lenient).
      - Dropping `--allow-signatures` **fails** with a signatures-not-allowed error (strict).
      - The signature/concrete reconciliation works **across files** (Part A) and the cross-file bare concept ref resolves (Part B).
      - **(D2 — member-file validation)** `mthds-agent validate bundle <child> -L <dir>/ --allow-signatures` — pointing at a **domain-only child member** file (no `main_pipe`) — validates the **library**, not erroring on the missing root header. The hook fires `validate bundle <the-file-just-written> -L <dir>` on EVERY save, so most saves target a child, not the root. If this errors, it is a **pipelex bug** to fix in `../_recursive` (the generic hook stays simple). Record the result.
- [x] Confirm how `pending_signatures` is exposed on a **successful** validate: run `mthds-agent validate bundle <root> -L <dir>/ --allow-signatures` and inspect stdout. Determine the exact invocation needed to read it as JSON (default stdout format vs an explicit `--format json`). **This answer drives Phase 1.2 and Phase 5.2** — record it in Open Questions.
- [x] **(D3 — error-routing confirm)** With `--allow-signatures --format json` added, run a **failing** validate and confirm the **error report still goes to stderr as markdown** (so the hook's `error_domain` grep still works) while the **success output is JSON on stdout** (so `pending_signatures` is readable). Static reads of the pipelex source conflicted on this, so it MUST be checked by running it. If `--format json` JSON-ifies errors too, fall back to **two invocations** (one markdown for classify/block, one JSON for the nudge) — at the cost of validating the library twice per save. **This decides the Phase 1.2 implementation.**
- [x] Version-floor recon: identify which **pipelex release** will carry Part A+B (`> 0.31.0`) and which **mthds-agent** version ships/requires it. `min_mthds_version` tracks the *mthds-agent* version (currently `0.9.0`), not pipelex. If unknown/unreleased, leave a dated note and defer the actual bump to Phase 6. (Check `mthds-js` package version + its pipelex pin, and the pipelex changelog/release plan.)

### ⛔ CHECKPOINT 0 — runtime ready

Verification: the by-hand two-file smoke test passes lenient and fails strict, with cross-file reconciliation working.

Record before continuing (filled 2026-06-07):

- **pipelex version now resolving locally + confirmation it is the editable worktree:** `pipelex --version` → `pipelex 0.31.0` (and `pipelex-agent 0.31.0`). It IS the editable worktree: `~/.local/share/uv/tools/pipelex/uv-receipt.toml` shows `requirements = [{ name = "pipelex", editable = "/Users/lchoquel/repos/Pipelex/_recursive" }]`, and the JSON error `error_source` traces into `/Users/lchoquel/repos/Pipelex/_recursive/pipelex/...`. The version *string* is still `0.31.0` because the branch hasn't bumped `pyproject.toml` — Part A+B rides on top of it unreleased. Other tools: `mthds-agent 0.9.0`, `plxt 0.4.0`. (Revert when done: `uv tool install --force pipelex`.) Extras: reinstalled editable **with all runtime extras** — `uv tool install --force --editable "/Users/lchoquel/repos/Pipelex/_recursive[anthropic,bedrock,docling,fal,gcp-storage,google,google-genai,huggingface,linkup,mistralai,dynamodb,s3,temporal]"` — so a later phase can `run` against live providers, not just `validate`. Verified present in the tool venv (anthropic, boto3, docling, mistralai, temporalio, google-genai, huggingface_hub, linkup, fal_client all import). (`docs`/`dev` extras intentionally omitted — not needed at runtime.)

- **Smoke test (two-file library `/tmp/mthds-smoke/lib/`: root `bundle.mthds` = signature header `make_brief` + boundary concept `Brief`; sibling `make_brief.mthds` = concrete `PipeSequence` reconciling with the header, forward-declaring child signatures `write_draft`/`polish_brief`, owning intermediate concept `Draft`, referencing `Brief` cross-file):**
  - Lenient (`-L <dir> --allow-signatures`) → **PASS** (exit 0), lists "Pending signatures (2): polish_brief, write_draft". ✓
  - Strict (drop the flag) → **FAIL** (exit 1, `ValidateBundleError`, `error_domain: input`, message: "depends on PipeSignature placeholders… re-run with `--allow-signatures`"). ✓
  - **Part A** (signature/concrete reconciliation across files): `make_brief` header in `bundle.mthds` + concrete in `make_brief.mthds` validated as `SUCCESS` with no duplicate-code error. ✓
  - **Part B** (cross-file bare concept ref): `make_brief.mthds` references `Brief` (declared only in `bundle.mthds`) and resolved with no unresolvable-concept error. ✓
  - **D2** (member-file validation): `validate bundle make_brief.mthds -L <dir> --allow-signatures` — pointing at the domain-only child (no `main_pipe`) — **PASS** (exit 0), validated all 3 pipes, same library-wide `pending_signatures`, **no** missing-root-header error. ✓ So the hook validating a child save works. No pipelex bug to file.

- **Exact validate invocation + where `pending_signatures` appears on success:** On success, `... --allow-signatures --format json` emits a clean JSON object on **stdout** (stderr empty) with a top-level `pending_signatures` array (e.g. `["smoke_test.polish_brief","smoke_test.write_draft"]`) plus `success:true`, `validated_pipes`, `total_pipes`. **Also** (default format, no `--format json`) success prints the same info as markdown on **stdout** under a `## Pending signatures (N)` section with `` - `code` `` list items (stderr empty). Either source is readable; both land on stdout on success.

- **D3 error-routing — RESOLVED, single invocation holds (the original plan is fine):** the `pipelex-agent` CLI exposes **two independent** format options (by design — see `_recursive/pipelex/cli/agent_cli/CLAUDE.md` §"Output format" and `validate/bundle_cmd.py:70–92`): `--format markdown|json` controls **success output (stdout)**, `--error-format markdown|json` controls **error reporting (stderr)**, and `--error-format` *inherits `--format`* when omitted. My first Phase 0 pass missed this and passed only `--format json`, which (via the inherit rule) flipped errors to JSON too — that was the only reason errors looked JSON-ified. **The fix is one extra flag, not a fallback.** Phase 1.2 Stage 3 uses **one** invocation:
  ```bash
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --allow-signatures --format json --error-format markdown
  ```
  Empirically confirmed through `mthds-agent` (passthrough forwards both flags): **success** → clean JSON on **stdout** with `pending_signatures`, stderr empty; **failure** → **markdown** on **stderr** (`# Error:` … `- **error_domain:** input`), stdout empty. I ran the hook's exact classifier (`sed '/^## Error source/,$d'` then `sed -n 's/^- \*\*error_domain:\*\* *//p'`) against the failure stderr → extracted `error_domain: input`. So: success path parses `pending_signatures` from JSON stdout (via the hook's existing `node` `_jv` helper) and emits the non-blocking nudge; **failure path (hook lines 108–155) stays byte-for-byte unchanged**, so R1–R3 are protected for free, with **no** second validation per save. R3 (config/runtime-domain error stays markdown) is the one residual to confirm under the new flags in Phase 1 — expected to hold because `set_agent_cli_error_format(error_format or output_format)` runs at `bundle_cmd.py:92` *before* the factory init that raises config/runtime errors.

- **Version-floor finding — UNRELEASED, DEFERRED to Phase 6.4:** Part A+B (additive multi-file construction: reconciliation, library-level concept resolution, `pending_signatures`) sit in the pipelex worktree's CHANGELOG **`[Unreleased]`** section — not yet cut; the release will be `> 0.31.0` (worktree `pyproject.toml` still reads `0.31.0`). The matching mthds-agent is also not cut: mthds-agent `0.9.0` currently pins **`pipelex >=0.31.0`** at `mthds-js/src/agent/binaries.ts:41` (`PIPELEX_PKG.version_constraint`). **D4 watch-item — partial resolution:** a pipelex floor-enforcement lever *does* exist (that `version_constraint`, consumed by mthds-agent's update-check/recovery), contra the strongest "no PIPELEX_OUTDATED" worry — but `>=0.31.0` would still accept released 0.31.0 (no Part A+B). Floor-bump recipe at Phase 6.4: (a) cut the pipelex release carrying Part A+B; (b) bump `binaries.ts:41` `version_constraint` to `>=<that pipelex version>` **and** the mthds-js package version; (c) `/bump-mthds-version` to set the plugin `min_mthds_version` to that mthds-agent version. Still to confirm at 6.4: whether that constraint actually *blocks* (vs. only advising on install) via the plugin's Step 0 env-check (`preamble.md.j2` — design D4 says it emits only `MTHDS_AGENT_OUTDATED`); and the plxt `PipeSignature` schema floor (`plxt 0.4.0` installed; constraint is `>=0.4.0`).

- **Any surprise in the primitive's behavior vs design.md §4.5:** None material. Two minor observations: (1) the per-pipe `validated_pipes` list depends on the *target* file — validating the root reports 1 pipe (`make_brief`, the main_pipe), validating the child reports all 3 — but the library-wide `pending_signatures` and overall pass/fail are identical either way, which is what the hook relies on (it always passes the just-saved file as the target). (2) I tested reconciliation with byte-identical bare spellings on both sides; the §4.5 bare↔qualified/native equivalence wasn't stress-tested here (covered by pipelex's own tests + the CHANGELOG `[Unreleased]` entry) — not needed to clear this checkpoint.

---

## Phase 1 — Unblock signatures in the Claude hook (foundational, independent)

Design refs: §5.1, §5.2. This is independent of the skill rewrite and is the smallest shippable unit. Do it first.

- [x] **1.1 — Unblock.** Add `--allow-signatures` to the Stage 3 `validate bundle` call in `templates/hooks/validate-mthds.sh.j2` (line ~97). Rationale: on a signature-free bundle, lenient ≡ strict, so this is a no-op for vibe/build/hand-edits and unblocks recursive saves. The strict gate moves to the skill's explicit finalize step + `run`.
- [x] **1.2 — Leftover-signature nudge (success path).** Per **decision D3** (Phase 0 confirmed the single-invocation path): Stage 3 uses **one** invocation with both format streams pinned — `... -L "$PARENT_DIR/" --allow-signatures --format json --error-format markdown`. `--error-format markdown` keeps errors as markdown-on-stderr so the existing classifier (lines 108–155) is **byte-for-byte untouched** (no two-invocation fallback); `--format json` puts the success envelope as JSON on stdout. On lenient success (currently the hook `exit 0`s at line ~100 without reading stdout), parse the `pending_signatures` array from validate's JSON stdout via the hook's existing `node` `_jv` helper (do **not** `grep -q '"PipeSignature"'` — headers persist additively after they're satisfied, so a grep false-positives; do **not** scrape the markdown section). If non-empty, emit a **non-blocking** `hookSpecificOutput.additionalContext` note listing them ("signatures remain — implement before running").
- [x] **1.3 — Regenerate.** `make build`; confirm the change appears in both `mthds/hooks/validate-mthds.sh` and `mthds-dev/hooks/validate-mthds.sh` (the dev target feeds the Docker integration tests).

### ⛔ CHECKPOINT 1 — hook is lenient + safe (HARD STOP)

This is a clean, independently-shippable boundary. Verify thoroughly before moving on.

Verification:
- [x] `make build && make agent-test` (silent on success) — the unit suite. → green; also `make check` (freshness + ruff + pyright + marketplace) all pass.
- [x] **internal-tools integration suite** (the safety net for the hook/install system): `make build && make agent-test` per the integration-test rule; if Docker is off, ask the user to start it — do not skip. → **PASS (2026-06-08, Docker up).** Ran `make -C ../internal-tools build` (both images `internal-tools-fresh-install` + `internal-tools-upgrade-from-old` built, exit 0) then `make -C ../internal-tools agent-test`: **`# ALL integration test scripts passed`** for *both* the fresh-install and upgrade-from-old scenarios, exit 0. (Benign orphan-container warnings for `cac-carol-dev`/`cac-nelly` from unrelated harnesses — not this suite.) The suite installs the **dev**-target hook into the container, so this exact `--allow-signatures` change was exercised.
- [x] Manual: saving a signature-containing `.mthds` is **not** blocked; saving a signature-free bundle behaves **exactly** as before (same block/warn behavior). A bundle with leftover signatures surfaces the non-blocking nudge. → Done with the **real** toolchain (mthds-agent 0.9.0 → editable `_recursive` pipelex) against `/tmp/mthds-smoke/lib/` (signatures) and `/tmp/mthds-free/lib/` (signature-free). See record below.
- [x] **Regression tests (IRON RULE — mandatory, the Stage 3 invocation change can silently break the existing classifier):**
      - **R1** signature-free bundle under `--allow-signatures --format json` → byte-identical block/warn/pass vs today. → `test_signature_free_success_no_nudge` (+ real-CLI TEST C silent pass); existing success/block/warn tests still green under the new flags.
      - **R2** input-domain error under the new flags → STILL blocks with the trimmed markdown reason (the Phase 0 error-routing confirm, hardened into a test). → `test_input_domain_still_blocks_under_lenient_flags` (+ real-CLI: a wrong-field bundle blocked with `error_domain: input`).
      - **R3** config/runtime-domain error under the new flags → STILL emits `additionalContext`, does not block. → `test_config_domain_still_emits_additional_context_under_lenient_flags`.
- [x] **New-path tests:** N1 leftover signatures → nudge lists them; N2 complete bundle (empty `pending_signatures`) → **no** nudge (no false reminder); N3 child member file (domain-only) saved → hook validates the library cleanly (automated form of the D2 Phase 0 check). → `test_pending_signatures_emit_nudge` (N1), `test_empty_pending_signatures_no_nudge` (N2), `test_validate_invoked_with_allow_signatures_and_library_dir` + real-CLI TEST A on the domain-only child (N3/D2).

Record before continuing (filled 2026-06-07):

- **Final Stage 3 invocation line (verbatim):**
  ```bash
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --allow-signatures --format json --error-format markdown >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?
  ```
  (`templates/hooks/validate-mthds.sh.j2` line ~111; renders identically into both `mthds/hooks/validate-mthds.sh` and `mthds-dev/hooks/validate-mthds.sh` — the prod/dev difference is only the install-command strings, none of which live in Stage 3.) The failure-path classifier (the `sed`/`error_domain` block) is **byte-for-byte unchanged**.

- **How the success-path nudge reads `pending_signatures` (flag, parse path):** On `EXIT_CODE -eq 0`, before the `exit 0`, read the success envelope from JSON **stdout** (`$TMPOUT`) via the hook's existing `_jv` node helper:
  ```bash
  PENDING=$(_jv "$(cat "$TMPOUT")" "Array.isArray(d.pending_signatures)?d.pending_signatures.join(', '):''") || PENDING=""
  ```
  Empty array, missing key, or unparseable stdout all yield `PENDING=""` → no nudge (verified in isolation). If non-empty, a dedicated `node -e` emits a **non-blocking** `hookSpecificOutput.additionalContext` (no `decision`) listing the codes: *"Bundle is valid (lenient). Signatures still unimplemented (PipeSignature placeholders): &lt;list&gt;. They mock their output on dry-run; implement them before running the method for real."* `|| true` / `|| PENDING=""` guards keep `set -e` from turning a nudge-formatting hiccup into a non-zero hook exit. Uses the field directly — **not** a `grep -q '"PipeSignature"'` (headers persist additively after they're satisfied, so a grep false-positives).

- **Tests added** (`tests/integration/test_hook_validate_mthds.py`, in the existing `TestHookValidateMthds` class; new helper `_stub_mthds_agent_validate_success` returns a JSON-stdout success stub that also records its argv): `test_validate_invoked_with_allow_signatures_and_library_dir` (R1 invocation shape / N3 — asserts `--allow-signatures`, both format flags, and `-L <parent>/` are passed), `test_signature_free_success_no_nudge` (R1), `test_input_domain_still_blocks_under_lenient_flags` (R2), `test_config_domain_still_emits_additional_context_under_lenient_flags` (R3), `test_pending_signatures_emit_nudge` (N1), `test_empty_pending_signatures_no_nudge` (N2). **Full `make agent-test` green** (26 hook tests + the rest of the unit suite). `make check` green (freshness, ruff, pyright, marketplace).

- **Real-CLI manual results** (the stub suite can't exercise the actual CLI under the new flags — this does): mthds-agent 0.9.0 → editable `_recursive` pipelex (still version string `0.31.0`).
  - TEST A — saving the **domain-only child** `make_brief.mthds` (no `main_pipe`, the D2 case): exit 0, **non-blocking** nudge `"… smoke_test.polish_brief, smoke_test.write_draft …"`. Confirms the hook validating a child save works end-to-end and the nudge reads `pending_signatures` from the real JSON envelope.
  - TEST B — saving the **root** `bundle.mthds`: exit 0, same nudge. Both A and B emit `hookSpecificOutput.additionalContext`, neither emits `decision:block`.
  - TEST C — a **signature-free** valid `PipeLLM` bundle: exit 0, **zero** stdout bytes → silent, exactly as before `--allow-signatures`.
  - Incidental R2 (real CLI): a bundle with a wrong field (`prompt_template`) returned `{"decision":"block", reason: "# Error: ValidateBundleError … - **error_domain:** input …"}` under the new flags → confirms errors still arrive as **markdown on stderr** and the classifier still blocks (decision D3 / Phase-0 R3 residual now confirmed empirically through the rendered hook).

- **Integration-test result (pass/fail + any flake notes):** plugin's own pytest integration suite (`tests/integration/test_hook_validate_mthds.py`, bash-stub based, no Docker) — **all pass, no flakes**. **internal-tools Docker suite (2026-06-08): PASS** — `make -C ../internal-tools build` (both images built, exit 0) then `make -C ../internal-tools agent-test` → `# ALL integration test scripts passed` for both fresh-install and upgrade-from-old, exit 0. No flakes; only benign orphan-container warnings (`cac-carol-dev`/`cac-nelly`, unrelated harnesses). All CHECKPOINT 1 gates green.

- **Anything about hook timeout / per-file whole-library validation cost worth knowing:** The hook validates the **whole assembled library** (`-L "$PARENT_DIR/"`) on every per-file save, so cost scales with library size, not the edited file — inherent to the multi-file model and unchanged by this phase (`--allow-signatures` adds only a cheap signature pre-pass). On the small smoke library each real `mthds-agent validate` ran sub-second; no timeout concern observed. The pytest integration harness caps each hook run at 30 s (`timeout=30` in `_run_hook`) and the full file ran in ~16 s across all 26 stub tests. Watch this at Phase 6 dogfood on a genuinely large multi-layer library, where per-save whole-library validation latency could become noticeable.

---

## Phase 2 — Document the primitive (references)

Design refs: §4.3, §5.4. Low-risk; can be done anytime after Phase 0, but before Phase 4 so the skill can point at it.

- [ ] **2.1** Add a `PipeSignature` section to `skills/mthds-vibe/references/vibe-cheat-sheet.md`: the signature syntax (design.md §1 reference block), the `signature_for` hint + its rules (not `"PipeSignature"`; it's a hint, not binding; multiplicity allowed), the operator-vs-controller decision, and the lenient (`--allow-signatures`) vs strict validate commands. The cheat sheet stays the syntax/field source of truth; the recursive loop itself lives in the SKILL body.
- [ ] **2.2** Add `--allow-signatures` + `pending_signatures` to `templates/skills/shared/mthds-agent-guide.md.j2` (near the existing `validate bundle` / `--graph` docs, ~line 209/236/264): document the flag (forwarded verbatim to pipelex via `.allowUnknownOption()`), what lenient vs strict means, and that successful validate emits `pending_signatures`.
- [ ] **2.3** `make build && make check` to confirm references render and freshness/stale-reference checks stay green.

(No hard checkpoint — verification folded into Checkpoint 3.)

---

## Phase 3 — `expand-signature` worker agent + build-system `agents/` support (Claude-only) — ⛔ DEFERRED TO FOLLOW-UP

> **Deferred per eng-review decision D1 (2026-06-07).** Fan-out is out of v1; the layer loop runs inline/serial on both targets. Everything in this phase — the worker agent, the `expand-signature` shared partial, and the build-system `agents/` support — moves to a follow-up PR. Rationale + the open auto-discovery question are recorded in [wip/deferred-issues.md](wip/deferred-issues.md). **Skip this phase for v1.** The sub-tasks below are kept verbatim as the follow-up's starting point.

Design refs: §4.4, §7.3. **This adds a brand-new plugin component class (`agents/`) that the build system does not handle today.** Two coupled pieces: author the worker, and teach the renderer to ship it (Claude targets only — Codex plugin manifests expose no `agents` field).

- [ ] **3.1 — Single source of truth for the expand-signature job.** Author the uniform "given one signature `S`, produce its implementation one level down (operator = done; controller = forward-declare child headers + own new concepts)" instructions **once**. Recommended: put the body in a shared partial (e.g. `templates/skills/shared/expand-signature.md.j2`) so it can be `{% include %}`d by *both* the worker agent template and the orchestrator SKILL's inline path. Must encode: contract preserved (declare `inputs`/`output` **explicitly** — pipes don't infer from sigils; spelling free, matched by concept identity), **adds exactly one `<code>.mthds` file**, never edits an existing file, no merge step, derive child/concept codes from its own pipe code to avoid sibling clashes.
- [ ] **3.2 — Worker agent template.** Create `templates/agents/mthds-signature-expander.md.j2` whose system prompt **is** the expand-signature job (include the shared partial). Frontmatter: `name`, `description`, restricted tools (Read + Write + the Bash validate command only), model as appropriate. Verify the exact agent-frontmatter schema Claude Code expects for plugin `agents/*.md` (name/description/tools/model) before finalizing.
- [ ] **3.3 — Renderer support** in `scripts/gen_skill_docs.py`: add agent templates (e.g. an `AGENT_TEMPLATES` list + a per-platform gate mirroring `HOOK_TEMPLATES_BY_PLATFORM`) so `templates/agents/*.md.j2` render into **Claude** target outputs (`mthds/agents/`, `mthds-dev/agents/`) and **never** the Codex target. Ensure rendered agent files land in `result.files` so the existing freshness check (`--check`) covers them automatically. Add orphan/leak scanning for `agents/` if needed (mirror the skills/hooks scans).
- [ ] **3.4 — Packaging guard** in `scripts/check.py`: extend `check_codex_no_claude_artifacts` (or add a sibling check) to fail if an `agents/` dir leaks into a Codex output dir.
- [ ] **3.5 — Auto-discovery confirmation.** Confirm Claude Code auto-discovers `agents/` at the plugin root (no `plugin.json` field needed). If a manifest field *is* required, add it to `.claude-plugin/plugin-base.json` (and ensure `make_plugin_json` carries it). Document the finding.
- [ ] **3.6** `make build && make check`; confirm `mthds/agents/mthds-signature-expander.md` and `mthds-dev/agents/...` exist and render correctly, and the Codex output (`mthds-codex/`) has **no** `agents/`.

### ⛔ CHECKPOINT 3 — new build surface landed (HARD STOP)

The build system now emits a component class it didn't before — this is context-heavy and worth a clean handoff.

Verification:
- [ ] `make build && make check` green (all scopes: shared, claude, codex).
- [ ] Agent renders for Claude targets, absent from Codex target.
- [ ] (Optional but recommended) Spawn the worker agent once by hand via the Agent tool on a single signature to sanity-check the system prompt produces a valid single-file definition.

Record before continuing:
- Where the expand-signature single-source lives (partial path) + who includes it: _______
- Agent frontmatter schema actually used (tools list, model): _______
- How the renderer gates agents to Claude (function/const names touched): _______
- Auto-discovery answer (manifest field needed? y/n): _______
- Update `docs/build-targets.md` to describe the new `agents/` component (done? path): _______

---

## Phase 4 — Rewrite the orchestrator skill (`mthds-vibe`)

Design refs: §4.1, §4.2, §4.4, §6 (Decisions). The biggest change. Replace the single-pass body of `templates/skills/mthds-vibe/SKILL.md.j2` with the recursive flow.

- [ ] **4.1 — Step structure (Step 0–4).**
      - Step 0: unchanged env-check (`{% include 'skills/shared/preamble.md.j2' %}`).
      - Step 1: capture the top requirement as one `PipeSignature`; write the **root** `bundle.mthds` (domain header, `main_pipe`, fully-specified **boundary** concepts, top signature header); validate leniently; **announce** the captured contract in one line (non-blocking). *Only* step with optional interactivity.
      - Step 2: drain the `pending_signatures` backlog breadth-first, **serially** — expand each pending signature inline, one at a time (no fan-out in v1, D1). Each expansion **adds a new `<code>.mthds` file**; validate the assembled library leniently (`-L <dir> --allow-signatures --format json`); recompute backlog from `pending_signatures` and repeat. **Prevent** intermediate-concept collisions up front (D5 — check before introducing); `ConceptLibraryError` is the backstop. On a contract mismatch, conform the **definition** to the frozen header (never edit the header — design §2.6).
      - Step 3: finalize — strict validate (`--graph`); fix whole-bundle semantic errors; passing = runnable.
      - Step 4: deliver (same as vibe today — show input schema, never write `inputs.json`, point at `dry_run.html`, suggest dry-run + `/mthds-inputs`). Early-stop variant: deliver the leniently-valid scaffold and list unimplemented signatures.
- [ ] **4.2 — No fan-out in v1 (decision D1).** The layer loop runs **inline/serial on BOTH targets** — when a layer has multiple pending signatures, expand them one at a time in the orchestrator's own context. Do **not** add the `mthds-signature-expander` worker, the Agent-tool fan-out, or the `{% if platform != "codex" %}` fan-out block for v1 (that returns with the deferred Phase 3). Expansion instructions live **inline** in Step 2 — no `expand-signature` shared partial (single consumer). Keep the loop expressed so re-adding Claude fan-out later is a localized template change.
- [ ] **4.2b — Concept-collision prevention (decision D5).** In Step 2, before introducing a new intermediate concept, **check it isn't already declared in the assembled library / pending set** and derive a unique code (namespace by the parent pipe code). Serial execution makes this nearly free; `ConceptLibraryError` stays the loud backstop. (Parallel-sibling collision handling returns with fan-out — see [wip/deferred-issues.md](wip/deferred-issues.md).)
- [ ] **4.3 — Frontmatter + identity.** Keep the `mthds-vibe` name/slot. Update the `description` to reflect top-down, valid-at-every-step refinement. **Preserve `disable-model-invocation: true` for non-Codex** (the `{% if platform != "codex" %}` block already in the template) — this stays explicit-invocation-only.
- [ ] **4.4 — Lazy-concepts + invariants prose.** Encode the core rules in the body: contract stability (concept identity, not byte-string), `main_pipe` frozen after Layer 0, concepts refine lazily (structure only when a consumer reads a field), additive writes (one concrete per file, headers persist), backlog = `{signatures} − {concretes}` via `pending_signatures`.
- [ ] **4.5** `make build` (prod + dev + codex) + `/reload-plugins`. Both renders are **inline-serial** (no fan-out in v1, D1). Inspect the rendered `mthds/skills/mthds-vibe/SKILL.md` (has `disable-model-invocation: true`) and `mthds-codex/skills/mthds-vibe/SKILL.md` (no `disable-model-invocation`, no `allowed-tools` — the `check_codex_no_claude_artifacts` guard). The only per-target difference is the frontmatter, not the loop.

### ⛔ CHECKPOINT 4 — skill rewritten and renders per target (HARD STOP)

Verification:
- [ ] `make build && make check` green.
- [ ] Claude render has the fan-out + `disable-model-invocation: true`; Codex render is inline-serial + has neither `disable-model-invocation` nor `allowed-tools` (the `check_codex_no_claude_artifacts` guard).
- [ ] A quick read-through of both renders for coherence (no dangling single-pass leftovers, no broken includes).

Record before continuing:
- Summary of the new Step 0–4 body + any deviations from design §4.1: _______
- Confirmed per-target render differences (fan-out, frontmatter): _______
- Decisions made while writing the prose that aren't in design.md: _______
- Update `docs/` (and the design doc's status) to reflect the shipped skill: _______

---

## Phase 5 — Codex hook parity (cross-repo: `mthds-js`)

Design refs: §5.3. The Codex hook runs the analogous `pipelex-agent validate bundle` at Stage 3 — it needs the same `--allow-signatures`. The nudge is optional for v1. Codex **orchestration** fan-out is explicitly out of scope (the skill runs inline under Codex).

- [ ] **5.1** In `mthds-js/src/agent/commands/codex-hook.ts`, add `--allow-signatures` to `runPipelexValidate()` (the args array at ~line 285): `["validate","bundle",file,"-L",libraryDir,"--allow-signatures"]`.
- [ ] **5.2 (optional — recommend SKIP for v1)** Mirror the leftover-signature nudge. Note: the Codex hook currently parses **markdown stderr** and only inspects output on failure; adding a `pending_signatures` success-path note means switching to `--format json`, which re-opens the same error-format coupling on the Codex side (`classifyStage3Result()`). For v1, ship **only 5.1** (`--allow-signatures`, no `--format json`, no nudge) to sidestep that risk entirely — the orchestrator skill already tracks `pending_signatures` itself. Log the Codex nudge as a follow-up.
- [ ] **5.3** Update `mthds-js/tests/unit/agent/codex-hook.test.ts` (mocks are dependency-injected — the `runPipelexValidate` mock returns `{exitCode, stderr}`; extend if 5.2 is done).
- [ ] **5.4** Build/lint mthds-js per its own repo conventions; ensure the installed `mthds-agent` reflects the change. (Dev-target Docker tests install mthds-js from the mount, so Phase 6 integration exercises this.)

### ⛔ CHECKPOINT 5 — Codex hook at parity

Verification:
- [ ] mthds-js unit tests pass.
- [ ] A signature-containing bundle edited under the Codex `apply_patch` matcher is not blocked by Stage 3.

Record before continuing:
- mthds-js version after the change + its pipelex pin: _______
- Whether 5.2 (nudge) was done or deferred: _______
- Any version-coordination note between mthds-js and the plugin's `min_mthds_version`: _______

---

## Phase 6 — End-to-end validation, dogfood, version floor, ship

Design refs: §7.6, §6 (Version floor). Brings it all together and gates the prod release on the pipelex dependency.

- [ ] **6.1** `make build && make check` (all scopes green).
- [ ] **6.2** internal-tools integration tests (Docker): `make build && make agent-test`. Don't skip — if Docker is off, ask the user to start it.
- [ ] **6.3 — Dogfood the recursive flow** on a real multi-layer method (the design §3 `research_brief` example is the canonical one): exercise **both** a single-pending (inline) layer **and** a multi-pending **serial** layer — i.e. a layer where several signatures are drained one at a time in the orchestrator's own context (fan-out is deferred, D1; do not expect parallel workers). Also exercise: lazy concept structuring, contract-mismatch recovery (conform the definition to the header), concept-collision **prevention** (D5 — build a method that reuses an intermediate concept name across controllers and confirm no `ConceptLibraryError`), and the **early-stop** scaffold deliverable. Confirm lenient-per-layer → strict-at-end behaves as designed, every intermediate save passes the now-lenient hook, `dry_run.html` updates each layer, and the final strict gate yields a runnable method. Capture any rough edges.
- [ ] **6.4 — Version floor bump (gated on the pipelex release).** Once the pipelex release carrying Part A+B is out and the matching `mthds-agent` version is known: bump `min_mthds_version` (`targets/defaults.toml`) to that mthds-agent version via the `/bump-mthds-version` skill, `make build && make check`. **If still unreleased, leave this unchecked with a dated blocker note** — the plugin can ship the hook/doc/skill changes against the current floor only if the additive flow degrades gracefully; otherwise the whole feature waits here.
- [ ] **6.5 — Docs.** Update this repo's `docs/` (`build-targets.md` for the `agents/` component, `codex-vs-claude-hooks.md` for the `--allow-signatures` parity + nudge), refresh `wip/deferred-issues.md` if any deferred item moved, and mark design.md §7 items done. Docs are part of the deliverable, not an afterthought.
- [ ] **6.6 — Ship.** Use the `/release` skill (runs `make check`, bumps version in target config + plugin files, finalizes `CHANGELOG.md`, opens the PR). Marketplace version bump per the release playbook.

### ⛔ CHECKPOINT 6 — feature complete, ready to ship (FINAL HARD STOP)

Done means: recursive `mthds-vibe` produces a runnable method through layered refinement (inline + fan-out), every intermediate save passes the lenient hook, the final strict gate holds, Codex runs the loop inline, and `make check` + integration tests are green.

Record before shipping:
- Dogfood result (method built, layers exercised, any rough edges filed): _______
- Version-floor resolution (mthds-agent version set, or still blocked on pipelex release): _______
- Release PR link + CHANGELOG entry: _______
- **Revert local pipelex** to the published release when done iterating: `uv tool install --force pipelex`.

---

## Decisions log (carry forward; seed from design.md §6)

- Skill identity: evolve `mthds-vibe` in place; `mthds-build` stays separate. Keep the name; update only the description.
- Invocation: stays explicit-invocation-only (`disable-model-invocation: true`, non-Codex).
- Delivery: multi-file same-domain library, additive (one concrete per file; headers reconcile at merge). Optional flatten-to-one-file deferred.
- Scope limits (`dict`, `PipeStructure`, inline `templating_style`) unchanged — tracked in revisit-vibe-scope-limits.md.

### Eng-review decisions (2026-06-07 — `/plan-eng-review`, recorded in design.md "GSTACK REVIEW REPORT")

- **D1 — Fan-out DEFERRED to a follow-up.** v1 runs the layer loop **inline/serial on BOTH targets** (was: Claude fan-out via `agents/` + Codex inline). The whole of the original **Phase 3 is deferred** — worker agent, the `expand-signature` shared partial, and the `agents/` build-system support — tracked in [wip/deferred-issues.md](wip/deferred-issues.md). Correctness identical; only parallelism + per-signature context isolation dropped. Expansion instructions live **inline** in the skill (no shared partial in v1).
- **D2 — Member-file validation contract.** A domain-only member file (no `main_pipe`) must validate with `-L`. Phase 0 confirms; any failure is a **pipelex bug** fixed in `../_recursive`, not a hook workaround.
- **D3 — Hook nudge via one invocation.** Stage 3 uses `--allow-signatures --format json`; Phase 0 must **empirically confirm** errors still arrive as markdown-on-stderr (else fall back to two invocations).
- **D4 — One release gate.** Hold the whole feature behind the pipelex Part A+B release; bump `min_mthds_version`; trust the floor. ⚠ **watch-item:** verify at floor-bump time that the mthds-agent floor actually blocks old pipelex (mthds-agent ↔ pipelex are PATH-decoupled; the env-check has no `PIPELEX_OUTDATED` status) — else old-pipelex users hit a loud-but-opaque `PipeLibraryError` at Layer 1. The plxt `PipeSignature` schema floor (~v0.9.0) is a second floor to confirm.
- **D5 — Concept-collision prevention (serial).** The skill's Step 2 **checks existing/pending concept codes before introducing** a new intermediate concept (derive a unique code); `ConceptLibraryError` stays the backstop. Parallel-sibling collision handling re-introduced when fan-out lands.
- **D7 — Eval harness deferred** to a separate design doc, [wip/recursive/eval-harness.md](wip/recursive/eval-harness.md); v1 ships dogfood-only.
- _(add new decisions here as they're made)_

## Open questions (resolve as you hit them)

- **Validate invocation for `pending_signatures`** — RESOLVED in Phase 0 (2026-06-07): **single invocation holds** — `--allow-signatures --format json --error-format markdown`. The `pipelex-agent` CLI has independent `--format` (stdout/success) and `--error-format` (stderr/errors) controls by design; pinning `--error-format markdown` gives JSON success output *and* markdown errors, so the hook's existing markdown classifier is untouched. (My first pass missed `--error-format`, which inherits `--format` when omitted — that was the whole "JSON-ifies errors" confusion. No two-invocation fallback needed.) See the CHECKPOINT 0 D3 block.
- **Member-file validation** — RESOLVED in Phase 0 (2026-06-07): a domain-only child (`make_brief.mthds`, no `main_pipe`) validates with `-L` (exit 0, library-wide `pending_signatures`, no missing-root-header error). No pipelex bug to file.
- **Version floor** — OPEN (unreleased): Part A+B sit in the pipelex worktree CHANGELOG `[Unreleased]` (release will be `> 0.31.0`, not yet cut). The matching mthds-agent isn't cut either — mthds-agent `0.9.0` pins `pipelex >=0.31.0` at `mthds-js/src/agent/binaries.ts:41`. (Phase 0 recon → Phase 6.4 bump.) **⚠ D4 watch-item — partially resolved:** the floor lever *does* exist (`binaries.ts:41 version_constraint`, consumed by mthds-agent update-check/recovery), but `>=0.31.0` still accepts released 0.31.0 (no Part A+B). At floor-bump time: bump that constraint to `>=<Part A+B release>` + the mthds-js version, then `/bump-mthds-version`. Still to confirm at 6.4: whether the constraint actually *blocks* via the Step 0 env-check (`preamble.md.j2` may emit only `MTHDS_AGENT_OUTDATED`); and the plxt `PipeSignature` schema floor (plxt `0.4.0` installed; constraint `>=0.4.0`).
- **Agent auto-discovery** — does Claude need a `plugin.json`/manifest field for `agents/`, or is the directory auto-discovered? **DEFERRED with fan-out / Phase 3** (D1) — answer it when the follow-up lands.
- _(add as discovered)_

## Files touched (running map — fill as you edit)

- `templates/hooks/validate-mthds.sh.j2` — ✅ Phase 1: Stage 3 now `--allow-signatures --format json --error-format markdown`; added success-path `pending_signatures` nudge (non-blocking `additionalContext`). Header comments updated. Regenerated into `mthds/hooks/validate-mthds.sh` + `mthds-dev/hooks/validate-mthds.sh`.
- `tests/integration/test_hook_validate_mthds.py` — ✅ Phase 1: added `_stub_mthds_agent_validate_success` helper + 6 tests (R1/R2/R3 regression, N1/N2/N3 new-path).
- `templates/skills/mthds-vibe/SKILL.md.j2` — _______
- `skills/mthds-vibe/references/vibe-cheat-sheet.md` — _______
- `templates/skills/shared/mthds-agent-guide.md.j2` — _______
- `templates/skills/shared/expand-signature.md.j2` (new) — ⛔ DEFERRED (Phase 3 follow-up, D1); v1 keeps expansion instructions inline in the skill
- `templates/agents/mthds-signature-expander.md.j2` (new) — ⛔ DEFERRED (Phase 3 follow-up, D1)
- `scripts/gen_skill_docs.py` — ⛔ DEFERRED (Phase 3 `AGENT_TEMPLATES` support, D1); no change in v1
- `scripts/check.py` — ⛔ DEFERRED (Phase 3 no-`agents/`-in-Codex guard, D1); no change in v1
- `targets/defaults.toml` (min_mthds_version) — _______
- `docs/build-targets.md`, `docs/codex-vs-claude-hooks.md` — _______
- `wip/recursive/eval-harness.md` (new) — created: deferred eval-harness design doc (D7)
- mthds-js: `src/agent/commands/codex-hook.ts`, `tests/unit/agent/codex-hook.test.ts` — v1: add `--allow-signatures` only (skip the nudge, 5.2)
