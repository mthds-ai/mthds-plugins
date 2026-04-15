#!/usr/bin/env python3
"""Validate shared references, generated artifacts, and marketplace consistency."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

from scripts.gen_skill_docs import SHARED_TEMPLATES, Platform

SHARED_TEMPLATE_FILES = [Path(template_path).name for template_path in SHARED_TEMPLATES]
_SHARED_STEMS = [Path(template_path).name.removesuffix(".md.j2") for template_path in SHARED_TEMPLATES]
STALE_REF_PATTERN = re.compile(r"references/(?:" + "|".join(re.escape(stem) for stem in _SHARED_STEMS) + r")")
FRONTMATTER_VERSION_PATTERN = re.compile(r"^min_mthds_version:\s*(.+)$", re.MULTILINE)
STALE_INSTALL_PATTERNS = [
    re.compile(r"pip install\s+pipelex(?!-)"),
    re.compile(r"pip install\s+pipelex-tools\b"),
    re.compile(r"curl.*install\.sh"),
]

TARGETS_DIR_NAME = "targets"
DEFAULTS_FILE = "defaults.toml"
CLAUDE_MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")
CODEX_MARKETPLACE_PATH = Path("packaging/codex-marketplace.json")


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


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted numeric version string into an ordered tuple."""
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        msg = f"invalid numeric version {version!r}"
        raise ValueError(msg) from exc


