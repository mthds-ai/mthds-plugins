# Multi-Target Build System

The plugin uses a multi-target build system to produce multiple Claude Code plugins from the same set of Jinja2 templates. Each target is a separate plugin in the marketplace, with its own name, version, template variables, and optional skill subset.

## How it works

```
templates/                      source of truth (all .j2 files)
├── skills/*/SKILL.md.j2        skill templates
├── skills/shared/*.md.j2       shared includes + runtime refs
└── hooks/*.j2                  hook templates
       |
       v
targets/defaults.toml          common variable defaults
       |
       v
targets/<name>.toml             per-target plugin identity + variable overrides + skill filter
       |
       v
scripts/gen_skill_docs.py       renders .j2 templates with merged variables
       |
       +---> mthds/skills/*/SKILL.md                   (prod target, output)
       +---> mthds/skills/shared/*.md                  (prod target, output)
       +---> mthds/hooks/*                             (prod target, output)
       +---> mthds/.claude-plugin/plugin.json          (generated: plugin-base.json + target overrides)
       +---> mthds-dev/skills/*/SKILL.md               (dev target, output)
       +---> mthds-dev/skills/shared/*.md              (dev target, output)
       +---> mthds-dev/hooks/*                         (dev target, output)
       +---> mthds-dev/.claude-plugin/plugin.json      (generated: plugin-base.json + target overrides)
```

## Template vs output directories

**`templates/`** contains all `.j2` source files. Never edit files in `mthds/` or `mthds-dev/` directly — they are generated output.

**`skills/`** at the root contains only static assets (`references/` subdirectories) that are symlinked by all targets. **`mthds/`** and **`mthds-dev/`** are generated output directories (build artifacts checked into git).

## Target configuration

### defaults.toml

Defines variables shared by all targets:

```toml
[vars]
min_mthds_version = "0.8.1"
marketplace_name = "mthds-plugins"

# Install/upgrade commands (prod defaults — registry packages)
mthds_install_cmd = "npm install -g mthds"
mthds_upgrade_cmd = "npm install -g mthds@latest"
pipelex_install_cmd = "uv tool install pipelex"
pipelex_upgrade_cmd = "uv tool install --upgrade pipelex"
plxt_install_cmd = "uv tool install pipelex-tools"
plxt_upgrade_cmd = "uv tool install --upgrade pipelex-tools"
```

### Per-target files (prod.toml, dev.toml, ...)

Each target defines plugin identity and can override any default variable:

```toml
[plugin]
name = "mthds-dev"
version = "0.1.0"
description = "Development build of MTHDS skills — for iteration and testing."
source = "mthds-dev/"     # output directory

[vars]
# Override install commands with local container paths for CCC testing.
mthds_install_cmd = "npm install -g /build-src/mthds-js/"
pipelex_install_cmd = "uv tool install /workspace/pipelex/"
plxt_install_cmd = "uv tool install /workspace/vscode-pipelex/"
# ... upgrade commands also overridden (see targets/dev.toml for full list)

[skills]
# Optional: build only a subset of skills. Omit for all skills.
# include = ["mthds-build", "mthds-check"]
```

### Variable resolution

Variables are resolved in this order (last wins):

1. `defaults.toml[vars]` — shared defaults
2. `<target>.toml[vars]` — per-target overrides
3. `plugin_name` — derived automatically from `[plugin].name`

All variables are available in all `.j2` templates as `{{ variable_name }}`.

## Output directories

Each target specifies a `source` directory where its output is written. Both targets produce a complete plugin directory:

```
mthds/                         (prod target)
├── .claude-plugin/
│   └── plugin.json           generated (inherits author/repo/license from plugin-base.json)
├── skills/
│   ├── mthds-build/
│   │   ├── SKILL.md           rendered with target's variables
│   │   └── references/ ->     symlink to ../../skills/mthds-build/references
│   ├── ...
│   └── shared/
│       ├── error-handling.md   rendered (all shared files are rendered per-target)
│       ├── preamble.md         rendered
│       └── ...
├── hooks/
│   ├── hooks.json             rendered
│   └── validate-mthds.sh      rendered (executable)
└── bin/ ->                    symlink to ../bin
```

Only `bin/` and `references/` are symlinked — everything else is rendered per-target with that target's variables.

## Per-target skill overlays

