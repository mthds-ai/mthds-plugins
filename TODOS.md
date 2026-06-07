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

- [ ] Repoint the local `pipelex` runtime at the worktree so the additive (Part A+B) flow is live locally:
      `uv tool install --force --editable /Users/lchoquel/repos/Pipelex/_recursive`
      Then verify: `pipelex --version`, and `grep editable ~/.local/share/uv/tools/pipelex/uv-receipt.toml` (confirms source is the worktree). This also repoints `pipelex-agent` / `pipelex-dev`, which is what the hooks invoke. (Revert later with `uv tool install --force pipelex`.) See the "Iterating on a local pipelex runtime" section of the workspace `CLAUDE.md`.
- [ ] Smoke-test the primitive end-to-end by hand (no plugin yet): write a tiny two-file library in a scratch dir — a root `bundle.mthds` with one `PipeSignature` main pipe, plus a sibling concrete definition file of the same code referencing a sibling-declared concept — and confirm:
      - `mthds-agent validate bundle <root> -L <dir>/ --allow-signatures` passes (lenient).
      - Dropping `--allow-signatures` **fails** with a signatures-not-allowed error (strict).
      - The signature/concrete reconciliation works **across files** (Part A) and the cross-file bare concept ref resolves (Part B).
      - **(D2 — member-file validation)** `mthds-agent validate bundle <child> -L <dir>/ --allow-signatures` — pointing at a **domain-only child member** file (no `main_pipe`) — validates the **library**, not erroring on the missing root header. The hook fires `validate bundle <the-file-just-written> -L <dir>` on EVERY save, so most saves target a child, not the root. If this errors, it is a **pipelex bug** to fix in `../_recursive` (the generic hook stays simple). Record the result.
- [ ] Confirm how `pending_signatures` is exposed on a **successful** validate: run `mthds-agent validate bundle <root> -L <dir>/ --allow-signatures` and inspect stdout. Determine the exact invocation needed to read it as JSON (default stdout format vs an explicit `--format json`). **This answer drives Phase 1.2 and Phase 5.2** — record it in Open Questions.
- [ ] **(D3 — error-routing confirm)** With `--allow-signatures --format json` added, run a **failing** validate and confirm the **error report still goes to stderr as markdown** (so the hook's `error_domain` grep still works) while the **success output is JSON on stdout** (so `pending_signatures` is readable). Static reads of the pipelex source conflicted on this, so it MUST be checked by running it. If `--format json` JSON-ifies errors too, fall back to **two invocations** (one markdown for classify/block, one JSON for the nudge) — at the cost of validating the library twice per save. **This decides the Phase 1.2 implementation.**
- [ ] Version-floor recon: identify which **pipelex release** will carry Part A+B (`> 0.31.0`) and which **mthds-agent** version ships/requires it. `min_mthds_version` tracks the *mthds-agent* version (currently `0.9.0`), not pipelex. If unknown/unreleased, leave a dated note and defer the actual bump to Phase 6. (Check `mthds-js` package version + its pipelex pin, and the pipelex changelog/release plan.)

### ⛔ CHECKPOINT 0 — runtime ready

Verification: the by-hand two-file smoke test passes lenient and fails strict, with cross-file reconciliation working.

Record before continuing:
- pipelex version now resolving locally + confirmation it is the editable worktree: _______
- Exact validate invocation + where `pending_signatures` appears on success (stdout JSON? which flag?): _______
- Version-floor finding (pipelex release + mthds-agent version, or "unreleased, deferred"): _______
- Any surprise in the primitive's behavior vs design.md §4.5: _______

---

## Phase 1 — Unblock signatures in the Claude hook (foundational, independent)

Design refs: §5.1, §5.2. This is independent of the skill rewrite and is the smallest shippable unit. Do it first.

- [ ] **1.1 — Unblock.** Add `--allow-signatures` to the Stage 3 `validate bundle` call in `templates/hooks/validate-mthds.sh.j2` (line ~97). Rationale: on a signature-free bundle, lenient ≡ strict, so this is a no-op for vibe/build/hand-edits and unblocks recursive saves. The strict gate moves to the skill's explicit finalize step + `run`.
- [ ] **1.2 — Leftover-signature nudge (success path).** Per **decision D3**: Stage 3 uses a **single** invocation `... -L <dir> --allow-signatures --format json` (gated on the Phase 0 error-routing confirm; two invocations only as fallback). On lenient success (currently the hook `exit 0`s without reading stdout), read the `pending_signatures` array from validate's JSON stdout (do **not** `grep -q '"PipeSignature"'` — headers persist additively after they're satisfied, so a grep false-positives). If non-empty, emit a **non-blocking** `hookSpecificOutput.additionalContext` note listing them ("signatures remain — implement before running"). This is a new success-path branch — parse the JSON envelope, not the markdown "Pending signatures" section.
- [ ] **1.3 — Regenerate.** `make build`; confirm the change appears in both `mthds/hooks/validate-mthds.sh` and `mthds-dev/hooks/validate-mthds.sh` (the dev target feeds the Docker integration tests).

