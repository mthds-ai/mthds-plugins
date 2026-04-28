# Changelog

## [v0.9.0] - 2026-04-28

### Changed

- Codex hook switched from `Stop` to `PostToolUse(apply_patch)` for per-edit `.mthds` validation, matching the Claude Code semantics. Codex 0.124.0 fixed the upstream blocker (apply_patch now emits hook payloads).
- Codex install no longer needs the curl-pipe-bash plugin install path: `codex plugin marketplace add mthds-ai/mthds-plugins` (Codex 0.124.0+) handles plugin install via the marketplace. The repo now ships `.agents/plugins/marketplace.json` (generated, byte-identical to the canonical `packaging/codex-marketplace.json`) so `codex plugin marketplace add` resolves cleanly.
- `bin/install-codex.sh` slimmed down — only wires the hook and copies the env-check helper. Plugin file copy, marketplace rendering, GitHub-clone fallback, and the `codex_hooks` feature toggle are gone (the toggle is default-enabled in Codex now).
- Codex hook script no longer parses the session transcript; it now reads the apply_patch envelope from `tool_input.command` directly.

### Migration

- Pre-existing installs have a `Stop` hook entry pointing at `codex-validate-mthds.sh` in `~/.codex/hooks.json`. Re-running `bin/install-codex.sh` automatically removes the stale `Stop` entry and writes the new `PostToolUse(apply_patch)` entry.

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