def load_target_configs(base_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all target configs from targets/ directory."""
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


def _platform_for_config(config: dict[str, Any], defaults: dict[str, str] | None = None) -> Platform:
    """Resolve a target platform from plugin, target vars, or defaults."""
    defaults = defaults or {}
    platform = config.get("plugin", {}).get(
        "platform",
        config.get("vars", {}).get("platform", defaults.get("platform", Platform.CLAUDE)),
    )
    return Platform(str(platform))


def check_matched_target_versions(base_dir: Path) -> list[str]:
    """Check that every target's ``[plugin].version`` is the same.

    Enforces the matched-version lockstep policy documented in
    ``.claude/skills/release/SKILL.md``: a release bumps all targets to the
    same version string, so drift between ``targets/*.toml`` is never valid.
    """
    configs = load_target_configs(base_dir)
    target_versions: dict[str, str] = {name: str(config.get("plugin", {}).get("version", "")) for name, config in configs.items()}
    unique_versions = set(target_versions.values())
    if len(unique_versions) <= 1:
        return []

    drift = ", ".join(f"{name}={version or '<missing>'}" for name, version in sorted(target_versions.items()))
    return [f"Target versions must be in lockstep: {drift}"]


def check_target_plugin_versions(base_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Check that each target's plugin.json version and name match its target config."""
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    errors: list[str] = []
    versions: dict[str, str] = {}

    for target_name, config in configs.items():
        plugin_section = config.get("plugin", {})
        config_version = plugin_section.get("version", "")
        source = plugin_section.get("source", "./")
        plugin_name = plugin_section.get("name", target_name)

        platform = _platform_for_config(config, defaults)
        manifest_dirname = ".codex-plugin" if platform == Platform.CODEX else ".claude-plugin"

        if source == "./":
            plugin_json_path = base_dir / manifest_dirname / "plugin.json"
        else:
            plugin_json_path = base_dir / str(source).rstrip("/") / manifest_dirname / "plugin.json"

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

        try:
            actual_name = _read_json_string(plugin_json_path, "name")
        except ValueError as exc:
            errors.append(f"[{target_name}] Cannot read plugin name: {exc}")
            continue

        if actual_name != plugin_name:
            errors.append(f"[{target_name}] plugin.json name is '{actual_name}', targets/{target_name}.toml has '{plugin_name}'")

    return errors, versions


def check_marketplace_plugins(base_dir: Path) -> list[str]:
    """Check that the Claude marketplace matches Claude targets and version rules."""
    marketplace_path = base_dir / CLAUDE_MARKETPLACE_PATH
    if not marketplace_path.is_file():
        return [f"{CLAUDE_MARKETPLACE_PATH} not found"]

    try:
        raw = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"{CLAUDE_MARKETPLACE_PATH} is not valid JSON"]

    plugins = raw.get("plugins", [])
    if not isinstance(plugins, list):
        return [f"{CLAUDE_MARKETPLACE_PATH} missing plugins array"]
    plugins_list = cast(list[object], plugins)

    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    claude_targets: dict[str, dict[str, str]] = {
        config.get("plugin", {}).get("name", name): {
            "version": str(config.get("plugin", {}).get("version", "")),
            "path": f"./{str(config.get('plugin', {}).get('source', './')).rstrip('/')}",
        }
        for name, config in configs.items()
        if _platform_for_config(config, defaults) != Platform.CODEX
    }
    marketplace_names: set[str] = set()
    for plugin in plugins_list:
        if isinstance(plugin, dict):
            plugin_dict = cast(dict[str, Any], plugin)
            name = plugin_dict.get("name")
            if isinstance(name, str):
                marketplace_names.add(name)

    errors: list[str] = []
    for idx, plugin in enumerate(plugins_list):
        if not isinstance(plugin, dict):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugins[{idx}] is not an object")
            continue
        plugin_dict = cast(dict[str, Any], plugin)

        name = plugin_dict.get("name")
        if not isinstance(name, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugins[{idx}] is missing 'name' key")
            continue

        source = plugin_dict.get("source")
        expected = claude_targets.get(name)
        if not isinstance(source, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugin '{name}' missing source string")
        elif expected and source != expected["path"]:
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} plugin '{name}' has source {source!r}, expected {expected['path']!r}")

    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"{CLAUDE_MARKETPLACE_PATH} missing metadata object")
    else:
        metadata_dict = cast(dict[str, Any], metadata)
        marketplace_version = metadata_dict.get("version")
        if not isinstance(marketplace_version, str):
            errors.append(f"{CLAUDE_MARKETPLACE_PATH} metadata.version missing or not a string")
        else:
            try:
                parsed_marketplace_version = _parse_version(marketplace_version)
            except ValueError as exc:
                errors.append(f"{CLAUDE_MARKETPLACE_PATH} metadata.version {exc}")
            else:
                try:
                    highest_target_version = max(_parse_version(target["version"]) for target in claude_targets.values() if target["version"])
                except ValueError as exc:
                    errors.append(f"Claude target version {exc}")
                else:
                    if parsed_marketplace_version < highest_target_version:
                        expected_floor = ".".join(str(part) for part in highest_target_version)
                        errors.append(
                            f"{CLAUDE_MARKETPLACE_PATH} metadata.version {marketplace_version!r} lags behind Claude target version {expected_floor!r}"
                        )

    for name in claude_targets.keys() - marketplace_names:
        errors.append(f"Claude target plugin '{name}' missing from {CLAUDE_MARKETPLACE_PATH} plugins array")
    for name in marketplace_names - claude_targets.keys():
        errors.append(f"{CLAUDE_MARKETPLACE_PATH} lists plugin '{name}' with no matching Claude target config")

    return errors


def check_codex_marketplace_plugins(base_dir: Path) -> list[str]:
    """Check that the tracked Codex packaging marketplace matches Codex targets and required fields.

    The canonical source.path here points at the build-output dir (e.g. ``./mthds-codex``),
    not the runtime on-disk path Codex actually reads (``./plugins/<name>``).
    ``bin/install-codex.sh`` rewrites the path at install time via ``render_repo_local_marketplace``.
    """
    marketplace_path = base_dir / CODEX_MARKETPLACE_PATH
    if not marketplace_path.is_file():
        return [f"{CODEX_MARKETPLACE_PATH} not found"]

    try:
        raw = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"{CODEX_MARKETPLACE_PATH} is not valid JSON"]

    plugins = raw.get("plugins", [])
    if not isinstance(plugins, list):
        return [f"{CODEX_MARKETPLACE_PATH} missing plugins array"]
    plugins_list = cast(list[object], plugins)

    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    codex_targets: dict[str, str] = {
        config.get("plugin", {}).get("name", name): f"./{str(config.get('plugin', {}).get('source', './')).rstrip('/')}"
        for name, config in configs.items()
        if _platform_for_config(config, defaults) == Platform.CODEX
    }

    marketplace_names: set[str] = set()
    for plugin in plugins_list:
        if isinstance(plugin, dict):
            plugin_dict = cast(dict[str, Any], plugin)
            name = plugin_dict.get("name")
            if isinstance(name, str):
                marketplace_names.add(name)
    errors: list[str] = []

    for idx, plugin in enumerate(plugins_list):
        if not isinstance(plugin, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugins[{idx}] is not an object")
            continue
        plugin_dict = cast(dict[str, Any], plugin)

        name = plugin_dict.get("name")
        if not isinstance(name, str):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugins[{idx}] is missing 'name' key")
            continue

        source = plugin_dict.get("source")
        if not isinstance(source, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing source object")
        else:
            source_dict = cast(dict[str, Any], source)
            if source_dict.get("source") != "local":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have source.source = 'local'")
            expected_path = codex_targets.get(name)
            source_path = source_dict.get("path")
            if expected_path and source_path != expected_path:
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' has path {source_path!r}, expected {expected_path!r}")

        policy = plugin_dict.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing policy object")
        else:
            policy_dict = cast(dict[str, Any], policy)
            if policy_dict.get("installation") != "AVAILABLE":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have policy.installation = 'AVAILABLE'")
            if policy_dict.get("authentication") != "ON_INSTALL":
                errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' must have policy.authentication = 'ON_INSTALL'")

        category = plugin_dict.get("category")
        if not isinstance(category, str) or not category:
            errors.append(f"{CODEX_MARKETPLACE_PATH} plugin '{name}' missing category")

    for name in codex_targets.keys() - marketplace_names:
        errors.append(f"Codex target plugin '{name}' missing from {CODEX_MARKETPLACE_PATH} plugins array")
    for name in marketplace_names - codex_targets.keys():
        errors.append(f"{CODEX_MARKETPLACE_PATH} lists plugin '{name}' with no matching Codex target config")

    return errors


def _collect_output_dirs(base_dir: Path) -> list[Path]:
    """Collect output directories from all configured targets."""
    configs = load_target_configs(base_dir)
    output_dirs: list[Path] = []
    for config in configs.values():
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            output_dirs.append(base_dir)
        else:
            output_dirs.append(base_dir / str(source).rstrip("/"))
    return output_dirs


def check_stale_install_references(base_dir: Path) -> list[str]:
    """Check for stale toolchain install references in generated SKILL.md files."""
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
    """Check that generated SKILL.md files do not reference shared files via references/."""
    errors: list[str] = []
    for output_dir in _collect_output_dirs(base_dir):
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            for idx, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
                if STALE_REF_PATTERN.search(line):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"{rel}:{idx}: stale references/ path (should use ../shared/)")
    return errors


def check_shared_files_exist(base_dir: Path) -> list[str]:
    """Check that all expected shared template source files are present."""
    shared_dir = base_dir / "templates" / "skills" / "shared"
    errors: list[str] = []
    for name in SHARED_TEMPLATE_FILES:
        if not (shared_dir / name).is_file():
            errors.append(f"MISSING: templates/skills/shared/{name}")
    return errors


def check_no_templates_in_output(base_dir: Path) -> list[str]:
    """Check that no .j2 files leaked into output directories."""
    errors: list[str] = []

    def _scan_dir(directory: Path) -> None:
        if directory.is_dir():
            for j2_file in sorted(directory.rglob("*.j2")):
                rel = j2_file.relative_to(base_dir)
                errors.append(f"LEAKED TEMPLATE: {rel} (should be in templates/)")

    _scan_dir(base_dir / "skills")
    _scan_dir(base_dir / "hooks")
    for output_dir in _collect_output_dirs(base_dir):
        if output_dir == base_dir:
            continue
        _scan_dir(output_dir / "skills")
        _scan_dir(output_dir / "hooks")

    return errors


def check_codex_no_claude_artifacts(base_dir: Path) -> list[str]:
    """Check that Codex output directories do not contain Claude-only artifacts."""
    errors: list[str] = []
    configs = load_target_configs(base_dir)
    defaults = load_defaults_vars(base_dir)
    for target_name, config in configs.items():
        if _platform_for_config(config, defaults) != Platform.CODEX:
            continue
        source = config.get("plugin", {}).get("source", "./")
        if source == "./":
            continue
        output_dir = base_dir / str(source).rstrip("/")
        claude_dir = output_dir / ".claude-plugin"
        if claude_dir.is_dir():
            errors.append(f"[{target_name}] .claude-plugin/ found in Codex output {source}")
        for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            frontmatter = parts[1] if len(parts) >= 3 else ""
            if "allowed-tools:" in frontmatter:
                rel = skill_md.relative_to(base_dir)
                errors.append(f"[{target_name}] {rel}: contains 'allowed-tools' (not supported in Codex)")
    return errors


def _resolve_target_output_dir(base_dir: Path, target_name: str) -> Path:
    """Resolve the output directory for a specific target."""
    configs = load_target_configs(base_dir)
    if target_name not in configs:
        msg = f"Target '{target_name}' not found in targets/"
        raise ValueError(msg)
    source = str(configs[target_name].get("plugin", {}).get("source", "./"))
    if source == "./":
        return base_dir
    return base_dir / source.rstrip("/")


def check_frontmatter_versions(base_dir: Path, canonical: str, target_name: str) -> list[str]:
    """Check that SKILL.md frontmatter min_mthds_version matches canonical."""
    errors: list[str] = []
    output_dir = _resolve_target_output_dir(base_dir, target_name)

    for skill_md in sorted(output_dir.glob("skills/*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        rel = skill_md.relative_to(base_dir)

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


def _run_check(title: str, errors: list[str], failure_message: str, success_message: str) -> bool:
    """Print a formatted check result and return whether it failed."""
    print(title)
    if errors:
        for error in errors:
            if error.startswith("MISSING:") or error.startswith("LEAKED TEMPLATE:"):
                print(f"  {error}")
            else:
                print(f"  MISMATCH: {error}")
        print(failure_message)
        return True

    print(success_message)
    return False


def run_shared_checks(base_dir: Path) -> bool:
    """Run platform-agnostic repository checks."""
    failed = False

    print("Checking target plugin versions...")
    try:
        errors, versions = check_target_plugin_versions(base_dir)
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot read target configs.")
        return True

    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print("FAIL: Target plugin versions are inconsistent.")
        failed = True
    else:
        for target_name, version in versions.items():
            print(f"  [{target_name}] version: {version}")
        print("  All target plugin versions consistent.")

    failed |= _run_check(
        "Checking target versions are in matched-version lockstep...",
        check_matched_target_versions(base_dir),
        "FAIL: Target versions have drifted — bump all of them together (see .claude/skills/release/SKILL.md).",
        "  All target versions match.",
    )

    failed |= _run_check(
        "Checking for stale install references in SKILL.md files...",
        check_stale_install_references(base_dir),
        "FAIL: Found stale install references (should use mthds-agent install commands).",
        "  No stale install references found.",
    )
    failed |= _run_check(
        "Checking for stale references/ paths to shared files...",
        check_stale_references(base_dir),
        "FAIL: Found stale references/ paths (should use ../shared/ instead).",
        "  No stale references found.",
    )
    failed |= _run_check(
        "Checking all shared template files exist...",
        check_shared_files_exist(base_dir),
        "FAIL: Some shared template files are missing.",
        "  All shared template files present.",
    )
    failed |= _run_check(
        "Checking for leaked .j2 files in output directories...",
        check_no_templates_in_output(base_dir),
        "FAIL: Found .j2 template files in output directories (should be in templates/).",
        "  No leaked templates found.",
    )

    try:
        canonical = resolve_target_var(base_dir, "prod", "min_mthds_version")
    except ValueError as exc:
        print("Checking min_mthds_version consistency...")
        print(f"  {exc}")
        print("FAIL: Cannot determine canonical min_mthds_version.")
        return True

    failed |= _run_check(
        "Checking prod frontmatter version consistency...",
        check_frontmatter_versions(base_dir, canonical, "prod"),
        f"FAIL: Version inconsistency detected (canonical: {canonical}).",
        "  All frontmatter versions consistent.",
    )

    return failed


def run_claude_checks(base_dir: Path) -> bool:
    """Run Claude-specific packaging checks."""
    return _run_check(
        "Checking Claude marketplace entries...",
        check_marketplace_plugins(base_dir),
        "FAIL: Claude marketplace entries are inconsistent with target configs.",
        "  Claude marketplace matches target configs.",
    )


def run_codex_checks(base_dir: Path) -> bool:
    """Run Codex-specific packaging and artifact checks."""
    failed = False
    failed |= _run_check(
        "Checking Codex packaging marketplace entries...",
        check_codex_marketplace_plugins(base_dir),
        "FAIL: Codex packaging marketplace entries are inconsistent with target configs.",
        "  Codex packaging marketplace matches target configs.",
    )
    failed |= _run_check(
        "Checking Codex targets for Claude artifacts...",
        check_codex_no_claude_artifacts(base_dir),
        "FAIL: Codex target contains Claude-specific artifacts.",
        "  No Claude artifacts in Codex targets.",
    )
    return failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("all", "shared", "claude", "codex"),
        default="all",
        help="Limit checks to a scope. Default: all.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_dir = Path(__file__).resolve().parent.parent

    failed = False
    if args.scope in {"all", "shared"}:
        failed |= run_shared_checks(base_dir)
    if args.scope in {"all", "claude"}:
        failed |= run_claude_checks(base_dir)
    if args.scope in {"all", "codex"}:
        failed |= run_codex_checks(base_dir)

    if failed:
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
