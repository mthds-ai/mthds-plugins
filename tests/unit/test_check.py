"""Tests for scripts/check.py validation checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import (
    check_frontmatter_versions,
    check_plugin_version_sync,
    check_shared_files_exist,
    check_stale_install_references,
    check_stale_references,
    get_canonical_version,
)

CANONICAL = "0.3.0"

GUIDE_CONTENT = (
    "# MTHDS Agent Guide\n"
    "\n"
    f"All skills in this plugin require `mthds-agent >= {CANONICAL}`. "
    "The Step 0 CLI Check in each skill enforces this — "
    "parse the output of `mthds-agent --version` and block execution "
    f"if the version is below `{CANONICAL}`.\n"
)

VALID_FRONTMATTER = f"---\nname: mthds-test\nmin_mthds_version: {CANONICAL}\ndescription: Test skill\n---\n\n# Test Skill\n"

PLUGIN_JSON_TEMPLATE = '{{\n  "name": "mthds",\n  "version": "{version}"\n}}'
MARKETPLACE_JSON_TEMPLATE = '{{\n  "name": "mthds-plugins",\n  "metadata": {{\n    "version": "{version}"\n  }}\n}}'


def _write_plugin_files(base: Path, plugin_version: str, marketplace_version: str) -> None:
    plugin_dir = base / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(PLUGIN_JSON_TEMPLATE.format(version=plugin_version))
    (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version=marketplace_version))


@pytest.fixture()
def skill_tree(tmp_path: Path) -> Path:
    """Create a minimal valid skill directory structure."""
    shared = tmp_path / "skills" / "shared"
    shared.mkdir(parents=True)
    for name in ["error-handling.md", "mthds-agent-guide.md", "mthds-reference.md", "native-content-types.md", "preamble.md", "upgrade-flow.md"]:
        (shared / name).write_text("# placeholder\n")
    (shared / "mthds-agent-guide.md").write_text(GUIDE_CONTENT)

    skill_dir = tmp_path / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER)

    return tmp_path


class TestStaleInstallReferences:
    def test_no_stale_install_refs(self, skill_tree: Path) -> None:
        assert check_stale_install_references(skill_tree) == []

    def test_detects_pip_install_pipelex(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install pipelex` to install.\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_detects_pip_install_pipelex_tools(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install pipelex-tools` first.\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_detects_curl_install_sh(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `curl -sSL https://example.com/install.sh | sh`\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_ignores_pip_install_python_docx(self, skill_tree: Path) -> None:
        """Python library deps like python-docx are legitimate, not toolchain installs."""
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install python-docx` for Word support.\n")
        assert check_stale_install_references(skill_tree) == []

    def test_ignores_pip_install_openpyxl(self, skill_tree: Path) -> None:
        """Python library deps like openpyxl are legitimate, not toolchain installs."""
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install openpyxl` for Excel support.\n")
        assert check_stale_install_references(skill_tree) == []

    def test_multiple_stale_refs_across_lines(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\n`pip install pipelex`\nSome text\n`pip install pipelex-tools`\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 2


class TestStaleReferences:
    def test_no_stale_refs(self, skill_tree: Path) -> None:
        assert check_stale_references(skill_tree) == []

    def test_detects_stale_ref(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [guide](references/mthds-agent-guide.md)\n")
        errors = check_stale_references(skill_tree)
        assert len(errors) == 1
        assert "stale references/" in errors[0]

    def test_ignores_correct_shared_path(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [guide](../shared/mthds-agent-guide.md)\n")
        assert check_stale_references(skill_tree) == []


class TestSharedFilesExist:
    def test_all_present(self, skill_tree: Path) -> None:
        assert check_shared_files_exist(skill_tree) == []

    def test_missing_file(self, skill_tree: Path) -> None:
        (skill_tree / "skills" / "shared" / "error-handling.md").unlink()
        errors = check_shared_files_exist(skill_tree)
        assert len(errors) == 1
        assert "error-handling.md" in errors[0]

    def test_all_missing(self, tmp_path: Path) -> None:
        (tmp_path / "skills" / "shared").mkdir(parents=True)
        errors = check_shared_files_exist(tmp_path)
        assert len(errors) == 6


class TestCanonicalVersion:
    def test_extracts_version(self, skill_tree: Path) -> None:
        assert get_canonical_version(skill_tree) == CANONICAL

    def test_raises_on_missing_pattern(self, skill_tree: Path) -> None:
        guide = skill_tree / "skills" / "shared" / "mthds-agent-guide.md"
        guide.write_text("# No version here\n\nJust some text.\n")
        with pytest.raises(ValueError, match="Cannot extract canonical version"):
            get_canonical_version(skill_tree)

    def test_raises_on_truncated_guide(self, skill_tree: Path) -> None:
        guide = skill_tree / "skills" / "shared" / "mthds-agent-guide.md"
        guide.write_text(f"# MTHDS Agent Guide\nRequires `mthds-agent >= {CANONICAL}`.\n")
        with pytest.raises(ValueError, match="only 2 line"):
            get_canonical_version(skill_tree)

    def test_raises_on_line3_mismatch(self, skill_tree: Path) -> None:
        guide = skill_tree / "skills" / "shared" / "mthds-agent-guide.md"
        guide.write_text(f"# MTHDS Agent Guide\n\nRequires `mthds-agent >= {CANONICAL}`. Block if below `0.0.9`.\n")
        with pytest.raises(ValueError, match=f"has 0.0.9, expected {CANONICAL}"):
            get_canonical_version(skill_tree)


class TestFrontmatterVersions:
    def test_matching_version(self, skill_tree: Path) -> None:
        assert check_frontmatter_versions(skill_tree, CANONICAL) == []

    def test_mismatched_version(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER.replace(CANONICAL, "0.0.1"))
        errors = check_frontmatter_versions(skill_tree, CANONICAL)
        assert len(errors) == 1
        assert "0.0.1" in errors[0]

    def test_missing_version_key(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text("---\nname: test\ndescription: test\n---\n\n# Test\n")
        errors = check_frontmatter_versions(skill_tree, CANONICAL)
        assert len(errors) == 1
        assert "no min_mthds_version" in errors[0]

    def test_no_frontmatter(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text("# Just a heading\n")
        errors = check_frontmatter_versions(skill_tree, CANONICAL)
        assert len(errors) == 1
        assert "no frontmatter" in errors[0]

    def test_multiple_skills(self, skill_tree: Path) -> None:
        """Two skills: one correct, one wrong."""
        bad_dir = skill_tree / "skills" / "mthds-bad"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(VALID_FRONTMATTER.replace(CANONICAL, "0.0.5"))
        errors = check_frontmatter_versions(skill_tree, CANONICAL)
        assert len(errors) == 1
        assert "mthds-bad" in errors[0]


class TestPluginVersionSync:
    def test_versions_in_sync(self, tmp_path: Path) -> None:
        _write_plugin_files(tmp_path, "0.6.0", "0.6.0")
        errors, plugin_ver, marketplace_ver = check_plugin_version_sync(tmp_path)
        assert errors == []
        assert plugin_ver == "0.6.0"
        assert marketplace_ver == "0.6.0"

    def test_versions_out_of_sync(self, tmp_path: Path) -> None:
        _write_plugin_files(tmp_path, "0.6.2", "0.6.0")
        errors, plugin_ver, marketplace_ver = check_plugin_version_sync(tmp_path)
        assert len(errors) == 1
        assert "0.6.2" in errors[0]
        assert "0.6.0" in errors[0]
        assert plugin_ver == "0.6.2"
        assert marketplace_ver == "0.6.0"

    def test_missing_plugin_json(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version="0.6.0"))
        with pytest.raises(ValueError, match="plugin.json not found"):
            check_plugin_version_sync(tmp_path)

    def test_missing_marketplace_json(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(PLUGIN_JSON_TEMPLATE.format(version="0.6.0"))
        with pytest.raises(ValueError, match="marketplace.json not found"):
            check_plugin_version_sync(tmp_path)

    def test_malformed_json(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text("not json")
        (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version="0.6.0"))
        with pytest.raises(ValueError, match="not valid JSON"):
            check_plugin_version_sync(tmp_path)

    def test_missing_version_key(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"name": "mthds"}')
        (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version="0.6.0"))
        with pytest.raises(ValueError, match="missing key"):
            check_plugin_version_sync(tmp_path)
