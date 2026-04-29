# TODOS — Codex plugin parity with Claude Code

Goal: bring the Codex plugin install UX, hooks, and reliability on par with the Claude Code plugin, leveraging fixes shipped in `codex` 0.124.0+ (latest `rust-v0.126.0-alpha.8` as of 2026-04-28). Three of the five blockers we hit when we built the Codex plugin in early April 2026 are now fixed; one is still upstream-blocked; one is moot.

---

## Status update — 2026-04-28: Phase 1 SHIPPED (final shape diverged)

Phase 1 is done. The plan below is preserved for historical context, but the path actually taken differs in two material ways:

1. **`bin/install-codex.sh` deleted entirely**, not slimmed. Its three remaining responsibilities (env-check copy, hook script copy, JSON merge) collapsed: env-check is now read from the plugin's per-version cache directory, and the hook runtime moved into mthds-agent itself (see 2 below). The JSON merge is what `mthds-agent codex install-hook` does.

2. **Hook runtime moved from a bash script into mthds-agent.** mthds-js 0.5.0 ships two new pieces:
   - `mthds-agent codex install-hook` (rewritten) writes a `PostToolUse(apply_patch)` entry whose `command` is the literal string `mthds-agent codex hook` — PATH-resolved at hook-fire time, not a path to a copied script. Migrates legacy `Stop` and legacy `PostToolUse` entries from earlier shapes.
   - `mthds-agent codex hook` (new runtime) — TS port of the bash hook logic. The plugin no longer ships any `hooks/` files. Single source of truth across Claude and Codex (Claude still uses its bundled bash script for now, retained as legacy; Codex routes through the agent).

Concrete diffs in this repo:
- Deleted: `bin/install-codex.sh`, `templates/hooks/codex-hooks.json.j2`, `templates/hooks/codex-validate-mthds.sh.j2`, `mthds-codex/hooks/`, `tests/unit/test_install_codex_version_ge.py`, `tests/integration/test_hook_codex_validate_mthds.py`.
- `templates/skills/shared/preamble.md.j2` — Codex env-check path replaced with a glob over `$CODEX_HOME/plugins/cache/*/mthds/*/bin/mthds-env-check`.
- `scripts/gen_skill_docs.py` — `HOOK_TEMPLATES_BY_PLATFORM[Platform.CODEX] = []`.
- `targets/defaults.toml` — `min_mthds_version = "0.5.0"`.
- README, CHANGELOG, CLAUDE.md, docs/codex-vs-claude-hooks.md updated for the new install line: `npm install -g mthds && mthds-agent bootstrap && mthds-agent codex install-hook && codex plugin marketplace add mthds-ai/mthds-plugins`.

Regression net: `internal-tools/tests/test-nelly-plugin-install.sh` (PHASE=B) drives the install end-to-end inside a Nelly container.

### What changed in the Phase-2 list

- **2A** (upstream `hooks` field deserializer) — STILL PENDING. Now matters less: when it lands, the install line drops `mthds-agent codex install-hook`, but the runtime stays in mthds-agent (no bash to bundle).
- **2B** (move script into plugin once `hooks` lands) — MOOT. There is no script to bundle anymore.
- **2C** (one-shot `codex plugin install`) — STILL PENDING (upstream).
- **2D** (mthds-agent offline-mode validation) — STILL PENDING. Stage 3 stays disabled in `mthds-agent codex hook` (`src/agent/commands/codex-hook.ts`) until this lands.
- **2E** (close out tracked issues) — STILL PENDING.
- **2F** (unify Claude/Codex hook templates) — partially MOOT — Codex no longer has a hook template at all. Claude's bash script could in principle be replaced with a `mthds-agent claude hook` parallel, but no driver for that today; defer.
- **2G** (move install logic into bootstrap or agent) — DONE in the form of `mthds-agent codex install-hook` (mthds-js 0.5.0). `bootstrap` itself stays platform-agnostic per the user's preference.

---

## Status of original blockers

