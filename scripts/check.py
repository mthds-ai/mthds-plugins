#!/usr/bin/env python3
"""Validate shared references, shared files, and version consistency across skills and targets."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

# Derive the shared template file list from gen_skill_docs.py (single source of truth).
# SHARED_TEMPLATES contains full relative paths like "skills/shared/error-handling.md.j2".
# We extract just the filenames for the existence check.
from scripts.gen_skill_docs import SHARED_TEMPLATES

SHARED_TEMPLATE_FILES = [Path(template_path).name for template_path in SHARED_TEMPLATES]

# Stale reference patterns — shared file stems that should use ../shared/ not references/
STALE_REF_PATTERN = re.compile(
    r"references/(?:error-handling|frontmatter|mthds-agent-guide|mthds-reference|native-content-types|preamble|upgrade-flow)"
)

# Frontmatter extraction: min_mthds_version value between --- delimiters
FRONTMATTER_VERSION_PATTERN = re.compile(r"^min_mthds_version:\s*(.+)$", re.MULTILINE)

# Stale install patterns — toolchain install instructions that should have been replaced
# by mthds-agent-based install commands. Excludes legitimate Python library deps
# (e.g. `pip install python-docx` in code examples).
STALE_INSTALL_PATTERNS = [
    re.compile(r"pip install\s+pipelex(?!-)"),
    re.compile(r"pip install\s+pipelex-tools\b"),
    re.compile(r"curl.*install\.sh"),
]

TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"


def _read_json_string(path: Path, *keys: str) -> str:
    """Read a nested key from a JSON file, raising ValueError on any problem."""
    rel = path.name
    if not path.is_file():
        msg = f"{rel} not found"
        raise ValueError(msg)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{rel} is not valid JSON"
        raise ValueError(msg) from exc
    value: Any = raw
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            msg = f"{rel} missing key: {'.'.join(keys)}"
            raise ValueError(msg)
        value = cast(dict[str, Any], value)[key]
    if not isinstance(value, str):
        msg = f"{rel} key '{'.'.join(keys)}' is not a string"
        raise ValueError(msg)
    return value


def load_target_configs(base_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all target configs from targets/ directory.

    Returns a dict mapping target name to its parsed TOML content.
    """
    targets_dir = base_dir / TARGETS_DIR_NAME
    if not targets_dir.is_dir():
        msg = f"Targets directory not found: {targets_dir}"
        raise ValueError(msg)

    configs: dict[str, dict[str, Any]] = {}
    for toml_path in sorted(targets_dir.glob("*.toml")):
        if toml_path.name == DEFAULTS_FILE:
            continue
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        configs[toml_path.stem] = raw
    return configs


def load_defaults_vars(base_dir: Path) -> dict[str, str]:
    """Load default template variables from defaults.toml."""
    defaults_path = base_dir / TARGETS_DIR_NAME / DEFAULTS_FILE
    if not defaults_path.is_file():
        msg = f"Defaults file not found: {defaults_path}"
        raise ValueError(msg)
    raw = tomllib.loads(defaults_path.read_text(encoding="utf-8"))
    defaults: dict[str, str] = {}
    if "vars" in raw:
        for key, value in raw["vars"].items():
            defaults[key] = str(value)
    return defaults


def resolve_target_var(base_dir: Path, target_name: str, var_name: str) -> str:
    """Resolve a template variable for a target (target override > default)."""
    defaults = load_defaults_vars(base_dir)
    configs = load_target_configs(base_dir)
    if target_name not in configs:
        msg = f"Target '{target_name}' not found in targets/"
        raise ValueError(msg)
    target_vars = configs[target_name].get("vars", {})
    value = target_vars.get(var_name, defaults.get(var_name))
    if value is None:
        msg = f"Variable '{var_name}' not defined for target '{target_name}'"
        raise ValueError(msg)
    return str(value)


