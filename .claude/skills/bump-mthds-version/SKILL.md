---
name: bump-mthds-version
description: >
  Update the minimum mthds-agent version required by all skills. Use when
  the user says "bump mthds version", "update min version", "raise minimum
  mthds version", "set mthds version to X.Y.Z", or any variation of changing
  the required CLI version across skills.
---

# Bump Minimum mthds-agent Version

This skill updates the `min_mthds_version` across all plugin skills in a single coordinated operation.

## Workflow

### 1. Determine the new version

Ask the user for the target version (semver `X.Y.Z`) unless they already specified it.

Show the current canonical version by reading line 3 of `skills/shared/mthds-agent-guide.md` — it contains `mthds-agent >= X.Y.Z`.

### 2. Update the canonical source

Edit `skills/shared/mthds-agent-guide.md` line 3. Replace both occurrences of the old version:

- `mthds-agent >= OLD` → `mthds-agent >= NEW`
- `` below `OLD` `` → `` below `NEW` ``

### 3. Update all SKILL.md.j2 templates

**Important**: The `.j2` templates are the source of truth. Never edit `SKILL.md` directly — those are generated build artifacts.

Read each `skills/*/SKILL.md.j2` file before editing it (the Edit tool requires a prior read).

For each file matching `skills/*/SKILL.md.j2`, update the frontmatter version:

- `min_mthds_version: OLD` → `min_mthds_version: NEW`

This is the only version string in each `.j2` template — the old body-text version patterns were replaced by `{% include 'shared/preamble.md' %}`.

### 4. Regenerate SKILL.md files

Run `make gen-skill-docs` from the repo root. This renders all `.j2` templates and writes the corresponding `SKILL.md` files.

### 5. Update the test constant

Edit `tests/unit/test_check.py` and replace the `CANONICAL = "OLD"` line with `CANONICAL = "NEW"` (using the actual old and new version strings). The test fixtures derive all version strings from this constant via f-strings, so updating it is sufficient.

### 6. Verify with grep

Run `grep -rc 'OLD' skills/*/SKILL.md.j2 skills/shared/mthds-agent-guide.md` (replacing `OLD` with the actual old version string). Every file must return `:0`. If any file still contains the old version, fix it before continuing.

### 7. Verify with `make check`

Run `make check` from the repo root. This validates shared refs, shared file existence, frontmatter version consistency, body-text version consistency, and template freshness (generated `.md` files match their `.j2` source). If it fails, report the errors and fix them before continuing.

### 8. Report

List all modified files and show the version change: `OLD → NEW`.
