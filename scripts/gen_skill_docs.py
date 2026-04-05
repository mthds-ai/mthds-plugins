#!/usr/bin/env python3
"""Generate skill docs, shared files, and hooks from Jinja2 templates.

Renders all .j2 templates under templates/ and writes the corresponding
output files (skills/, hooks/). Templates (.j2) are the source of truth;
output files are build artifacts checked into git.

Supports multiple build targets (e.g. prod, dev) defined in targets/*.toml.
Each target can override template variables, filter skills, and write output
to a different directory.

Usage:
    python scripts/gen_skill_docs.py                    # build prod target
    python scripts/gen_skill_docs.py --target prod      # build prod target
    python scripts/gen_skill_docs.py --target dev       # build dev target
    python scripts/gen_skill_docs.py --target all       # build all targets
    python scripts/gen_skill_docs.py --target prod --check  # verify freshness
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError

TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"
TEMPLATES_DIR_NAME = "templates"

# All shared files are templates rendered per target.
# Paths are relative to the templates/ directory.
SHARED_TEMPLATES = [
    "skills/shared/error-handling.md.j2",
    "skills/shared/frontmatter.md.j2",
    "skills/shared/mthds-agent-guide.md.j2",
    "skills/shared/mthds-reference.md.j2",
    "skills/shared/native-content-types.md.j2",
    "skills/shared/preamble.md.j2",
    "skills/shared/python-execution.md.j2",
    "skills/shared/upgrade-flow.md.j2",
]

# Hook templates rendered per target.
HOOK_TEMPLATES = [
    "hooks/hooks.json.j2",
    "hooks/validate-mthds.sh.j2",
]

# Files that should be made executable after rendering.
EXECUTABLE_OUTPUTS = {"validate-mthds.sh"}


@dataclass
class TargetConfig:
    """Parsed build target configuration."""

    name: str
    plugin_name: str
    plugin_version: str
    plugin_description: str
    source: str
    template_vars: dict[str, str]
    include_skills: list[str] | None = None

    @property
    def is_root(self) -> bool:
        """Whether this target writes output to the repo root."""
        return self.source == "./"


@dataclass
class BuildResult:
    """Result of rendering templates for a target."""

    files: dict[Path, str] = field(default_factory=lambda: {})
    plugin_json: dict[str, object] | None = None


def load_defaults(targets_dir: Path) -> dict[str, str]:
    """Load default template variables from defaults.toml."""
    defaults_path = targets_dir / DEFAULTS_FILE
    if not defaults_path.is_file():
        msg = f"Defaults file not found: {defaults_path}"
        raise SystemExit(msg)
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    defaults: dict[str, str] = {}
    if "vars" in raw:
        for key, value in raw["vars"].items():
            defaults[key] = str(value)
    return defaults


def load_target_config(targets_dir: Path, target_name: str, defaults: dict[str, str] | None = None) -> TargetConfig:
    """Load a target config, merging defaults with target-specific overrides.

    Args:
        targets_dir: Path to the targets/ directory.
        target_name: Name of the target (stem of the .toml file).
        defaults: Pre-loaded defaults to avoid re-reading defaults.toml.
            If None, defaults are loaded from disk.
    """
    target_path = targets_dir / f"{target_name}.toml"
    if not target_path.is_file():
        msg = f"Target config not found: {target_path}"
        raise SystemExit(msg)

    if defaults is None:
        defaults = load_defaults(targets_dir)
    raw = tomllib.loads(target_path.read_text(encoding="utf-8"))

    plugin = raw.get("plugin", {})
    if not plugin.get("name"):
        msg = f"{target_path.name}: [plugin].name is required"
        raise SystemExit(msg)

    # Merge template vars: defaults → target overrides → derived values
    template_vars = dict(defaults)
    if "vars" in raw:
        for key, value in raw["vars"].items():
            template_vars[key] = str(value)
    template_vars["plugin_name"] = plugin["name"]

    include_skills: list[str] | None = None
    skills_section = raw.get("skills", {})
    if "include" in skills_section:
        include_skills = list(skills_section["include"])

    return TargetConfig(
        name=target_name,
        plugin_name=plugin["name"],
        plugin_version=plugin.get("version", "0.0.0"),
        plugin_description=plugin.get("description", ""),
        source=plugin.get("source", "./"),
        template_vars=template_vars,
        include_skills=include_skills,
    )


def list_targets(targets_dir: Path) -> list[str]:
    """List all target names (excluding defaults.toml)."""
    if not targets_dir.is_dir():
        msg = f"Targets directory not found: {targets_dir}"
        raise SystemExit(msg)
    return sorted(path.stem for path in targets_dir.glob("*.toml") if path.name != DEFAULTS_FILE)


def resolve_output_dir(base_dir: Path, source: str) -> Path:
    """Resolve the output directory for a target."""
    if source == "./":
        return base_dir
    return base_dir / source.rstrip("/")


def render_templates(
    templates_dir: Path,
    base_dir: Path,
    template_vars: dict[str, str],
    include_skills: list[str] | None = None,
) -> dict[Path, str]:
    """Render all .j2 templates and return {output_path: rendered_content}.

    Templates live in templates/ and output goes to the repo root (skills/, hooks/).
    The output path is derived by stripping the templates/ prefix and removing the
    .j2 suffix.

    Args:
        templates_dir: Path to the templates/ directory (Jinja2 FileSystemLoader root).
        base_dir: Repository root — output paths are relative to this.
        template_vars: Variables to inject into all templates.
        include_skills: If set, only render skill templates in these directories.

    Raises:
        SystemExit: On missing include files or template syntax errors.
    """
    if not templates_dir.is_dir():
        msg = f"Templates directory not found: {templates_dir}"
        raise SystemExit(msg)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
    )

    # Collect shared templates (must all exist — fail loudly if missing)
    shared_j2_paths: list[Path] = []
    for name in SHARED_TEMPLATES:
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared shared template not found: {name}"
            raise SystemExit(msg)
        shared_j2_paths.append(path)

    # Collect hook templates (must all exist — fail loudly if missing)
    hook_j2_paths: list[Path] = []
    for name in HOOK_TEMPLATES:
        path = templates_dir / name
        if not path.is_file():
            msg = f"Declared hook template not found: {name}"
            raise SystemExit(msg)
        hook_j2_paths.append(path)

    # Collect skill templates (templates/skills/*/SKILL.md.j2)
    j2_paths = sorted(templates_dir.glob("skills/*/SKILL.md.j2"))
    if include_skills is not None:
        j2_paths = [path for path in j2_paths if path.parent.name in include_skills]

    all_j2_paths = j2_paths + shared_j2_paths + hook_j2_paths

    # No templates at all (no skills found and no shared/hook templates)
    if not all_j2_paths:
        return {}

    results: dict[Path, str] = {}
    for j2_path in all_j2_paths:
        template_name = j2_path.relative_to(templates_dir).as_posix()
        try:
            template = env.get_template(template_name)
            rendered = template.render(**template_vars)
        except TemplateNotFound as exc:
            msg = f"{template_name}: include file not found: {exc.name}"
            raise SystemExit(msg) from exc
        except TemplateSyntaxError as exc:
            msg = f"{template_name}: syntax error at line {exc.lineno}: {exc.message}"
            raise SystemExit(msg) from exc
        except UndefinedError as exc:
            msg = f"{template_name}: undefined variable: {exc.message} — add it to targets/defaults.toml or the target config"
            raise SystemExit(msg) from exc
        # Map template path to output path:
        # templates/skills/X/SKILL.md.j2 -> skills/X/SKILL.md
        # templates/hooks/X.sh.j2 -> hooks/X.sh
        output_rel = j2_path.relative_to(templates_dir).with_suffix("")  # strip .j2
        output_path = base_dir / output_rel
        results[output_path] = rendered

    return results


def make_plugin_json(base_dir: Path, config: TargetConfig) -> dict[str, object]:
    """Create a plugin.json dict by overlaying target-specific fields on the base template.

    Uses .claude-plugin/plugin-base.json for shared fields (author, repository, license)
    that stay in sync without duplication across targets.
    """
    base_plugin_path = base_dir / ".claude-plugin" / "plugin-base.json"
    base: dict[str, object] = json.loads(base_plugin_path.read_text(encoding="utf-8"))
    base["name"] = config.plugin_name
    base["description"] = config.plugin_description
    base["version"] = config.plugin_version
    return base


def _relative_symlink_target(link_location: Path, real_target: Path) -> Path:
    """Compute a relative path from link_location to real_target for use in symlinks.

    Both paths must be absolute or both relative to the same root.
    The result is suitable for ``link_location.symlink_to(result)``.
    """
    return Path(os.path.relpath(real_target, link_location.parent))


def setup_symlinks(base_dir: Path, output_dir: Path, templates_dir: Path, include_skills: list[str] | None) -> None:
    """Create symlinks in the output directory for static assets.

    For non-root targets, symlinks point back to the source-of-truth files.
    Only static assets (bin/, references/) are symlinked — skills/, shared/,
    and hooks/ are all generated per-target by the template renderer.
    """
    # Symlink bin/ (static, not a template)
    bin_src = base_dir / "bin"
    bin_dst = output_dir / "bin"
    if bin_src.is_dir() and not bin_dst.exists():
        bin_dst.symlink_to(_relative_symlink_target(bin_dst, bin_src))

    # Determine which skills to link
    if include_skills is not None:
        skill_names = include_skills
    else:
        skill_names = sorted(path.parent.name for path in templates_dir.glob("skills/*/SKILL.md.j2"))

    output_skills_dir = output_dir / "skills"
    output_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skill subdirectories and symlink references/ (static assets)
    skills_dir = base_dir / "skills"
    for skill_name in skill_names:
        skill_output = output_skills_dir / skill_name
        skill_output.mkdir(parents=True, exist_ok=True)
        refs_src = skills_dir / skill_name / "references"
        refs_dst = skill_output / "references"
        if refs_src.is_dir() and not refs_dst.exists():
            refs_dst.symlink_to(_relative_symlink_target(refs_dst, refs_src))


def build_target(base_dir: Path, config: TargetConfig, *, dry_run: bool = False) -> BuildResult:
    """Build a single target: render templates, set up output directory.

    Args:
        base_dir: Repository root.
        config: Target configuration.
        dry_run: If True, compute expected files without creating directories,
            symlinks, or writing anything to disk.
    """
    templates_dir = base_dir / TEMPLATES_DIR_NAME
    output_dir = resolve_output_dir(base_dir, config.source)
    is_root = config.is_root

    result = BuildResult()

    # Render templates — output paths are relative to base_dir
    rendered = render_templates(templates_dir, base_dir, config.template_vars, config.include_skills)
    if not rendered:
        return result

    if is_root:
        # Root target: write in place (output paths already point to base_dir/...)
        result.files = rendered
    else:
        # Non-root target: write to output directory
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            setup_symlinks(base_dir, output_dir, templates_dir, config.include_skills)

        for src_path, content in rendered.items():
            # Map base_dir-relative output to target output dir
            # e.g. base_dir/skills/X/SKILL.md -> output_dir/skills/X/SKILL.md
            # e.g. base_dir/hooks/validate-mthds.sh -> output_dir/hooks/validate-mthds.sh
            rel = src_path.relative_to(base_dir)
            dst_path = output_dir / rel
            if not dry_run:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
            result.files[dst_path] = content

        # Generate plugin.json
        plugin_json = make_plugin_json(base_dir, config)
        result.plugin_json = plugin_json
        plugin_dir = output_dir / ".claude-plugin"
        if not dry_run:
            plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_json_path = plugin_dir / "plugin.json"
        result.files[plugin_json_path] = json.dumps(plugin_json, indent=2) + "\n"

    return result


def generate(base_dir: Path, target_name: str = "prod") -> int:
    """Render templates and write output files for one or all targets."""
    targets_dir = base_dir / TARGETS_DIR_NAME

    if target_name == "all":
        target_names = list_targets(targets_dir)
    else:
        target_names = [target_name]

    defaults = load_defaults(targets_dir)

    total_files = 0
    for name in target_names:
        config = load_target_config(targets_dir, name, defaults)
        result = build_target(base_dir, config)

        if not result.files:
            print(f"  [{name}] No templates found.")
            continue

        for output_path, content in result.files.items():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            # Make hook scripts executable
            if output_path.name in EXECUTABLE_OUTPUTS:
                output_path.chmod(0o755)
            rel = output_path.relative_to(base_dir)
            print(f"  [{name}] Generated {rel}")

        file_count = len(result.files)
        total_files += file_count
        print(f"  [{name}] Generated {file_count} files.")

    if total_files == 0:
        print("No templates found.")
        return 1

    return 0


def check_freshness(base_dir: Path, target_name: str = "prod") -> int:
    """Verify that all generated files match their template output."""
    targets_dir = base_dir / TARGETS_DIR_NAME

    if target_name == "all":
        target_names = list_targets(targets_dir)
    else:
        target_names = [target_name]

    defaults = load_defaults(targets_dir)
    all_stale: list[str] = []

    for name in target_names:
        config = load_target_config(targets_dir, name, defaults)
        result = build_target(base_dir, config, dry_run=True)

        if not result.files:
            all_stale.append(f"  [{name}] No templates found.")
            continue

        for output_path, rendered in result.files.items():
            rel = output_path.relative_to(base_dir)
            if not output_path.is_file():
                all_stale.append(f"  MISSING: {rel}")
            elif output_path.read_text(encoding="utf-8") != rendered:
                all_stale.append(f"  STALE: {rel}")
            elif output_path.name in EXECUTABLE_OUTPUTS and not os.access(output_path, os.X_OK):
                all_stale.append(f"  NOT EXECUTABLE: {rel}")

        # Detect orphaned SKILL.md files with no corresponding template
        output_dir = resolve_output_dir(base_dir, config.source)
        output_skills_dir = output_dir / "skills"
        rendered_skill_parents = {path.parent for path in result.files if path.name == "SKILL.md"}
        if output_skills_dir.is_dir():
            for skill_md in sorted(output_skills_dir.glob("*/SKILL.md")):
                if skill_md.parent not in rendered_skill_parents:
                    rel = skill_md.relative_to(base_dir)
                    all_stale.append(f"  ORPHAN: {rel} (no corresponding .j2 template)")

        # Detect leaked .j2 files in output directories (should only be in templates/)
        if output_skills_dir.is_dir():
            for j2_file in sorted(output_skills_dir.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                all_stale.append(f"  LEAKED TEMPLATE: {rel} (should be in templates/)")
        output_hooks_dir = output_dir / "hooks"
        if output_hooks_dir.is_dir():
            for j2_file in sorted(output_hooks_dir.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                all_stale.append(f"  LEAKED TEMPLATE: {rel} (should be in templates/)")

    if all_stale:
        for msg in all_stale:
            print(msg)
        print("FAIL: Generated files are out of date. Run `make build` to regenerate.")
        return 1

    target_label = target_name if target_name != "all" else ", ".join(target_names)
    print(f"  All generated files are fresh (targets: {target_label}).")
    return 0


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent

    # Parse arguments
    args = sys.argv[1:]
    target_name = "prod"
    check_mode = False

    idx = 0
    while idx < len(args):
        if args[idx] == "--target" and idx + 1 < len(args):
            target_name = args[idx + 1]
            idx += 2
        elif args[idx] == "--check":
            check_mode = True
            idx += 1
        else:
            msg = f"Unknown argument: {args[idx]}"
            raise SystemExit(msg)

    if check_mode:
        return check_freshness(base_dir, target_name)
    return generate(base_dir, target_name)


if __name__ == "__main__":
    sys.exit(main())