### ⛔ CHECKPOINT 1 — hook is lenient + safe (HARD STOP)

This is a clean, independently-shippable boundary. Verify thoroughly before moving on.

Verification:
- [ ] `make build && make agent-test` (silent on success) — the unit suite.
- [ ] **internal-tools integration suite** (the safety net for the hook/install system): `make build && make agent-test` per the integration-test rule; if Docker is off, ask the user to start it — do not skip.
- [ ] Manual: saving a signature-containing `.mthds` is **not** blocked; saving a signature-free bundle behaves **exactly** as before (same block/warn behavior). A bundle with leftover signatures surfaces the non-blocking nudge.
- [ ] **Regression tests (IRON RULE — mandatory, the Stage 3 invocation change can silently break the existing classifier):**
      - **R1** signature-free bundle under `--allow-signatures --format json` → byte-identical block/warn/pass vs today.
      - **R2** input-domain error under the new flags → STILL blocks with the trimmed markdown reason (the Phase 0 error-routing confirm, hardened into a test).
      - **R3** config/runtime-domain error under the new flags → STILL emits `additionalContext`, does not block.
- [ ] **New-path tests:** N1 leftover signatures → nudge lists them; N2 complete bundle (empty `pending_signatures`) → **no** nudge (no false reminder); N3 child member file (domain-only) saved → hook validates the library cleanly (automated form of the D2 Phase 0 check).

Record before continuing:
- Final Stage 3 invocation line (verbatim): _______
- How the success-path nudge reads `pending_signatures` (flag, parse path): _______
- Integration-test result (pass/fail + any flake notes): _______
- Anything about hook timeout / per-file whole-library validation cost worth knowing: _______

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

- **Validate invocation for `pending_signatures`** — DECIDED (D3): one invocation `--allow-signatures --format json`. Still needs the Phase 0 **error-routing confirm** (errors stay markdown-on-stderr) before it's locked; two-invocation fallback if not.
- **Member-file validation** — DECIDED (D2): a domain-only child must validate with `-L`. Phase 0 confirms; failure = pipelex bug in `../_recursive`.
- **Version floor** — OPEN: which pipelex release carries Part A+B (`> 0.31.0`), and which `mthds-agent` version ships/requires it? (Phase 0 recon → Phase 6.4 bump.) **⚠ D4 watch-item:** does bumping `min_mthds_version` actually protect users from old pipelex? mthds-agent ↔ pipelex are PATH-decoupled and the env-check has no `PIPELEX_OUTDATED` status, so the mthds-agent floor may NOT enforce a pipelex floor. Confirm at floor-bump time; also confirm the plxt `PipeSignature` schema floor (~v0.9.0).
- **Agent auto-discovery** — does Claude need a `plugin.json`/manifest field for `agents/`, or is the directory auto-discovered? **DEFERRED with fan-out / Phase 3** (D1) — answer it when the follow-up lands.
- _(add as discovered)_

## Files touched (running map — fill as you edit)

- `templates/hooks/validate-mthds.sh.j2` — _______
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
