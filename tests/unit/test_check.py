"""Tests for scripts/check.py validation checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check import (
    check_frontmatter_versions,
    check_marketplace_plugins,
    check_no_templates_in_output,
    check_shared_files_exist,
    check_stale_install_references,
    check_stale_references,
    check_target_plugin_versions,
    resolve_target_var,
)

CANONICAL = "0.3.3"

VALID_FRONTMATTER = f"---\nname: mthds-test\nmin_mthds_version: {CANONICAL}\ndescription: Test skill\n---\n\n# Test Skill\n"

PLUGIN_JSON_TEMPLATE = '{{\n  "name": "{name}",\n  "version": "{version}"\n}}'
MARKETPLACE_JSON_TEMPLATE = """\
{{
  "name": "mthds-plugins",
  "metadata": {{
    "version": "{version}"
  }},
  "plugins": {plugins_json}
}}"""


def _write_target_configs(
    base: Path,
    targets: dict[str, dict[str, str]],
    defaults_vars: dict[str, str] | None = None,
) -> None:
    """Write targets/ directory with defaults and per-target configs."""
    targets_dir = base / "targets"
    targets_dir.mkdir(parents=True, exist_ok=True)

    if defaults_vars is None:
        defaults_vars = {"min_mthds_version": CANONICAL, "marketplace_name": "mthds-plugins"}
    vars_lines = "\n".join(f'{key} = "{value}"' for key, value in defaults_vars.items())
    (targets_dir / "defaults.toml").write_text(f"[vars]\n{vars_lines}\n")

    for target_name, target_info in targets.items():
        (targets_dir / f"{target_name}.toml").write_text(
            f'[plugin]\nname = "{target_info["name"]}"\nversion = "{target_info["version"]}"\nsource = "{target_info.get("source", "./")}"\n'
        )


def _write_plugin_json(base: Path, name: str, version: str, subdir: str = ".") -> None:
    plugin_dir = base / subdir / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(PLUGIN_JSON_TEMPLATE.format(name=name, version=version))


def _write_marketplace_json(base: Path, version: str, plugins: list[dict[str, str]]) -> None:
    import json

    plugin_dir = base / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugins_json = json.dumps(plugins)
    (plugin_dir / "marketplace.json").write_text(MARKETPLACE_JSON_TEMPLATE.format(version=version, plugins_json=plugins_json))


@pytest.fixture()
def skill_tree(tmp_path: Path) -> Path:
    """Create a minimal valid skill directory structure with target configs."""
    # Template source files (checked by check_shared_files_exist)
    template_shared = tmp_path / "templates" / "skills" / "shared"
    template_shared.mkdir(parents=True)
    for name in [
        "error-handling.md.j2",
        "frontmatter.md.j2",
        "mthds-agent-guide.md.j2",
        "mthds-reference.md.j2",
        "native-content-types.md.j2",
        "preamble.md.j2",
        "upgrade-flow.md.j2",
    ]:
        (template_shared / name).write_text("# placeholder\n")

    # Output directories (prod target outputs to mthds/)
    (tmp_path / "mthds" / "skills" / "shared").mkdir(parents=True)

    skill_dir = tmp_path / "mthds" / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(VALID_FRONTMATTER)

    _write_target_configs(tmp_path, {"prod": {"name": "mthds", "version": "0.6.3", "source": "mthds/"}})
    _write_plugin_json(tmp_path, "mthds", "0.6.3", "mthds")
    _write_marketplace_json(tmp_path, "0.6.3", [{"name": "mthds", "source": "mthds/"}])

    return tmp_path


class TestTargetPluginVersions:
    def test_versions_consistent(self, skill_tree: Path) -> None:
        errors, versions = check_target_plugin_versions(skill_tree)
        assert errors == []
        assert versions == {"prod": "0.6.3"}

    def test_version_mismatch(self, skill_tree: Path) -> None:
        _write_plugin_json(skill_tree, "mthds", "0.6.0", "mthds")
        errors, _versions = check_target_plugin_versions(skill_tree)
        assert len(errors) == 1
        assert "0.6.0" in errors[0]
        assert "0.6.3" in errors[0]

    def test_name_mismatch(self, skill_tree: Path) -> None:
        _write_plugin_json(skill_tree, "wrong-name", "0.6.3", "mthds")
        errors, _versions = check_target_plugin_versions(skill_tree)
        assert len(errors) == 1
        assert "wrong-name" in errors[0]

    def test_missing_plugin_json(self, tmp_path: Path) -> None:
        _write_target_configs(tmp_path, {"prod": {"name": "mthds", "version": "0.6.3", "source": "mthds/"}})
        errors, _versions = check_target_plugin_versions(tmp_path)
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_multi_target(self, skill_tree: Path) -> None:
        """Multiple targets with different versions."""
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "mthds", "version": "0.6.3", "source": "mthds/"},
                "dev": {"name": "mthds-dev", "version": "0.1.0", "source": "mthds-dev/"},
            },
        )
        dev_dir = skill_tree / "mthds-dev"
        dev_dir.mkdir()
        _write_plugin_json(skill_tree, "mthds-dev", "0.1.0", "mthds-dev")
        errors, versions = check_target_plugin_versions(skill_tree)
        assert errors == []
        assert versions == {"prod": "0.6.3", "dev": "0.1.0"}


class TestMarketplacePlugins:
    def test_matching(self, skill_tree: Path) -> None:
        assert check_marketplace_plugins(skill_tree) == []

    def test_missing_from_marketplace(self, skill_tree: Path) -> None:
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "mthds", "version": "0.6.3", "source": "mthds/"},
                "dev": {"name": "mthds-dev", "version": "0.1.0", "source": "mthds-dev/"},
            },
        )
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "mthds-dev" in errors[0]
        assert "missing from marketplace" in errors[0]

    def test_extra_in_marketplace(self, skill_tree: Path) -> None:
        _write_marketplace_json(
            skill_tree,
            "0.6.3",
            [{"name": "mthds", "source": "mthds/"}, {"name": "ghost-plugin", "source": "ghost/"}],
        )
        errors = check_marketplace_plugins(skill_tree)
        assert len(errors) == 1
        assert "ghost-plugin" in errors[0]
        assert "no matching target" in errors[0]


class TestResolveTargetVar:
    def test_default_value(self, skill_tree: Path) -> None:
        assert resolve_target_var(skill_tree, "prod", "min_mthds_version") == CANONICAL

    def test_override_value(self, skill_tree: Path) -> None:
        # Add an override in prod.toml
        targets_dir = skill_tree / "targets"
        (targets_dir / "prod.toml").write_text(
            '[plugin]\nname = "mthds"\nversion = "0.6.3"\nsource = "mthds/"\n\n[vars]\nmin_mthds_version = "9.9.9"\n'
        )
        assert resolve_target_var(skill_tree, "prod", "min_mthds_version") == "9.9.9"

    def test_missing_var(self, skill_tree: Path) -> None:
        with pytest.raises(ValueError, match="not defined"):
            resolve_target_var(skill_tree, "prod", "nonexistent_var")

    def test_missing_target(self, skill_tree: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            resolve_target_var(skill_tree, "nonexistent", "min_mthds_version")


class TestStaleInstallReferences:
    def test_no_stale_install_refs(self, skill_tree: Path) -> None:
        assert check_stale_install_references(skill_tree) == []

    def test_detects_pip_install_pipelex(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install pipelex` to install.\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_detects_pip_install_pipelex_tools(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install pipelex-tools` first.\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_detects_curl_install_sh(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `curl -sSL https://example.com/install.sh | sh`\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 1
        assert "stale install reference" in errors[0]

    def test_ignores_pip_install_python_docx(self, skill_tree: Path) -> None:
        """Python library deps like python-docx are legitimate, not toolchain installs."""
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install python-docx` for Word support.\n")
        assert check_stale_install_references(skill_tree) == []

    def test_ignores_pip_install_openpyxl(self, skill_tree: Path) -> None:
        """Python library deps like openpyxl are legitimate, not toolchain installs."""
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nRun `pip install openpyxl` for Excel support.\n")
        assert check_stale_install_references(skill_tree) == []

    def test_multiple_stale_refs_across_lines(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\n`pip install pipelex`\nSome text\n`pip install pipelex-tools`\n")
        errors = check_stale_install_references(skill_tree)
        assert len(errors) == 2


class TestStaleReferences:
    def test_no_stale_refs(self, skill_tree: Path) -> None:
        assert check_stale_references(skill_tree) == []

    def test_detects_stale_ref(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [guide](references/mthds-agent-guide.md)\n")
        errors = check_stale_references(skill_tree)
        assert len(errors) == 1
        assert "stale references/" in errors[0]

    def test_ignores_correct_shared_path(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER + "\nSee [guide](../shared/mthds-agent-guide.md)\n")
        assert check_stale_references(skill_tree) == []


class TestSharedFilesExist:
    def test_all_present(self, skill_tree: Path) -> None:
        assert check_shared_files_exist(skill_tree) == []

    def test_missing_file(self, skill_tree: Path) -> None:
        (skill_tree / "templates" / "skills" / "shared" / "error-handling.md.j2").unlink()
        errors = check_shared_files_exist(skill_tree)
        assert len(errors) == 1
        assert "error-handling.md.j2" in errors[0]

    def test_all_missing(self, tmp_path: Path) -> None:
        (tmp_path / "templates" / "skills" / "shared").mkdir(parents=True)
        errors = check_shared_files_exist(tmp_path)
        assert len(errors) == 7


class TestFrontmatterVersions:
    def test_matching_version(self, skill_tree: Path) -> None:
        assert check_frontmatter_versions(skill_tree, CANONICAL, "prod") == []

    def test_mismatched_version(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text(VALID_FRONTMATTER.replace(CANONICAL, "0.0.1"))
        errors = check_frontmatter_versions(skill_tree, CANONICAL, "prod")
        assert len(errors) == 1
        assert "0.0.1" in errors[0]

    def test_missing_version_key(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text("---\nname: test\ndescription: test\n---\n\n# Test\n")
        errors = check_frontmatter_versions(skill_tree, CANONICAL, "prod")
        assert len(errors) == 1
        assert "no min_mthds_version" in errors[0]

    def test_no_frontmatter(self, skill_tree: Path) -> None:
        skill_md = skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        skill_md.write_text("# Just a heading\n")
        errors = check_frontmatter_versions(skill_tree, CANONICAL, "prod")
        assert len(errors) == 1
        assert "no frontmatter" in errors[0]

    def test_multiple_skills(self, skill_tree: Path) -> None:
        """Two skills: one correct, one wrong."""
        bad_dir = skill_tree / "mthds" / "skills" / "mthds-bad"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(VALID_FRONTMATTER.replace(CANONICAL, "0.0.5"))
        errors = check_frontmatter_versions(skill_tree, CANONICAL, "prod")
        assert len(errors) == 1


class TestNoTemplatesInOutput:
    def test_clean_state(self, skill_tree: Path) -> None:
        assert check_no_templates_in_output(skill_tree) == []

    def test_detects_leaked_j2_in_skills(self, skill_tree: Path) -> None:
        (skill_tree / "mthds" / "skills" / "mthds-test").mkdir(parents=True, exist_ok=True)
        (skill_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md.j2").write_text("leaked\n")
        errors = check_no_templates_in_output(skill_tree)
        assert len(errors) == 1
        assert "LEAKED TEMPLATE" in errors[0]

    def test_detects_leaked_j2_in_hooks(self, skill_tree: Path) -> None:
        hooks_dir = skill_tree / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        (hooks_dir / "validate-mthds.sh.j2").write_text("leaked\n")
        errors = check_no_templates_in_output(skill_tree)
        assert len(errors) == 1
        assert "hooks" in errors[0]

    def test_detects_leaked_j2_in_target_dir(self, skill_tree: Path) -> None:
        """Leaked .j2 files in non-root target output dirs are detected."""
        _write_target_configs(
            skill_tree,
            {
                "prod": {"name": "mthds", "version": "0.6.3", "source": "mthds/"},
                "dev": {"name": "mthds-dev", "version": "0.1.0", "source": "mthds-dev/"},
            },
        )
        target_skills = skill_tree / "mthds-dev" / "skills" / "mthds-test"
        target_skills.mkdir(parents=True)
        (target_skills / "SKILL.md.j2").write_text("leaked\n")
        errors = check_no_templates_in_output(skill_tree)
        assert len(errors) == 1
        assert "mthds-dev" in errors[0]
        assert "LEAKED TEMPLATE" in errors[0]

    def test_missing_dirs_no_crash(self, tmp_path: Path) -> None:
        """No crash when skills/ or hooks/ directories don't exist."""
        errors = check_no_templates_in_output(tmp_path)
        assert errors == []
