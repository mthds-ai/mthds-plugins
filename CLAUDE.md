# CLAUDE.md — mthds-plugins

Claude Code skills plugin for building, running, validating, and editing AI methods (.mthds bundles) using the `mthds-agent` CLI.

## Repository Structure

```
skills/
├── .claude-plugin/marketplace.json   # Plugin metadata (name, version, skill list)
├── hooks/
│   ├── hooks.json                    # PostToolUse hook config (fires on Write|Edit)
│   └── validate-mthds.sh            # Lint → format → validate .mthds files via mthds-agent
├── skills/
│   ├── mthds-build/                  # /mthds-build — create new .mthds bundles from scratch
│   │   ├── SKILL.md.j2              # Jinja2 template (source of truth)
│   │   ├── SKILL.md                 # Generated from .j2 (build artifact, checked in)
│   │   └── references/              # Skill-specific refs (build-phases, model-references)
│   ├── mthds-check/                  # /mthds-check — validate bundles (read-only)
│   ├── mthds-edit/                   # /mthds-edit — modify existing bundles
│   │   └── references/              # Skill-specific refs (model-references)
│   ├── mthds-explain/                # /mthds-explain — document and explain workflows
│   ├── mthds-fix/                    # /mthds-fix — auto-fix validation errors
│   ├── mthds-inputs/                 # /mthds-inputs — prepare inputs (templates, synthetic data)
│   ├── mthds-install/                # /mthds-install — install method packages
│   ├── mthds-pipelex-setup/          # /mthds-pipelex-setup — configure backends and API keys
│   ├── mthds-pkg/                    # /mthds-pkg — MTHDS package management (init, deps, lock)
│   ├── mthds-publish/                # /mthds-publish — publish methods to mthds.sh
│   ├── mthds-run/                    # /mthds-run — execute methods and interpret output
│   ├── mthds-share/                  # /mthds-share — share methods on social media
│   ├── mthds-upgrade/                # /mthds-upgrade — upgrade MTHDS CLI tools
│   └── shared/                       # Shared docs (linked via ../shared/ or included via Jinja2)
│       ├── error-handling.md
│       ├── mthds-agent-guide.md
│       ├── mthds-reference.md
│       ├── native-content-types.md
│       ├── preamble.md              # Step 0 environment check (included by all .j2 templates)
│       └── upgrade-flow.md          # Upgrade flow reference (read at runtime by Claude)
├── Makefile
└── README.md
```

Each skill directory contains a `SKILL.md.j2` (Jinja2 template, source of truth) and a `SKILL.md` (generated build artifact). Edit `.j2` files, then run `make gen-skill-docs` to regenerate. Shared docs in `skills/shared/` are included via `{% include 'shared/preamble.md' %}` in templates or linked via `../shared/` relative paths at runtime. Some skills (build, edit) also have a `references/` folder for skill-specific docs.

## Make Targets

```bash
make help            # Show available targets
make gen-skill-docs  # Generate SKILL.md from .j2 templates
make check           # Verify shared refs, version consistency, template freshness, format, lint, typecheck
make test            # Run unit tests (sets up venv via uv)
make env             # Create virtual environment
make install         # Install dev dependencies
```

**`make gen-skill-docs`** renders all `SKILL.md.j2` templates into `SKILL.md` files using Jinja2. Run this after editing any `.j2` template or shared include.

**`make check`** runs `scripts/check.py` (system `python3`) and `scripts/gen_skill_docs.py --check` (venv) and verifies that:
1. No SKILL.md files contain stale `references/` paths to shared files (should use `../shared/` instead).
2. All shared files exist in `skills/shared/`.
3. All `min_mthds_version` frontmatter values in SKILL.md files match the canonical version in `mthds-agent-guide.md`.
4. All generated SKILL.md files are fresh (match their `.j2` template output).

**`make test`** runs pytest against `tests/` using a uv-managed venv.

## PostToolUse Hook

`hooks/validate-mthds.sh` runs automatically after every Write or Edit on `.mthds` files. It:
1. Lints with `plxt lint` (blocks on errors)
2. Formats with `plxt fmt` (only if lint passes)
3. Validates semantically with `mthds-agent validate bundle` (blocks or warns)

Passes silently if `mthds-agent` is not installed or file is not `.mthds`.

## Prerequisites

The `mthds-agent` CLI must be on PATH. Install via: `npm install -g mthds`

## Key Dependency

This plugin calls `mthds-agent` (from the `mthds-js` repo). Changes to the `mthds-agent` CLI interface can break the hook and skill docs.
