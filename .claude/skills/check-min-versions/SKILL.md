---
name: check-min-versions
description: >
  Report the minimum and configured versions currently set in this plugin
  repo — the canonical min_mthds_version plus any per-target overrides and the
  plugin/marketplace versions. Use when the user says "check min versions",
  "what's the minimum mthds version", "show configured versions", "what version
  is required", "are the versions consistent", or wants to see version config
  without changing it. Read-only — never edits files.
---

# Check Configured Versions

Report the minimum and configured versions across this plugin's build targets. This is a **read-only** inspection — never edit any file. To change the minimum version, the user wants `bump-mthds-version` instead.

## Sources of truth

- **`min_mthds_version`** — canonical in `targets/defaults.toml` under `[vars]`. Any target `.toml` may override it under its own `[vars]`; an override wins for that target only.
- **Plugin version** — each target's `[plugin].version` in `targets/prod.toml`, `targets/dev.toml`, `targets/codex.toml`.
- **Marketplace version** — `metadata.version` in `.claude-plugin/marketplace.json` (independent of plugin versions).

## Workflow

### 1. Read the canonical minimum

Read `targets/defaults.toml` and report `[vars].min_mthds_version`.

### 2. Check for per-target overrides

Read `targets/prod.toml`, `targets/dev.toml`, and `targets/codex.toml`. For each, look under `[vars]` for a `min_mthds_version` line. If present, it overrides the default for that target — flag it. If absent, the target inherits the canonical default.

### 3. Read the configured plugin and marketplace versions

Report each target's `[plugin].version` and the marketplace `metadata.version`.

### 4. Report

Present a compact summary, for example:

```
Minimum mthds-agent version (canonical): 0.10.0
  prod   → inherits default
  dev    → inherits default
  codex  → inherits default

Plugin versions:
  prod 0.13.0 · dev 0.13.0 · codex 0.13.0
Marketplace version: 0.13.0
```

Call out anything inconsistent — a target whose `min_mthds_version` override differs from the canonical default, or plugin/marketplace versions that have drifted apart when they were expected to match. Note that whether the generated `SKILL.md` artifacts actually carry the canonical value is verified by `make check`; mention it as the follow-up if the user wants to confirm freshness, but don't run it unless asked.
