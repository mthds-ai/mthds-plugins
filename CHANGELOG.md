# Changelog

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