| #   | Blocker                                                  | Status                       | Phase   |
| --- | -------------------------------------------------------- | ---------------------------- | ------- |
| 1   | PostToolUse doesn't fire for apply_patch (#16732)        | FIXED in 0.124.0 (PR #18391) | Now     |
| 2   | No `codex marketplace add` / plugin install CLI (#17087) | FIXED — `codex plugin marketplace add` | Now     |
| 3   | Hooks can't be bundled in plugin manifest                | NOT FIXED                    | Later   |
| 4   | Sandbox blocks `SystemConfiguration.framework` on macOS  | FIXED (PR #16670)            | Now (re-test Stage 3) |
| 5   | Personal marketplace at `~/.agents/plugins/` (#16500)    | FIXED differently            | Moot    |

Reference paths in `/Users/lchoquel/repos/OpenSource/codex`:
- `codex-rs/core/src/tools/handlers/apply_patch.rs:317-339` — apply_patch hook payloads
- `codex-rs/core/src/tools/hook_names.rs:28-39` — `apply_patch` canonical name + `Write|Edit` aliases
- `codex-rs/cli/src/marketplace_cmd.rs:25-48` — `add | upgrade | remove`, accepts `owner/repo[@ref] | url | path`
- `codex-rs/core-plugins/src/marketplace.rs:20-23` — `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json` both accepted (PR #18182)
- `codex-rs/core-plugins/src/manifest.rs:11-30` — `RawPluginManifest` (no `hooks` field)
- `codex-rs/sandboxing/src/seatbelt_network_policy.sbpl:24-26` — SystemConfiguration mach-lookup allowlist

---

## Target end-state (Phase 1 done)

```
Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && codex plugin marketplace add mthds-ai/mthds-plugins'. Then tell me to restart Codex and run /plugins to install mthds.
```

vs the current curl-pipe-bash 7-step install. Two remaining gaps from the Claude Code line are upstream-blocked (Phase 2):
- The `mthds-agent bootstrap` step quietly handles hook wiring (Codex doesn't auto-load `hooks` from plugins yet).
- The manual `/plugins` step after restart (Codex has no one-shot `codex plugin install <name>@<marketplace>` CLI yet).

---

## Phase 1 — NOW (all in this repo)

### 1A. Verify upstream behavior before coding

These are ground-truth checks that drive the rest. Record results inline in this section.

- [ ] **Codex version on dev machine**: `codex --version` ≥ 0.124.0. Bump if needed via `npm install -g @openai/codex@latest`.
- [ ] **PostToolUse fires for apply_patch**: register a no-op shell hook with `"matcher": "apply_patch"`, edit a file in a Codex session, capture the stdin JSON. Record:
  - exact `tool_name` value (canonical `apply_patch` vs alias)
  - exact path field (`tool_input.file_path`? `tool_input.input` raw text? `tool_input.changes[].path`?)
  - source: `codex-rs/core/src/tools/handlers/apply_patch.rs:317-339`
  - **This drives the hook script rewrite in 1B.**
- [ ] **`codex plugin marketplace add` shape**: `codex plugin marketplace add --help`. Confirm: positional `<owner/repo[@ref] | url | path>`, flags `--ref`, `--sparse PATH`. Confirm `codex marketplace add` (without `plugin`) is rejected (`codex-rs/cli/src/main.rs:1939-1949`).
- [ ] **Marketplace discovery precedence**: with both `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` present in a repo, does Codex pick one, merge them, or error? Source: `codex-rs/core-plugins/src/marketplace.rs:20-23`. Determines whether 1C must include changes to `.claude-plugin/marketplace.json` to avoid Codex picking it up.
- [ ] **Local-path marketplace add works**: `codex plugin marketplace add /Users/lchoquel/repos/Pipelex/mthds-plugins` (after 1C lands). `mthds` should appear in `/plugins` list.
- [ ] **Owner/repo marketplace add works**: `codex plugin marketplace add mthds-ai/mthds-plugins` from a clean dir, against the upstream branch with 1C merged.
- [x] **`[features] codex_hooks = true` still required**: NO. Verified in `codex-rs/features/src/lib.rs:768-771` — `FeatureSpec { id: Feature::CodexHooks, key: "codex_hooks", stage: Stage::Stable, default_enabled: true }`. Hooks load by default in 0.124+; the flag is only consulted as a kill-switch (explicit `false` disables hooks). Install flow drops the line; `mthds-agent codex apply-config` warns (without modifying) when an explicit `false` is set.
- [ ] **Stage 3 unblocked?**: from inside a Codex session sandbox, run `mthds-agent validate bundle <path>` against a known-good bundle. If it completes (no S3 hang on `pipelex_remote_config_08.json`), re-enable Stage 3 in 1B. If it still hangs, leave Stage 3 disabled and create a Phase 2 task in mthds-js for offline mode.

### 1B. Switch the Codex hook from `Stop` to `PostToolUse(apply_patch)`

Files:
- `templates/hooks/codex-hooks.json.j2`
- `templates/hooks/codex-validate-mthds.sh.j2`
- `mthds-codex/hooks/codex-hooks.json` (regenerated)
- `mthds-codex/hooks/codex-validate-mthds.sh` (regenerated)

Changes:
- [ ] **Hook config (`templates/hooks/codex-hooks.json.j2`)**: replace `Stop` with `PostToolUse` and add a matcher. Use the canonical `apply_patch` name:
  ```json
  {
    "hooks": {
      "PostToolUse": [
        {
          "matcher": "apply_patch",
          "hooks": [
            {
              "type": "command",
              "command": "~/.codex/hooks/codex-validate-mthds.sh",
              "timeout": 30
            }
          ]
        }
      ]
    }
  }
  ```
- [ ] **Hook script (`templates/hooks/codex-validate-mthds.sh.j2`)**: rewrite per 1A's payload schema. Drop the entire transcript-parsing block (lines ~28-58 in the current template). Structure becomes very close to the Claude Code template `templates/hooks/validate-mthds.sh.j2`:
  1. Read stdin (PostToolUse JSON)
  2. Extract file path with `_jv` (using the field name from 1A; if it's the apply_patch raw text, parse one `Update File:` / `Add File:` line — much simpler than transcript parsing)
  3. Pass-silently if not `.mthds`
  4. Stage 1: `plxt lint` (block on errors)
  5. Stage 2: `plxt fmt` (warn on errors)
  6. Stage 3: `mthds-agent validate bundle` — re-enable conditional on 1A
- [ ] **Stage 3 conditional**: if 1A says sandbox is unblocked, port the Claude template's Stage 3 logic verbatim (the `node -e` block that classifies errors). If still blocked, keep Stage 3 disabled and update the inline comment to reference the new mthds-js offline-mode task in Phase 2D.
- [ ] **Regenerate**: `make build`. Confirm `mthds-codex/hooks/codex-hooks.json` and `mthds-codex/hooks/codex-validate-mthds.sh` match the templates.
- [ ] **Sanity test**: run `make check` — freshness + Codex packaging consistency must pass.

### 1C. Add `.agents/plugins/marketplace.json` to the repo (Codex-discoverable)

Files:
- `.agents/plugins/marketplace.json` (new — checked in, generated)
- `packaging/codex-marketplace.json` (existing — remains canonical source)
- `scripts/gen_skill_docs.py` (extend to copy/render the marketplace file)
- `scripts/check.py` (verify the generated file matches canonical)
- `.gitignore` (ensure `.agents/plugins/marketplace.json` is NOT ignored)

Changes:
- [ ] **Keep `packaging/codex-marketplace.json` as canonical** (single source of truth). It currently points to `./mthds-codex`, which is correct.
- [ ] **Generate `.agents/plugins/marketplace.json` from canonical** at build time:
  - Add a step in `scripts/gen_skill_docs.py` (or a new tiny `scripts/sync_codex_marketplace.py`) that reads `packaging/codex-marketplace.json` and writes it verbatim to `.agents/plugins/marketplace.json`. Path remains `./mthds-codex` — both files live at repo root, so the relative path is unchanged.
  - Add the file to `make build`.
  - Add a freshness check in `scripts/check.py --scope codex`.
- [ ] **Decide based on 1A's marketplace-precedence finding**: if Codex picks up `.claude-plugin/marketplace.json` and gets confused (because that file lists the Claude `mthds/` plugin which has `.claude-plugin/plugin.json`, not `.codex-plugin/plugin.json`), do one of:
  - Option A — leave both files; rely on Codex's plugin-loader to skip the Claude entry (because `mthds/` has no `.codex-plugin/plugin.json`). **Verify** this is the actual behavior.
  - Option B — namespace the Codex marketplace differently (`.agents/plugins/marketplace.json` only, no `.claude-plugin/marketplace.json` change).
  - Default to A unless 1A shows it breaks.
- [ ] **End-to-end test**: `codex plugin marketplace add mthds-ai/mthds-plugins` (from a fresh dir). Confirm `mthds` shows up in `/plugins` and installs cleanly into `$CODEX_HOME/plugins/cache/mthds-plugins/mthds/<version>/`.

### 1D. Slim `bin/install-codex.sh`

The marketplace step is now Codex's job. The install script keeps only what Codex can't yet do: hooks + (maybe) feature flag + env-check binary.

Files:
- `bin/install-codex.sh`

Changes:
- [ ] **Remove**:
  - `setup_plugin()` (Codex CLI handles plugin file install via marketplace)
  - `setup_marketplace()` and `render_repo_local_marketplace()` (replaced by `codex plugin marketplace add`)
  - `verify_install` checks for `$PWD/plugins/mthds/.codex-plugin` and `$PWD/.agents/plugins/marketplace.json`
  - The `TODO-WHEN-0.119.0` block (close-out — 3 of 4 items resolved, 1 moot)
  - GitHub-clone fallback path in `resolve_plugin_source` (no longer needed)
- [ ] **Keep**:
  - `install_mthds_cli` — mthds-agent dependency (with `MIN_MTHDS_VERSION` bumped per 1B Stage 3 decision if applicable)
  - `install_env_check` — copies `bin/mthds-env-check` to `~/.codex/bin/`, used by SKILL.md preambles
  - `setup_hooks` — calls `mthds-agent codex install-hook` to merge hook into `~/.codex/hooks.json`
  - ~~`enable_hooks_feature`~~ — DELETE (1A confirmed not required at 0.124.0+; flag is `Stage::Stable, default_enabled: true`)
- [ ] **Stretch goal (recommended)**: collapse the entire script into `mthds-agent bootstrap`. In the mthds-js repo, extend `bootstrap` to detect Codex (presence of `~/.codex/`) and run hook install + env-check copy automatically. This eliminates `bin/install-codex.sh` and the curl-pipe-bash entirely. Tracked in 2G.
- [ ] **If stretch doesn't land in this phase**, the script is now ~150 lines (down from ~415). Smaller surface area, less to maintain.

### 1E. Update README install snippets

Files:
- `README.md`
- `CHANGELOG.md`

Changes:
- [ ] **Replace lines 24-39 in `README.md`** with the new install instructions. Two scenarios depending on whether 1D's stretch goal lands:

  **If `mthds-agent bootstrap` handles hooks (preferred)**:
  ```markdown
  ## Install for Codex

  Open Codex and paste this. Codex does the rest.

  ```
  Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && codex plugin marketplace add mthds-ai/mthds-plugins'. Then tell me to restart Codex and run /plugins to install mthds.
  ```

  ### Manual install (Codex)

  ```bash
  npm install -g mthds
  mthds-agent bootstrap
  codex plugin marketplace add mthds-ai/mthds-plugins
  # Restart Codex, then run /plugins to install mthds
  ```
  ```

  **If `bin/install-codex.sh` is still needed (fallback)**:
  ```markdown
  Install mthds: run bash -c 'npm install -g mthds && mthds-agent bootstrap && codex plugin marketplace add mthds-ai/mthds-plugins && mthds-agent codex install-hook'. Then tell me to restart Codex and run /plugins to install mthds.
  ```
  (`mthds-agent codex install-hook` already exists per `bin/install-codex.sh:278`. Bundle env-check copy into it too — small change in mthds-js.)
- [ ] **Update CHANGELOG.md**: "Codex plugin: switched from `Stop` hook to `PostToolUse(apply_patch)` for per-edit validation, matching Claude Code semantics. Marketplace install now uses `codex plugin marketplace add` (Codex 0.124.0+). Removed transcript-parsing fallback. Removed curl-pipe-bash install path."

### 1F. Update CLAUDE.md and docs

Files:
- `CLAUDE.md`
- `docs/codex-vs-claude-hooks.md`

Changes:
- [ ] In `CLAUDE.md`, update the "PostToolUse Hook" section: Claude and Codex hooks now use the same event with the same matcher semantics; only the JSON wiring differs (Codex still merges into `~/.codex/hooks.json` instead of plugin-bundled).
- [ ] In `docs/codex-vs-claude-hooks.md`:
  - Replace the "Stop hook" / "transcript parsing" sections with the new PostToolUse setup
  - Update the "Why an install script" section to reflect what's left (hook wiring only, until Phase 2 closes it)
  - Update "Tracked upstream issues":
    - #16732 — mark FIXED in 0.124.0 (PR #18391)
    - #17087 — mark SHIPPED as `codex plugin marketplace add`
    - #14754 — mark FIXED (subsumed by #16732)
    - Add a new tracked issue (or PR) for the plugin-manifest `hooks` field
  - Update the "TODO" section at the bottom to point to this `TODOS.md`

### 1G. Tests

Files:
- `tests/`

Changes:
- [ ] Add a unit test that takes a fixture PostToolUse JSON for apply_patch (captured during 1A) and asserts the hook script extracts the correct file path. Use a fixture both for the canonical `apply_patch` payload and for any edge case (e.g., multi-file patch — does the hook fire once per file or once per patch?).
- [ ] If the hook fires once per multi-file patch, add a regression test confirming all `.mthds` files in the patch are validated.
- [ ] Run `make agent-test`.
- [ ] Run `make agent-check`.

### 1H. Bump versions

Files:
- `targets/codex.toml`
- `.claude-plugin/marketplace.json` (metadata.version, if bumped on any release)
- `targets/defaults.toml` (if `min_mthds_version` changes — only if 1B Stage 3 re-enable requires a newer mthds-agent)

Changes:
- [ ] Bump `targets/codex.toml [plugin].version` 0.8.1 → 0.9.0 (breaking install-flow change).
- [ ] Bump `.claude-plugin/marketplace.json` `metadata.version`.
- [ ] If Stage 3 re-enable requires a newer mthds-agent: bump `targets/defaults.toml [vars].min_mthds_version` (and align `MIN_MTHDS_VERSION` in `bin/install-codex.sh`).
- [ ] `make build` then commit regenerated artifacts (`mthds-codex/.codex-plugin/plugin.json`, hooks).

---

## Phase 2 — LATER (upstream-blocked or out-of-repo)

### 2A. Upstream: plugin-manifest `hooks` field deserializer

Codex's `RawPluginManifest` (`codex-rs/core-plugins/src/manifest.rs:11-30`) deserializes only `name | version | description | skills | mcp_servers | apps | interface`. The plugin-spec doc `codex-rs/skills/src/assets/samples/plugin-creator/references/plugin-json-spec.md:18,64` documents `"hooks": "./hooks.json"` but the deserializer drops it. `HookSource` enum (`codex-rs/app-server-protocol/schema/typescript/v2/HookSource.ts`) has no `plugin` variant.

- [ ] Search openai/codex issues for an existing report. If none, file one with a minimal repro: a plugin with `"hooks": "./hooks.json"` in `plugin.json` and a `hooks/hooks.json`, show that the runtime never registers it.
- [ ] Optional PR: add `hooks: Option<PathBuf>` to `RawPluginManifest`, plumb a new `HookSource::Plugin { plugin_id, path }` variant, register `hooks.json` from the plugin-loader.

### 2B. When `hooks` lands in plugin manifest

- [ ] Move hook script from `~/.codex/hooks/` to `mthds-codex/hooks/` (already there), reference from plugin via `${CODEX_PLUGIN_ROOT}` or whatever Codex names it.
- [ ] Add `"hooks": "./hooks/codex-hooks.json"` to `mthds-codex/.codex-plugin/plugin.json` and to the template.
- [ ] **Delete `bin/install-codex.sh` entirely**. `mthds-agent codex install-hook` becomes a no-op (or removed). Full install collapses to:
  ```bash
  npm install -g mthds && mthds-agent bootstrap && codex plugin marketplace add mthds-ai/mthds-plugins
  ```

### 2C. When single-shot `codex plugin install <repo>` lands

Today: marketplace add → restart → `/plugins` install. Claude Code does this in one CLI call.

- [ ] When upstream ships a one-shot CLI install, drop the `/plugins` step. README install line becomes a true one-shot equivalent to Claude Code's. Codex install UX is then on full par.
- [ ] Track via openai/codex issue tracker.

### 2D. mthds-agent offline mode (mthds-js repo)

Conditional on 1A's Stage 3 finding. If `mthds-agent validate bundle` still hangs in the Codex sandbox due to the S3 remote-config fetch:

- [ ] In mthds-js, add an offline mode (or lazy fetch with skip-on-failure) so `validate bundle` doesn't depend on remote config.
- [ ] When shipped: re-enable Stage 3 unconditionally in `templates/hooks/codex-validate-mthds.sh.j2`. Bump `min_mthds_version` in `targets/defaults.toml`.

### 2E. Close out tracked issues

After Phase 1 ships:
- [ ] Comment on openai/codex#16732 confirming the fix solves the use case; reference our `PostToolUse(apply_patch)` switchover commit.
- [ ] Comment on openai/codex#17087 confirming switchover from custom install script to `codex plugin marketplace add`.
- [ ] Comment on openai/codex#14754 (subsumed by #16732).
- [ ] Update `docs/codex-vs-claude-hooks.md` "Tracked upstream issues" section.

### 2F. Optional: unify Claude and Codex hook scripts

If 1A shows the Codex `PostToolUse(apply_patch)` payload is shape-compatible with Claude's `PostToolUse(Write|Edit)`:
- [ ] Collapse `validate-mthds.sh.j2` and `codex-validate-mthds.sh.j2` into one template, conditioned on `platform`.
- [ ] Same for `hooks.json.j2` and `codex-hooks.json.j2`.
- [ ] Update `scripts/gen_skill_docs.py` `HOOK_TEMPLATES_BY_PLATFORM` (currently routes Claude vs Codex to different files) — collapse to a single list with platform-conditional templates.
- [ ] Removes ~200 lines of duplication. Quality-of-life win, not user-facing.

### 2G. Move install logic into `mthds-agent bootstrap` (mthds-js repo)

Stretch goal from 1D, lifted to Phase 2 if not done in Phase 1:
- [ ] In mthds-js, extend `mthds-agent bootstrap` to detect Codex (presence of `~/.codex/`) and:
  - Copy `mthds-env-check` from the npm-installed location to `~/.codex/bin/`
  - Run hook install (merging into `~/.codex/hooks.json`, hook script bundled in mthds npm package)
  - ~~Set `[features] codex_hooks = true` if still required at the user's Codex version~~ (not required at 0.124.0+; default-enabled)
- [ ] When shipped, delete `bin/install-codex.sh` entirely, even before 2B lands.

---

## Out of scope

- **Personal marketplace at `~/.agents/plugins/`** (#16500): investigation showed Codex's user-plugin location is `$CODEX_HOME/plugins/cache/...`, and `~/.agents/plugins/` is not auto-discovered as a personal marketplace. Our path forward is `codex plugin marketplace add <local-or-remote>` — already canonical.
- **`mthds-env-check` binary**: keep at `~/.codex/bin/mthds-env-check`. SKILL.md preambles invoke it.
- **Claude Code plugin**: no changes needed; already at parity.

---

## Verification matrix (1A findings, recorded 2026-04-28)

| Check                                                       | Expected                                  | Actual                                                                                                                              | Source                                                            |
| ----------------------------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `codex --version`                                           | ≥ 0.124.0                                 | 0.125.0 ✓                                                                                                                           | `codex --version` on dev machine                                  |
| PostToolUse fires for apply_patch                           | yes                                       | yes — `ApplyPatchHandler::post_tool_use_payload` returns a payload                                                                  | `codex-rs/core/src/tools/handlers/apply_patch.rs:324-339`         |
| Stdin payload field for path                                | record exact field                        | `tool_input.command` is the **raw apply_patch envelope** (string with `*** Update File:` / `*** Add File:` / `*** Move to:` lines) | `apply_patch.rs:330-336` + `apply_patch_payload_command:251-259`  |
| Canonical `tool_name`                                       | `apply_patch`                             | `apply_patch` ✓ (with `Write`, `Edit` accepted as matcher aliases)                                                                  | `codex-rs/core/src/tools/hook_names.rs:34-39`                     |
| `[features] codex_hooks` still required                     | ?                                         | **NO** — `Stage::Stable, default_enabled: true`. Drop `enable_hooks_feature` from install script.                                   | `codex-rs/features/src/lib.rs:765-770`                            |
| Stage 3 (`mthds-agent validate bundle`) works in sandbox    | ?                                         | not verified live (deferred). Conservative: keep Stage 3 disabled, leave Phase 2D task open for offline mode in mthds-js.            | n/a                                                               |
| `.agents/plugins/marketplace.json` discovery precedence     | known (vs `.claude-plugin/marketplace.json`) | `.agents/plugins/...` checked FIRST — Codex picks one (no merge), so a Codex marketplace at `.agents/plugins/...` shadows `.claude-plugin/...` cleanly. | `codex-rs/core-plugins/src/marketplace.rs:20-23,237-247`          |
| `codex plugin marketplace add` accepts owner/repo + path    | yes                                       | yes — `<SOURCE>` accepts `owner/repo[@ref]`, HTTP(S) Git URLs, SSH URLs, or local marketplace root dirs                              | `codex plugin marketplace add --help`                             |
| Top-level `codex marketplace add` rejected                  | yes                                       | yes — `error: unrecognized subcommand 'add'`                                                                                         | `codex marketplace add` (run on dev machine)                      |
| Plugin manifest `hooks` field deserialized                  | NO                                        | **NO** — `RawPluginManifest` has only `name|version|description|skills|mcp_servers|apps|interface`. Phase 2A still required.        | `codex-rs/core-plugins/src/manifest.rs:11-30`                     |
| Multi-file apply_patch — one hook fire or many              | record                                    | **one hook fire per `apply_patch` call**, even for multi-file patches — handler returns a single payload with the full envelope     | `apply_patch.rs:324-339`                                          |
| `mthds-agent codex install-hook` writes Stop entry          | (regression risk)                         | confirmed — hardcodes `hooks.Stop[]`. Must NOT be called after 1B switch; install-codex.sh now does its own PostToolUse JSON merge.  | `mthds-js/src/agent/commands/codex.ts:55-65,153-170`              |

---

## Rollout order

1. 1A (verification — sets parameters for everything else)
2. 1B + 1C in parallel (hooks + marketplace file — independent)
3. 1D (slim install script — depends on 1C)
4. 1F + 1G (docs + tests — depend on 1B/1D)
5. 1E (README — depends on whether 1D's stretch goal lands)
6. 1H (version bump)
7. Tag release, comment on tracked issues (start of 2E)
