# Changelog

## [v0.14.1] - 2026-06-22

### Changed

- **Bump `min_mthds_version` from 0.12.0 to 0.12.1.** `mthds-agent` 0.12.1 floors pipelex at `>=0.35.1`, which fixes the `PipeImgGen` prompt model that this release's skill/doc cleanup reflects. Pinning the floor here keeps the skills' corrected `PipeImgGen` guidance in lockstep with a pipelex that actually implements it — a consumer on an older `mthds-agent` / pipelex would otherwise be taught the new input model while running a runtime that still expects the old one. Consumers on an older `mthds-agent` fail the env-check with a clean upgrade prompt.

### Documentation

- **Dropped the `ImgGenPrompt` native concept from the skills and taught the correct `PipeImgGen` input model.** `PipeImgGen` takes a plain text prompt as its input, not a dedicated `ImgGenPrompt` native concept; the skills and `mthds-agent-guide` now describe the actual input model.
- **Updated aspect-ratio documentation for `PipeImgGen`** and related references.
- **Removed the dead `img_gen_input_not_text_compatible` error-hint row** and the dead img-gen enum (PR #32).

## [v0.14.0] - 2026-06-19

### Changed

- **Bump `min_mthds_version` from 0.10.0 to 0.12.0.** The v0.14.0 Stage 3 hook pins `mthds-agent validate bundle … --allow-signatures --format json --error-format json`, and `--error-format` is an `mthds-agent` 0.12.0 surface (`--allow-signatures` is 0.11.0). Flooring at 0.12.0 keeps this release's reciprocal floor in lockstep with mthds-js 0.12.0, which reciprocally enforces plugin `>=0.14.0` (`MIN_PLUGIN_VERSION`) — so a partial upgrade in either direction is caught by the env-check with a clean upgrade prompt instead of a hook that silently loses leniency or blocks on an unknown option.
- **Claude PostToolUse validate hook now reads the structured JSON verdict instead of parsing markdown.** `validate-mthds.sh` Stage 3 previously consumed pipelex's markdown error envelope textually; it now pins `mthds-agent validate bundle … --allow-signatures --format json --error-format json` (both streams JSON) and classifies from machine-readable fields: `is_valid` / `pending_signatures` from the success envelope on stdout, and `error_domain` / `message` / `validation_errors` from the error envelope on stderr. The decision model is unchanged — BLOCK on input-domain (or missing/unknown, default-to-block) errors with the validation report as the agent-actionable reason, emit `hookSpecificOutput.additionalContext` on config/runtime-domain errors so the agent is informed without editing the file — but the verdict is now read structurally rather than scraped from prose, removing the markdown-format coupling that had repeatedly broken Stage 3 when pipelex changed its envelope wording.

### Added

- **`--allow-signatures` lenient validation: in-progress bundles that still reach `PipeSignature` headers validate without failing.** Both the Claude hook and the Codex hook now pass `--allow-signatures`, so a bundle whose graph still terminates at a `PipeSignature` (a not-yet-implemented sub-method) rides the success envelope — carrying `pending_signatures` — instead of being blocked as broken. When a saved bundle is valid-but-not-yet-runnable, the Claude hook surfaces a **non-blocking** `pending_signatures` nudge (the named signatures still need implementations) rather than a block. This unblocks recursive/top-down authoring, where higher-level methods are written and validated before their leaf sub-methods exist.
- **`check-min-versions` skill.** A read-only report of the versions currently configured in the plugin repo — the canonical `min_mthds_version` plus any per-target overrides and the plugin/marketplace versions. Never edits files; complements the existing `bump-mthds-version` skill.

### Fixed

- **Validate hook now blocks on exit 0 without a structured success envelope.** A `mthds-agent validate` call that exited 0 but emitted no parseable success envelope (e.g. a wrapper that printed nothing) previously slipped through Stage 3 as a pass. The hook now treats a missing/unparseable success envelope on a zero exit as a block, closing a silent-pass path (greptile P1). Also addresses the PR #30 review findings from greptile/cubic.

### Documentation

- **mthds-vibe skill and `mthds-agent-guide` updated for the PipeSignature / pending-signatures flow,** with the `vibe-cheat-sheet.md` reference extended to cover signature-terminated drafts.
- **New `docs/mthds-agent-output-audit.md`** — a full audit of every `mthds-agent` call across the plugin (both hooks + all skills): its consumer (software vs LLM), how it uses stdout/stderr, and whether each `--format` / `--error-format` choice is correct. `docs/codex-vs-claude-hooks.md` updated to match the structured-JSON Stage 3.

## [v0.13.0] - 2026-06-12

### Added

- **`mthds-sandbox` build-only plugin target.** A fourth build target alongside prod, dev, and codex, listed in the marketplace as `mthds-sandbox`. It ships the build-assistant skill subset only (`mthds-build`, `mthds-edit`, `mthds-check`, `mthds-fix`, `mthds-explain`, `mthds-inputs`, `mthds-vibe`) for pre-provisioned, locked-down environments: `env_check = false` (the agent never runs env/doctor/upgrade commands) and `can_run_methods = false` (execution is the platform's job, never the agent's). Omits the run / runner-setup / install / upgrade / publish / share / pkg skills — and with them the only `AskUserQuestion` and `doctor` usages.
- **Per-target SKILL overlay system and a sandbox workspace check** in the build pipeline, letting a target adjust individual skill instructions without forking the shared templates.

### Changed

- **Sandbox skills no longer auto-emit a method summary** on build or validate, and the no-summary rule was extended to `mthds-edit` and `mthds-fix` — the locked-down build assistant edits `.mthds` files without narrating method internals.
- **Env-check artifacts are dropped from `env_check = false` targets,** so the sandbox build omits the env-check binary and preamble it would never run.
- **`mthds-install` drops its Step 5,** and the skill now offers to register MTHDS in user memory after install.
- **Skill `mthds-agent-guide` synced with the current agent-CLI flags** (`--base-url`, `models --type`).
- **Bump `min_mthds_version` to 0.10.0.**

## [v0.12.0] - 2026-05-26

### Changed

- **Env-check preamble rule split: `UP_TO_DATE` and "no output" are now distinct outcomes.** The previous rule read "No output or `UP_TO_DATE` → Proceed to Step 1", which silently swallowed a broken `mthds-agent` (where the wrapper would print nothing) as if it were a clean run. Paired with mthds-js 0.9.0's new explicit `UP_TO_DATE mthds-agent=X plxt=X plugin=X` line, the preamble now treats `UP_TO_DATE ...` as the only success signal and "no output" as a WARN — the env-check could not be confirmed, proceed cautiously. Two "explicit-quiet" variants of the same prefix are also accepted as clean: `UP_TO_DATE update-check=disabled` (user turned the check off via config) and `UP_TO_DATE update-check=snoozed` (user has an active snooze on the current version key). The split is at the template level (`templates/skills/shared/preamble.md.j2`); all generated SKILL.md files inherit the new wording on rebuild. Closes a class of "agent looked fine but env-check was silently broken" issues that previously surfaced only when something else later failed.
- **`bin/mthds-env-check` reordering: Codex config check runs before `update-check`.** The wrapper previously called `mthds-agent update-check` first, captured its output, then ran the Codex `apply-config --check` (when `--codex` was set) and conditionally suppressed update-check's stdout. That ordering had a hidden bug: update-check's `just-upgraded-from` marker is a one-shot, consumed destructively on first read — so a Codex-broken run would consume the marker, suppress the `JUST_UPGRADED` line that should announce the upgrade, and lose it forever. The wrapper now runs the Codex check first; when it fails, it emits `CODEX_CONFIG_NEEDS_SETUP` (plus up to 20 lines of `#`-prefixed stderr diagnostic, up from `head -n 1` which only captured the opening `{` of mthds-agent's pretty-printed JSON envelope) and exits before calling update-check. The marker stays intact and fires on the next run after the user fixes Codex and restarts. Without `--codex` (Claude Code path) the wrapper behavior is unchanged.
- **Bump `min_mthds_version` from 0.8.1 to 0.9.0.** mthds-js 0.9.0 emits the explicit `UP_TO_DATE` line that the new preamble rule depends on, adds the remote upstream probes that close the "silent when both stale" gap (npm + marketplace.json fetched in parallel, 24h-cached for complete responses, 1h-cached for partial responses to avoid locking nulls, fail-silent on offline), and adds the `UP_TO_DATE update-check=snoozed` sentinel the new preamble recognizes so snoozed users no longer trip the no-output WARN rule. Consumers on an older `mthds-agent` get no `UP_TO_DATE` line and would trip the new "no output" WARN branch on every run — the env-check therefore fails its agent floor check with a clean upgrade prompt instead, routing them through the standard upgrade flow before they hit the WARN.

## [v0.11.3] - 2026-05-26

### Fixed

- **PostToolUse validate hook no longer silently passes broken `.mthds` files (Claude side).** Pipelex 0.29 flipped the agent CLI's error output to markdown-by-default; the hook's Stage 3 was parsing stderr as JSON, the parse failed, and the script took its "warn and pass" branch — meaning structurally broken bundles saved through Claude Code stopped being blocked. Rewrote Stage 3 to consume pipelex's markdown error envelope directly: BLOCKs on input-domain errors with the trimmed markdown as the agent-actionable reason, and uses Claude Code's `hookSpecificOutput.additionalContext` to surface config/runtime errors to the agent without blocking (config/runtime are environment issues, not bundle issues — the agent shouldn't edit the file). Empty or absent `error_domain` defaults to BLOCK for safety. The hook strips pipelex's `## Error source` stack-trace section defensively; on the supported floor (pipelex 0.30.2+ via the mthds-js bump below) the section is already gone, so the strip is a no-op kept only to protect against custom pipelex builds.
- **Codex PostToolUse hook now blocks broken `.mthds` files too (parity with Claude).** The Codex hook (`mthds-agent codex hook`, in mthds-js) previously stopped after `plxt lint` + `plxt fmt`; semantic validation was disabled because earlier pipelex builds eagerly fetched remote config on startup, which the Codex sandbox blocks. Pipelex's `validate bundle` path is offline-safe (no gateway / remote-config fetch), so mthds-js 0.8.1 re-enables Stage 3 with the same markdown-first decision tree as the Claude hook. The plugin pulls this through transparently via the floor bump below; no plugin-side hook config changes were needed because the Codex hook's logic ships in the npm package, not in the plugin.

### Changed

- **Bump `min_mthds_version` from 0.7.0 to 0.8.1.** mthds-js 0.8.1 floors pipelex / pipelex-agent at `>=0.30.2` and ships the Codex Stage 3 enablement noted above. The transitive chain: 0.30.0 routes pipelex logs to stderr so JSON consumers no longer get polluted stdout; 0.30.1 silences every Python logger on `pipelex-agent`'s stderr regardless of user TOML (a user setting `package_log_levels.pipelex = "DEBUG"` can no longer corrupt the stderr envelope); 0.30.2 drops the `## Error source` stack-trace section from the markdown error envelope (internal frames are noise for an LLM trying to fix a `.mthds`). mthds-js 0.8.0 separately fixed five PipelexRunner `JSON.parse` paths broken by the pipelex 0.29.0 markdown-by-default contract change. Consumers on older `mthds-agent` fail the env-check with a clean upgrade prompt.
- **Skill doc `mthds-agent-guide.md` updated for pipelex 0.29 changes.** The `--graph` flag for `validate bundle` documents the renamed `--graph-format <format>` option (was `--format <format>`), and the surrounding `graph_files` claim is now markdown-first: the generated graph path appears in stderr logs, and is only in the JSON envelope when `--format json` is set.

## [v0.11.2] - 2026-05-21

### Documentation

- **Document the `mthds-vibe` skill.** The skill shipped in v0.11.0 but was not listed in the README skill table or mentioned in the changelog, so users had no way to discover it through normal documentation. Added a row to the README skill inventory and documented the skill below under v0.11.0 (where it actually shipped). The skill itself is unchanged.

## [v0.11.1] - 2026-05-17

### Changed

- **The `CODEX_CONFIG_NEEDS_SETUP` env-check signal now drives an offer-then-run flow instead of a passive warning.** When a skill's Step 0 env-check finds `~/.codex/` not set up for the plugin, the preamble previews the fix with `mthds-agent codex apply-config --dry-run`, asks the user, and runs `apply-config` — falling back to handing over the command if the Codex sandbox blocks the write to `~/.codex/config.toml`. It relays any `warnings` (read-only sandbox, hooks disabled) that `apply-config` deliberately will not auto-fix, and is explicit that the bundled hook only loads after a Codex restart — so the current session relies on the skills' own explicit `plxt lint` + `validate bundle` steps. Previously the skill only warned and proceeded, leaving the user to resolve the gap unaided. Detection was already correct; this closes the resolution gap in the skill instruction.

## [v0.11.0] - 2026-05-15

### Added

- **`mthds-vibe` skill.** A single-pass authoring path: write a complete `bundle.mthds` in one go, then let the PostToolUse hook and an explicit `validate bundle` step catch errors. Scope is deliberately narrower than `mthds-build` (no `dict` fields, no `PipeStructure`, no inline `templating_style` blocks) — when those come up the skill is instructed to emit the closest in-scope equivalent and flag the deviation. On Claude Code the skill is `disable-model-invocation: true` (explicit `/mthds-vibe` only); on Codex it's discoverable normally. Ships with a `vibe-cheat-sheet.md` reference under `skills/mthds-vibe/references/`.

### Changed

- **Codex validation hook is now bundled in the plugin.** Codex 0.129–0.130 added plugin-bundled hook discovery: a plugin can declare a `hooks` entry in `.codex-plugin/plugin.json` and Codex loads it directly. The plugin now ships `hooks/codex-hooks.json` — a `PostToolUse(^apply_patch$)` entry invoking `mthds-agent codex hook` — and declares it in the Codex manifest. This replaces the per-user `mthds-agent codex install-hook` step. **Requires Codex 0.130.0+** (was 0.124.0+); plugin-bundled hooks load only when `[features] plugin_hooks = true`.
- **`mthds-agent codex apply-config` now also enables `[features] plugin_hooks`.** Codex loads plugin-bundled hooks only when that flag is set, and it is off by default — so `apply-config` merges it alongside the existing `[sandbox_workspace_write] network_access = true`. `apply-config` additionally sweeps any obsolete `PostToolUse`/`Stop` entry the retired `install-hook` left in `~/.codex/hooks.json`, so the bundled hook never fires twice.
- **Bump `min_mthds_version` from 0.6.3 to 0.7.0.** mthds-js 0.7.0 ships the multi-key `apply-config` and is the release that removes `install-hook`. Consumers on an older `mthds-agent` fail the env-check with a clean upgrade prompt.
- **Codex env-check signal `CODEX_SANDBOX_NETWORK_MISSING` renamed to `CODEX_CONFIG_NEEDS_SETUP`.** `bin/mthds-env-check` runs `apply-config --check`, which now also flags a missing `plugin_hooks` key or a leftover hook entry — not just sandbox network — so the signal name and the skill preamble's wording were generalized.

### Removed

- **The `mthds-agent codex install-hook` install step.** **Breaking (Codex).** The hook ships with the plugin, so there is no per-user wiring step. Existing installs are cleaned up automatically — `mthds-agent codex apply-config` removes the stale `~/.codex/hooks.json` entry the old step left behind.

## [v0.10.3] - 2026-05-12

### Fixed

- **`validate-mthds.sh` no longer blocks non-`.mthds` Edit/Write operations.** The PostToolUse hook fires on every Write/Edit (matcher `"Write|Edit"`, no file-pattern filter), and a bug in its gating order meant a Node.js JSON-parser failure would emit a `decision: block` payload against unrelated files (`.ts`, `.py`, `.md`, anything). The `.mthds` extension check ran *after* the unconditional block on `_jv` failure. Moved the `.mthds` pre-filter to the top of the script so non-`.mthds` payloads exit silently before any Node, `plxt`, or `mthds-agent` invocation — blast radius drops from "any Write/Edit in any session" to "edits to `.mthds` files only".

### Changed

- **Hook now scoped to `.mthds` files at the harness level via Claude Code's `if` permission rule.** The PostToolUse handler in `hooks.json` carries `if: "Edit(*.mthds)"` / `if: "Write(*.mthds)"` (two separate handlers per the Claude Code docs — `|` is not supported inside `if`), so the script is never invoked for unrelated edits in the first place — no process spawn, no stdin read, no Node. The script-level bash pre-filter remains as defense-in-depth and is still the primary filter for the Codex target, where no native file-pattern matcher exists yet (tracked upstream as openai/codex#21753).

## [v0.10.2] - 2026-05-11

### Changed

- **Bump `min_mthds_version` from 0.6.2 to 0.6.3.** The new `mthds-agent` ships two fixes that this release surfaces to users: (1) plugin-version detection now works under Codex (previously read only the Claude Code registry, so Codex users saw `plugin: outdated 0.10.0, required >=0.10.1` when their Codex install was actually fine); (2) the update-check cache writer falls back to `$TMPDIR/mthds-agent/` when `~/.mthds/state/` is unwritable, eliminating the repeated `Warning: could not write update-check cache (EPERM)` users hit inside Codex's `workspaceWrite` sandbox. Users still on `mthds-agent` 0.6.2 will be prompted to upgrade.
- `PLUGIN_UPDATE_AVAILABLE` emitted by `mthds-agent` now includes a `host` field (`"claude" | "codex"`) and a host-appropriate `cmd` (Codex sessions see `/plugins install mthds` instead of the Claude shell command). Skill preambles do not yet branch on this field — that's a follow-up once we standardize host-aware upgrade prompts.

## [v0.10.1] - 2026-05-05

### Changed

- Bump `min_mthds_version` from 0.6.0 to 0.6.2.
- Document the `live_run_graph.json` artifact in the `mthds-run` skill and shared `mthds-agent-guide`. Live runs write the graph spec JSON next to the bundle alongside the existing `live_run.html` / `dry_run.html`.

## [v0.10.0] - 2026-04-30

### Changed

- **`mthds-install` skill drops `--agent` and `--skills` flags from the documented surface.** **Breaking.** Coordinated with mthds-js 0.6.0, which removes both flags from `mthds-agent install`. Method packages always install under `.mthds/methods/` regardless of which agent runs the command — `--agent` was meaningless. Skills are installed via the Claude Code / Codex plugin systems, not by the method install command.
- **Bump `min_mthds_version` from 0.5.0 to 0.6.0.** Consumers running an older `mthds-agent` will fail the env-check with a clean upgrade prompt rather than hitting an "unknown option `--agent`" error from the CLI. mthds-js 0.6.0 reciprocally enforces plugin >= 0.10.0, so the floors catch any partial upgrade in either direction.
- Minor template hygiene: `mthds-runner-setup` skill now uses `{{ harness_name }}` instead of hardcoded "Claude Code" so the Codex target renders correctly.

### Removed

- **Dead `default_agent` template variable.** No `.j2` template or build script references it after the `mthds-install` skill changes; deleted from `targets/defaults.toml` and `targets/codex.toml`.

## [v0.9.0] - 2026-04-29

### Changed

- Codex hook switched from `Stop` to `PostToolUse(apply_patch)` for per-edit `.mthds` validation, matching the Claude Code semantics. Codex 0.124.0 fixed the upstream blocker (apply_patch now emits hook payloads).
- Codex install no longer needs the curl-pipe-bash plugin install path: `codex plugin marketplace add mthds-ai/mthds-plugins` (Codex 0.124.0+) handles plugin install via the marketplace. The repo ships `.agents/plugins/marketplace.json` (generated from canonical `packaging/codex-marketplace.json`) so `codex plugin marketplace add` resolves cleanly.
- Codex hook validation logic moved from a bash script (`codex-validate-mthds.sh`) into the `mthds-agent codex hook` runtime (mthds-js npm package, requires ≥ 0.5.0). The hook config in `~/.codex/hooks.json` now invokes `mthds-agent codex hook` directly; no bash script is copied to `~/.codex/hooks/`.
- Skill preambles now resolve `mthds-env-check` from the plugin's per-version cache directory (`$CODEX_HOME/plugins/cache/*/mthds/*/bin/mthds-env-check`) instead of `~/.codex/bin/mthds-env-check`. The env-check binary is no longer copied out of the plugin. Version selection across cached versions uses semver-aware sort keys (zero-padded numeric segments), so the resolver correctly picks `0.10.0` over `0.9.0` rather than the lex-greatest match. Stays in pure bash to preserve the layering invariant: env-check verifies mthds-agent is installed and therefore must not depend on mthds-agent itself.

### Removed

- `bin/install-codex.sh` — replaced by `mthds-agent codex install-hook` (in mthds-js 0.5.0). The new install line is `npm install -g mthds && mthds-agent bootstrap && mthds-agent codex install-hook && mthds-agent codex apply-config && codex plugin marketplace add mthds-ai/mthds-plugins`.
- `templates/hooks/codex-hooks.json.j2` and `templates/hooks/codex-validate-mthds.sh.j2` — Codex plugin no longer ships hook files (validation runtime lives in the agent).
- `~/.codex/bin/mthds-env-check` copy step — env-check is read from the plugin install dir directly.

### Migration

- Pre-existing installs (with the legacy `Stop` hook or the WIP-0.9.0 `PostToolUse(apply_patch)` entry pointing at `codex-validate-mthds.sh`) are migrated automatically when the user runs `mthds-agent codex install-hook`: stale entries are removed and replaced with the new shape. Stale `~/.codex/hooks/codex-validate-mthds.sh` and `~/.codex/bin/mthds-env-check` files left from previous installs are harmless; they can be deleted manually if desired.

## [v0.8.0] - 2026-04-13

### Added

- OpenAI Codex CLI plugin target (`mthds-codex`) — full MTHDS skill set adapted for the Codex agent platform
- Codex-specific hooks (`codex-hooks.json`, `codex-validate-mthds.sh`) for `.mthds` file validation
- Codex install script (`bin/install-codex.sh`) for automated plugin setup
- `.agents/plugins/marketplace.json` for Codex plugin marketplace listing
- Documentation comparing Codex vs Claude hook systems (`docs/codex-vs-claude-hooks.md`)

### Changed

- Build system extended to support Codex as a third target alongside prod and dev
- `check.py` updated to validate Codex targets and detect Claude artifacts in Codex output
- Template frontmatter and preamble adapted for multi-agent platform support

## [v0.7.1] - 2026-04-06

### Fixed

- Hook silent failures: Stage 3 Node.js crash now blocks instead of logging a warning; `_jv` helper checks exit code
- check.py: derive `STALE_REF_PATTERN` from `SHARED_TEMPLATES` (was missing python-execution); remove silent `ValueError` fallback

### Changed

- Bump min_mthds_version from 0.3.4 to 0.3.5

## [v0.7.0] - 2026-04-02

### Added

- Multi-target build system: TOML-based target configs in `targets/` with
  defaults + per-target variable overrides and optional skill filtering
- Dev plugin target (`mthds-dev`) for development iteration, built from the
  same templates with independent versioning
- Architecture docs in `docs/build-targets.md`

### Changed

- Template variable source of truth moved from `mthds-agent-guide.md` regex
  to `targets/defaults.toml`
- `mthds-agent-guide.md` is now a Jinja2 template (`.j2`), rendered per target
- `preamble.md` uses `{{ marketplace_name }}` instead of hardcoded path
- `make build` now builds all targets; `make check` validates all targets
- Simplified `/bump-mthds-version` skill: single edit to `defaults.toml`
- Updated `/release` skill for multi-target version management
- Simplified Tier 1 prereqs: replaced manual tool checks with `mthds-agent bootstrap`

## [v0.6.2] - 2026-03-30

### Added

- Version sync check in `make check` — verifies plugin.json and marketplace.json have matching versions
- Changelog support in the `/release` skill workflow

### Changed

- Updated README install instructions with correct plugin name and `/reload-plugins` flow