A skill can carry **target-only content** without touching its shared `SKILL.md.j2`. Drop a `SKILL.<target>.md.j2` file next to a skill's `SKILL.md.j2` (where `<target>` is the stem of the target's `.toml`, e.g. `sandbox` for `targets/sandbox.toml`). When that target is built, the overlay is rendered with the same variables and **appended** to the skill's output; every other target stays byte-identical because the shared template is never modified.

Overlays are append-only, so they add or override behavior (a later instruction in the rendered skill wins) but cannot delete earlier content. For removals, gate the shared template with a `{% if %}` on a target variable instead (see `env_check` / `can_run_methods`). Because overlays render in the same Jinja environment, they may use template variables and `{% include %}` shared partials.

Current overlays (all for the `mthds-sandbox` target — a locked-down, platform-driven build sandbox):

- **Workspace check (silent)** — `mthds-build`, `mthds-vibe`: after finishing, ensure the bundle lives under `mthds-wip/<bundle_dir>/`, moving it silently if not.
- **Method summary (on request only)** — `mthds-build`, `mthds-vibe`, `mthds-check`: after a successful build/validation the agent must not auto-emit a method walkthrough (pipeline-flow diagram + step breakdown) — the platform renders the method visually. It confirms in one line and surfaces any errors/warnings, producing the full summary only when the user explicitly asks.

The mechanism is implemented in `render_templates()` (`scripts/gen_skill_docs.py`, `target_name` parameter) and verified by `tests/unit/test_sandbox_overlay.py`.

## Commands

```bash
make build                   # build all targets
make gen-skill-docs          # build default target (prod)
make gen-skill-docs TARGET=dev   # build a specific target

# Validation
make check-shared            # shared repo checks + freshness + lint/type checks
make check-claude            # Claude marketplace checks
make check-codex             # Codex packaging checks
make check                   # aggregate target
```

The underlying script accepts:

```bash
python scripts/gen_skill_docs.py --target prod        # one target
python scripts/gen_skill_docs.py --target all         # all targets
python scripts/gen_skill_docs.py --target dev --check  # freshness check
```

## Adding a new target

1. Create `targets/<name>.toml` with `[plugin]` section (name, version, description, source)
2. Add the plugin to `.claude-plugin/marketplace.json` `plugins` array
3. Run `make build` — the output directory is created with rendered files and symlinks
4. Run `make check` — validates shared, Claude, and Codex consistency

## Version management

Each target has its own version in `targets/<name>.toml [plugin].version`.

- **Prod plugin version**: `targets/prod.toml` is the source of truth. The `mthds/.claude-plugin/plugin.json` is generated by the build.
- **Dev plugin version**: `targets/dev.toml` is the source of truth. The `mthds-dev/.claude-plugin/plugin.json` is generated by the build.
- **Marketplace version**: `.claude-plugin/marketplace.json metadata.version` is independent — bumped when any plugin is released.

`make check-claude` validates the Claude marketplace, including that `metadata.version`
does not lag behind the highest released Claude target version. `make check` aggregates
shared, Claude, and Codex validation.

## Template variables

Variables used in `.j2` templates:

| Variable | Defined in | Used in |
|----------|-----------|---------|
| `min_mthds_version` | `defaults.toml` | `frontmatter.md.j2`, `preamble.md.j2`, `mthds-agent-guide.md.j2`, `mthds-check/SKILL.md.j2` |
| `marketplace_name` | `defaults.toml` | `preamble.md.j2` (env-check script path) |
| `mthds_install_cmd` | `defaults.toml` | `preamble.md.j2`, `validate-mthds.sh.j2` |
| `mthds_upgrade_cmd` | `defaults.toml` | `preamble.md.j2`, `upgrade-flow.md.j2` |
| `pipelex_install_cmd` | `defaults.toml` | `error-handling.md.j2` |
| `pipelex_upgrade_cmd` | `defaults.toml` | `upgrade-flow.md.j2` |
| `plxt_install_cmd` | `defaults.toml` | `validate-mthds.sh.j2` |
| `plxt_upgrade_cmd` | `defaults.toml` | `upgrade-flow.md.j2` |
| `plugin_name` | Derived from `[plugin].name` | Available but not currently used in templates |

### Shared template files

All shared files in `templates/skills/shared/` are `.j2` templates listed in `SHARED_TEMPLATES` in `gen_skill_docs.py`. They are all rendered per-target and written to `skills/shared/`.

Some shared files serve a dual role — `frontmatter.md.j2` and `preamble.md.j2` are also included inline by skill templates via `{% include %}`. Jinja2 resolves variables in the including template's context.

Hook templates in `templates/hooks/` are rendered per-target and written to `hooks/`.
