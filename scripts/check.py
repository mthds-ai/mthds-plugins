#!/usr/bin/env python3
"""Validate shared references, shared files, and version consistency across skills."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, cast

# Shared files that must exist in skills/shared/
SHARED_FILES = [
    "error-handling.md",
    "mthds-agent-guide.md",
    "mthds-reference.md",
    "native-content-types.md",
    "preamble.md",
    "upgrade-flow.md",
]

# Pattern that extracts the canonical version from mthds-agent-guide.md
CANONICAL_VERSION_PATTERN = re.compile(r"mthds-agent >= (\d+\.\d+\.\d+)")

# Stale reference patterns — shared file stems that should use ../shared/ not references/
STALE_REF_PATTERN = re.compile(r"references/(?:error-handling|mthds-agent-guide|mthds-reference|native-content-types|preamble|upgrade-flow)")

# Frontmatter extraction: min_mthds_version value between --- delimiters
FRONTMATTER_VERSION_PATTERN = re.compile(r"^min_mthds_version:\s*(.+)$", re.MULTILINE)

SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+")

# Stale install patterns — toolchain install instructions that should have been replaced
# by mthds-agent-based install commands. Excludes legitimate Python library deps
# (e.g. `pip install python-docx` in code examples).
STALE_INSTALL_PATTERNS = [
    re.compile(r"pip install\s+pipelex(?!-)"),
    re.compile(r"pip install\s+pipelex-tools\b"),
    re.compile(r"curl.*install\.sh"),
]


def check_plugin_version_sync(base_dir: Path) -> tuple[list[str], str, str]:
    """Check that plugin.json and marketplace.json have the same version.

    Returns:
        A tuple of (errors, plugin_version, marketplace_version).

    Raises:
        ValueError: If either file is missing, malformed, or lacks the expected key.
    """
    plugin_path = base_dir / ".claude-plugin" / "plugin.json"
    marketplace_path = base_dir / ".claude-plugin" / "marketplace.json"

    plugin_version = _read_json_version(plugin_path, "version")
    marketplace_version = _read_json_version(marketplace_path, "metadata", "version")

    errors: list[str] = []
    if plugin_version != marketplace_version:
        errors.append(f"plugin.json has {plugin_version}, marketplace.json has {marketplace_version}")
    return errors, plugin_version, marketplace_version


def _read_json_version(path: Path, *keys: str) -> str:
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
        msg = f"{rel} version is not a string"
        raise ValueError(msg)
    return value


def check_stale_install_references(base_dir: Path) -> list[str]:
    """Check for stale pip install / curl install references in generated SKILL.md files.

    These patterns indicate toolchain install instructions that should use
    mthds-agent-based install commands instead.
    """
    errors: list[str] = []
    for skill_md in sorted(base_dir.glob("skills/*/SKILL.md")):
        for line_num, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in STALE_INSTALL_PATTERNS:
                if pattern.search(line):
                    rel = skill_md.relative_to(base_dir)
                    errors.append(f"{rel}:{line_num}: stale install reference: {line.strip()}")
                    break
    return errors


def check_stale_references(base_dir: Path) -> list[str]:
    """Check 1: No SKILL.md files should reference shared files via references/ paths."""
    errors: list[str] = []
    for skill_md in sorted(base_dir.glob("skills/*/SKILL.md")):
        for i, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
            if STALE_REF_PATTERN.search(line):
                rel = skill_md.relative_to(base_dir)
                errors.append(f"{rel}:{i}: stale references/ path (should use ../shared/)")
    return errors


def check_shared_files_exist(base_dir: Path) -> list[str]:
    """Check 2: All expected shared files must be present."""
    shared_dir = base_dir / "skills" / "shared"
    errors: list[str] = []
    for name in SHARED_FILES:
        if not (shared_dir / name).is_file():
            errors.append(f"MISSING: skills/shared/{name}")
    return errors


def get_canonical_version(base_dir: Path) -> str:
    """Extract the canonical mthds-agent version from mthds-agent-guide.md.

    The canonical version comes from the first 'mthds-agent >= X.Y.Z' match.
    Also validates that all semver strings on line 3 match the canonical version.
    """
    guide = base_dir / "skills" / "shared" / "mthds-agent-guide.md"
    if not guide.is_file():
        raise ValueError(f"File not found: {guide.relative_to(base_dir)}")
    text = guide.read_text(encoding="utf-8")

    match = CANONICAL_VERSION_PATTERN.search(text)
    if not match:
        raise ValueError(f"Cannot extract canonical version from {guide.relative_to(base_dir)}")

    canonical = match.group(1)

    # Validate line 3 consistency (all semver strings on that line must match)
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError(f"{guide.relative_to(base_dir)} has only {len(lines)} line(s), expected at least 3")

    line3_versions = SEMVER_PATTERN.findall(lines[2])
    if not line3_versions:
        raise ValueError(f"Cannot extract version(s) from line 3 of {guide.relative_to(base_dir)}")
    for v in line3_versions:
        if v != canonical:
            raise ValueError(f"{guide.relative_to(base_dir)} line 3 has {v}, expected {canonical}")

    return canonical


def check_frontmatter_versions(base_dir: Path, canonical: str) -> list[str]:
    """Check 3: All SKILL.md frontmatter min_mthds_version must match canonical."""
    errors: list[str] = []
    for skill_md in sorted(base_dir.glob("skills/*/SKILL.md")):
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

    # Check 0: plugin.json and marketplace.json version sync
    print("Checking plugin version sync...")
    try:
        errors, plugin_ver, marketplace_ver = check_plugin_version_sync(base_dir)
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot read plugin version files.")
        return 1
    if errors:
        for error in errors:
            print(f"  MISMATCH: {error}")
        print("FAIL: plugin.json and marketplace.json versions are out of sync.")
        failed = True
    else:
        print(f"  plugin.json: {plugin_ver}, marketplace.json: {marketplace_ver}")
        print("  Versions in sync.")

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

    # Check 2: shared files exist
    print("Checking all shared files exist...")
    errors = check_shared_files_exist(base_dir)
    if errors:
        for error in errors:
            print(f"  {error}")
        print("FAIL: Some shared files are missing.")
        failed = True
    else:
        print("  All shared files present.")

    # Check 3: frontmatter version consistency
    print("Checking min_mthds_version consistency...")
    try:
        canonical = get_canonical_version(base_dir)
    except ValueError as exc:
        print(f"  {exc}")
        print("FAIL: Cannot determine canonical version.")
        return 1

    errors = check_frontmatter_versions(base_dir, canonical)
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