def check_target_plugin_versions(base_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Check that each target's plugin.json version matches its target config.

    For root targets (source="./"): checks .claude-plugin/plugin.json.
    For non-root targets: checks <source>/.claude-plugin/plugin.json.

    Returns:
        A tuple of (errors, {target_name: version}).
    """
    configs = load_target_configs(base_dir)
    errors: list[str] = []
    versions: dict[str, str] = {}

    for target_name, config in configs.items():
        plugin_section = config.get("plugin", {})
        config_version = plugin_section.get("version", "")
        source = plugin_section.get("source", "./")
        plugin_name = plugin_section.get("name", target_name)

        if source == "./":
            plugin_json_path = base_dir / ".claude-plugin" / "plugin.json"
        else:
            plugin_json_path = base_dir / source.rstrip("/") / ".claude-plugin" / "plugin.json"

        if not plugin_json_path.is_file():
            errors.append(f"[{target_name}] plugin.json not found at {plugin_json_path.relative_to(base_dir)}")
            continue

        try:
            actual_version = _read_json_string(plugin_json_path, "version")
        except ValueError as exc:
            errors.append(f"[{target_name}] {exc}")
            continue

        versions[target_name] = actual_version

        if actual_version != config_version:
            errors.append(f"[{target_name}] plugin.json has {actual_version}, targets/{target_name}.toml has {config_version}")

        # Also verify plugin name matches
        try:
            actual_name = _read_json_string(plugin_json_path, "name")
        except ValueError as exc:
            errors.append(f"[{target_name}] Cannot read plugin name: {exc}")
            continue
        if actual_name != plugin_name:
            errors.append(f"[{target_name}] plugin.json name is '{actual_name}', targets/{target_name}.toml has '{plugin_name}'")

    return errors, versions


def check_marketplace_plugins(base_dir: Path) -> list[str]:
    """Check that marketplace.json plugins array matches target configs."""
    marketplace_path = base_dir / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        return ["marketplace.json not found"]

    try:
        raw = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["marketplace.json is not valid JSON"]

    plugins = raw.get("plugins", [])
    marketplace_names = {plugin["name"] for plugin in plugins if "name" in plugin}

    configs = load_target_configs(base_dir)
    config_names = {config.get("plugin", {}).get("name", name) for name, config in configs.items()}

    errors: list[str] = []
    for idx, plugin in enumerate(plugins):
        if "name" not in plugin:
            errors.append(f"marketplace.json plugins[{idx}] is missing 'name' key")
    for name in config_names - marketplace_names:
        errors.append(f"Target plugin '{name}' missing from marketplace.json plugins array")
    for name in marketplace_names - config_names:
        errors.append(f"marketplace.json lists plugin '{name}' with no matching target config")

    return errors


def _collect_output_dirs(base_dir: Path) -> list[Path]:
    """Collect output directories from all configured targets."""
    try:
        configs = load_target_configs(base_dir)
    except ValueError:
        return [base_dir]
    output_dirs: list[Path] = []
    for _target_name, config in configs.items():
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            output_dirs.append(base_dir)
        else:
            output_dirs.append(base_dir / source.rstrip("/"))
    return output_dirs


def check_stale_install_references(base_dir: Path) -> list[str]:
    """Check for stale pip install / curl install references in generated SKILL.md files.

    These patterns indicate toolchain install instructions that should use
    mthds-agent-based install commands instead.
    """
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for line_num, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                for pattern in STALE_INSTALL_PATTERNS:
                    if pattern.search(line):
                        rel = skill_md.relative_to(base_dir)
                        errors.append(f"{rel}:{line_num}: stale install reference: {line.strip()}")
                        break
    return errors


def check_stale_references(base_dir: Path) -> list[str]:
    """Check: No SKILL.md files should reference shared files via references/ paths."""
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for idx, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                if STALE_REF_PATTERN.search(line):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"{rel}:{idx}: stale references/ path (should use ../shared/)")
    return errors


def check_shared_files_exist(base_dir: Path) -> list[str]:
    """Check: All expected shared template source files must be present in templates/."""
    shared_dir = base_dir / "templates" / "skills" / "shared"
    errors: list[str] = []
    for name in SHARED_TEMPLATE_FILES:
        if not (shared_dir / name).is_file():
            errors.append(f"MISSING: templates/skills/shared/{name}")
    return errors


def check_no_templates_in_output(base_dir: Path) -> list[str]:
    """Check: No .j2 files should exist in output directories (they belong in templates/).

    Scans root skills/ and hooks/ (for static assets), plus all target output directories.
    """
    errors: list[str] = []

    def _scan_dir(directory: Path) -> None:
        if directory.is_dir():
            for j2_file in sorted(directory.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                errors.append(f"LEAKED TEMPLATE: {rel} (should be in templates/)")

    # Scan root static asset directories
    _scan_dir(base_dir / "skills")
    _scan_dir(base_dir / "hooks")

    # Scan all target output directories
    for output_dir in _collect_output_dirs(base_dir):
        if output_dir == base_dir:
            continue  # Already scanned root above
        _scan_dir(output_dir / "skills")
        _scan_dir(output_dir / "hooks")

    return errors


def _resolve_target_output_dir(base_dir: Path, target_name: str) -> Path:
    """Resolve the output directory for a specific target."""
    configs = load_target_configs(base_dir)
    if target_name not in configs:
        msg = f"Target '{target_name}' not found in targets/"
        raise ValueError(msg)
    source: str = configs[target_name].get("plugin", {}).get("source", "./")
    if source == "./":
        return base_dir
    return base_dir / source.rstrip("/")


def check_frontmatter_versions(base_dir: Path, canonical: str, target_name: str) -> list[str]:
    """Check: SKILL.md frontmatter min_mthds_version must match canonical.

    Scans only the specified target's output directory for SKILL.md files.
    Dev targets may intentionally override min_mthds_version, so only prod
    is validated by default.
    """
    errors: list[str] = []
    output_dir = _resolve_target_output_dir(base_dir, target_name)

    for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        rel = skill_md.relative_to(base_dir)

        # Extract frontmatter (between first two --- lines)
        parts = text.split("---", 2)
        if len(parts) < 3:
            errors.append(f"{rel}: no frontmatter found")
            continue

        frontmatter = parts[1]
        match = FRONTMATTER_VERSION_PATTERN.search(frontmatter)
        if not match:
            errors.append(f"{rel}: no min_mthds_version in frontmatter")
            continue

        version = match.group(1).strip()
        if version != canonical:
            errors.append(f"{rel}: has {version}, expected {canonical}")

    return errors


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent
    failed = False

    # Check 0: Target plugin versions (each target's plugin.json matches its config)
    print("Checking target plugin versions...")
    try:
        errors, versions = check_target_plugin_versions(base_dir)
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot read target configs.")
        return 1
    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print("FAIL: Target plugin versions are inconsistent.")
        failed = True
    else:
        for target_name, version in versions.items():
            print(f"  [{target_name}] version: {version}")
        print("  All target plugin versions consistent.")

    # Check 0b: Marketplace plugins match target configs
    print("Checking marketplace plugin entries...")
    errors = check_marketplace_plugins(base_dir)
    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print("FAIL: marketplace.json plugins are inconsistent with target configs.")
        failed = True
    else:
        print("  Marketplace plugins match target configs.")

    # Check 1a: stale install references (pip install pipelex, curl install.sh)
    print("Checking for stale install references in SKILL.md files...")
    errors = check_stale_install_references(base_dir)
    if errors:
        for error in errors:
            print(f"  {error}")
        print("FAIL: Found stale install references (should use mthds-agent install commands).")
        failed = True
    else:
        print("  No stale install references found.")

    # Check 1b: stale references/ paths
    print("Checking for stale references/ paths to shared files...")
    errors = check_stale_references(base_dir)
    if errors:
        for error in errors:
            print(f"  {error}")
        print("FAIL: Found stale references/ paths (should use ../shared/ instead).")
        failed = True
    else:
        print("  No stale references found.")

    # Check 2: shared template source files exist
    print("Checking all shared template files exist...")
    errors = check_shared_files_exist(base_dir)
    if errors:
        for error in errors:
            print(f"  {error}")
        print("FAIL: Some shared template files are missing.")
        failed = True
    else:
        print("  All shared template files present.")

    # Check 2b: no .j2 files leaked into output directories
    print("Checking for leaked .j2 files in output directories...")
    errors = check_no_templates_in_output(base_dir)
    if errors:
        for error in errors:
            print(f"  {error}")
        print("FAIL: Found .j2 template files in output directories (should be in templates/).")
        failed = True
    else:
        print("  No leaked templates found.")

    # Check 3: frontmatter version consistency (per-target)
    print("Checking min_mthds_version consistency...")
    try:
        canonical = resolve_target_var(base_dir, "prod", "min_mthds_version")
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot determine canonical min_mthds_version.")
        return 1

    errors = check_frontmatter_versions(base_dir, canonical, "prod")
    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print(f"FAIL: Version inconsistency detected (canonical: {canonical}).")
        failed = True
    else:
        print("  All frontmatter versions consistent.")

    if failed:
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
