#!/usr/bin/env python3
"""Generate SKILL.md from SKILL.md.j2 templates, with multi-target support.

Renders all Jinja2 templates under skills/ and writes the corresponding
SKILL.md files. Both .j2 (source of truth) and .md (build artifact) are
checked into git.

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

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"

# Shared template files that are rendered per target (contain {{ }} variables
# but are not {% include %}-ed — they are read at runtime by Claude via links).
SHARED_TEMPLATES = ["shared/mthds-agent-guide.md.j2"]


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
    skills_dir: Path,
    template_vars: dict[str, str],
    include_skills: list[str] | None = None,
) -> dict[Path, str]:
    """Render all .j2 templates and return {output_path: rendered_content}.

    Args:
        skills_dir: Path to the skills/ directory containing templates.
        template_vars: Variables to inject into all templates.
        include_skills: If set, only render templates in these skill directories.

    Raises:
        SystemExit: On missing include files or template syntax errors.
    """
    if not skills_dir.is_dir():
        msg = f"Skills directory not found: {skills_dir}"
        raise SystemExit(msg)

    env = Environment(
        loader=FileSystemLoader(str(skills_dir)),
        keep_trailing_newline=True,
    )

    # Collect skill templates
    j2_paths = sorted(skills_dir.glob("*/SKILL.md.j2"))
    if include_skills is not None:
        j2_paths = [path for path in j2_paths if path.parent.name in include_skills]

    # Also collect shared templates (e.g. mthds-agent-guide.md.j2)
    shared_j2_paths = [skills_dir / template_name for template_name in SHARED_TEMPLATES if (skills_dir / template_name).is_file()]

    all_j2_paths = j2_paths + shared_j2_paths
    if not all_j2_paths:
        return {}

    results: dict[Path, str] = {}
    for j2_path in all_j2_paths:
        template_name = j2_path.relative_to(skills_dir).as_posix()
        try:
            template = env.get_template(template_name)
            rendered = template.render(**template_vars)
        except TemplateNotFound as exc:
            msg = f"{template_name}: include file not found: {exc.name}"
            raise SystemExit(msg) from exc
        except TemplateSyntaxError as exc:
            msg = f"{template_name}: syntax error at line {exc.lineno}: {exc.message}"
            raise SystemExit(msg) from exc
        output_path = j2_path.with_suffix("")  # .md.j2 -> .md
        results[output_path] = rendered

    return results


def make_plugin_json(base_dir: Path, config: TargetConfig) -> dict[str, object]:
    """Create a plugin.json dict by overlaying target-specific fields on the root plugin.json.

    Uses the root .claude-plugin/plugin.json as a base template so shared fields
    (author, repository, license) stay in sync without duplication.
    """
    root_plugin_path = base_dir / ".claude-plugin" / "plugin.json"
    base: dict[str, object] = json.loads(root_plugin_path.read_text(encoding="utf-8"))
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


def setup_symlinks(base_dir: Path, output_dir: Path, skills_dir: Path, include_skills: list[str] | None) -> None:
    """Create symlinks in the output directory for shared assets.

    For non-root targets, symlinks point back to the source-of-truth files.
    The shared/ directory is a real directory (not a symlink) because it
    contains a mix of generated files and symlinks to non-template originals.
    """
    # Symlink top-level directories
    for dirname in ["hooks", "bin"]:
        src = base_dir / dirname
        dst = output_dir / dirname
        if src.is_dir() and not dst.exists():
            dst.symlink_to(_relative_symlink_target(dst, src))

    # Determine which skills to link
    if include_skills is not None:
        skill_names = include_skills
    else:
        skill_names = sorted(path.parent.name for path in skills_dir.glob("*/SKILL.md.j2"))

    output_skills_dir = output_dir / "skills"
    output_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create shared/ as a real directory with symlinks to non-template files.
    # Template-generated files (e.g. mthds-agent-guide.md) are written directly
    # by the build step, not symlinked.
    shared_src = skills_dir / "shared"
    shared_dst = output_skills_dir / "shared"
    shared_dst.mkdir(parents=True, exist_ok=True)
    shared_template_outputs = {Path(template_name).with_suffix("").name for template_name in SHARED_TEMPLATES}
    if shared_src.is_dir():
        for src_file in sorted(shared_src.iterdir()):
            # Skip .j2 templates (their output is written by the build)
            if src_file.suffix == ".j2":
                continue
            # Skip files that are generated from templates
            if src_file.name in shared_template_outputs:
                continue
            dst_file = shared_dst / src_file.name
            if not dst_file.exists():
                dst_file.symlink_to(_relative_symlink_target(dst_file, src_file))

    # Create skill subdirectories and symlink references/
    for skill_name in skill_names:
        skill_output = output_skills_dir / skill_name
        skill_output.mkdir(parents=True, exist_ok=True)
        refs_src = skills_dir / skill_name / "references"
        refs_dst = skill_output / "references"
        if refs_src.is_dir() and not refs_dst.exists():
            refs_dst.symlink_to(_relative_symlink_target(refs_dst, refs_src))


def build_target(base_dir: Path, config: TargetConfig) -> BuildResult:
    """Build a single target: render templates, set up output directory."""
    skills_dir = base_dir / "skills"
    output_dir = resolve_output_dir(base_dir, config.source)
    is_root = config.is_root

    result = BuildResult()

    # Render templates
    rendered = render_templates(skills_dir, config.template_vars, config.include_skills)
    if not rendered:
        return result

    if is_root:
        # Root target: write in place
        result.files = rendered
    else:
        # Non-root target: write to output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        setup_symlinks(base_dir, output_dir, skills_dir, config.include_skills)

        output_skills_dir = output_dir / "skills"
        for src_path, content in rendered.items():
            # Map source path to output path
            rel = src_path.relative_to(skills_dir)
            dst_path = output_skills_dir / rel
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            result.files[dst_path] = content

        # Generate plugin.json
        plugin_json = make_plugin_json(base_dir, config)
        result.plugin_json = plugin_json
        plugin_dir = output_dir / ".claude-plugin"
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
            output_path.write_text(content, encoding="utf-8")
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
    skills_dir = base_dir / "skills"

    if target_name == "all":
        target_names = list_targets(targets_dir)
    else:
        target_names = [target_name]

    defaults = load_defaults(targets_dir)
    all_stale: list[str] = []

    for name in target_names:
        config = load_target_config(targets_dir, name, defaults)
        result = build_target(base_dir, config)

        if not result.files:
            all_stale.append(f"  [{name}] No templates found.")
            continue

        for output_path, rendered in result.files.items():
            rel = output_path.relative_to(base_dir)
            if not output_path.is_file():
                all_stale.append(f"  MISSING: {rel}")
            elif output_path.read_text(encoding="utf-8") != rendered:
                all_stale.append(f"  STALE: {rel}")

        # Detect orphaned .md files (only for root target)
        if config.is_root:
            rendered_parents = {path.parent for path in result.files if path.parent.parent == skills_dir}
            for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
                if skill_md.parent not in rendered_parents:
                    rel = skill_md.relative_to(base_dir)
                    all_stale.append(f"  ORPHAN: {rel} (no corresponding .j2 template)")

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
