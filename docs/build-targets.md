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
       +---> skills/*/SKILL.md                         (prod target, output)
       +---> skills/shared/*.md                        (prod target, output)
       +---> hooks/*                                   (prod target, output)
       +---> mthds-dev/skills/*/SKILL.md               (dev target, output)
       +---> mthds-dev/skills/shared/*.md               (dev target, output)
       +---> mthds-dev/hooks/*                          (dev target, output)
       +---> mthds-dev/.claude-plugin/plugin.json       (generated: root plugin.json + target overrides)
```

## Template vs output directories

**`templates/`** contains all `.j2` source files. Never edit files in `skills/` or `hooks/` directly — they are generated output.

**`skills/`** and **`hooks/`** contain generated output (build artifacts checked into git). The only non-generated content in `skills/` is the `references/` subdirectories which contain static reference docs.

## Target configuration

### defaults.toml

Defines variables shared by all targets:

```toml
[vars]
min_mthds_version = "0.3.3"
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
source = "mthds-dev/"     # output directory (use "./" for in-place)

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

**Root target** (source = `"./"`) writes output directly to `skills/`, `hooks/`, etc.

**Non-root targets** (e.g. source = `"mthds-dev/"`) create a complete plugin directory:

```
mthds-dev/
├── .claude-plugin/
│   └── plugin.json           generated (inherits author/repo/license from root plugin.json)
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

## Commands

```bash
make build                   # build all targets
make gen-skill-docs          # build default target (prod)
make gen-skill-docs TARGET=dev   # build a specific target

# Freshness checks
make check                   # runs check.py + freshness check for all targets
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
4. Run `make check` — validates consistency

## Version management

Each target has its own version in `targets/<name>.toml [plugin].version`.

- **Prod plugin version**: `targets/prod.toml` is the source of truth. Must match `.claude-plugin/plugin.json`.
- **Dev plugin version**: `targets/dev.toml` is the source of truth. The dev `plugin.json` is generated by the build.
- **Marketplace version**: `.claude-plugin/marketplace.json metadata.version` is independent — bumped when any plugin is released.

`make check` validates all of these are consistent.

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
