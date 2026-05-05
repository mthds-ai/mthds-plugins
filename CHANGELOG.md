# Changelog

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
