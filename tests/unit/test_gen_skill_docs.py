"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import EXECUTABLE_OUTPUTS, HOOK_TEMPLATES, SHARED_TEMPLATES, check_freshness, generate, render_templates

DEFAULT_VARS = {"min_mthds_version": "1.0.0", "marketplace_name": "mthds-plugins", "plugin_name": "mthds"}


def _create_required_templates(templates_dir: Path) -> None:
    """Create all shared and hook template files required by render_templates."""
    for name in SHARED_TEMPLATES:
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# placeholder\n")
    for name in HOOK_TEMPLATES:
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# placeholder\n")


@pytest.fixture()
def template_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with templates/ directory, skills/ output, and target configs."""
    # Templates directory (source of truth)
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    # All declared shared templates must exist (render_templates enforces this)
    (shared / "preamble.md.j2").write_text("Preamble content here.\n")
    (shared / "mthds-agent-guide.md.j2").write_text("Guide: mthds-agent >= {{ min_mthds_version }}\n")
    (shared / "error-handling.md.j2").write_text("# Error Handling\n")
    (shared / "frontmatter.md.j2").write_text("min_mthds_version: {{ min_mthds_version }}\n")
    (shared / "mthds-reference.md.j2").write_text("# MTHDS Reference\n")
    (shared / "native-content-types.md.j2").write_text("# Native Content Types\n")
    (shared / "upgrade-flow.md.j2").write_text("# Upgrade Flow\n")
    # Hook templates must also exist
    hooks_tmpl = templates_dir / "hooks"
    hooks_tmpl.mkdir()
    (hooks_tmpl / "hooks.json.j2").write_text("{}\n")
    (hooks_tmpl / "validate-mthds.sh.j2").write_text("#!/bin/bash\n")

    skill_dir = templates_dir / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n---\n\n### Step 0\n\n{% include 'skills/shared/preamble.md.j2' %}\nRest of skill.\n")

    # plugin-base.json (shared fields for all targets)
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin-base.json").write_text('{"author": {"name": "test"}, "license": "MIT"}\n')

    # Target configs
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\nmarketplace_name = "mthds-plugins"\n')
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "mthds/"\n')

    return tmp_path


class TestRenderTemplates:
    def test_renders_include(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        skill_output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        assert skill_output in results
        rendered = results[skill_output]
        assert "Preamble content here." in rendered
        assert "Rest of skill." in rendered
        assert "{% include" not in rendered

    def test_renders_shared_templates(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        guide_output = template_tree / "skills" / "shared" / "mthds-agent-guide.md"
        assert guide_output in results
        assert "mthds-agent >= 1.0.0" in results[guide_output]

    def test_no_skill_templates(self, tmp_path: Path) -> None:
        """With shared/hook templates but no skill templates, shared and hooks are still rendered."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _create_required_templates(templates_dir)
        results = render_templates(templates_dir, tmp_path, DEFAULT_VARS)
        # Shared and hook templates are rendered even without skills
        assert len(results) > 0
        output_names = {path.name for path in results}
        assert "mthds-agent-guide.md" in output_names

    def test_preserves_frontmatter(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        output_path = template_tree / "skills" / "mthds-test" / "SKILL.md"
        rendered = results[output_path]
        assert rendered.startswith("---\nname: test\n---\n")

    def test_missing_include_raises(self, tmp_path: Path) -> None:
        """Missing include file produces a clear error, not a raw traceback."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "mthds-test"
        skill_dir.mkdir(parents=True)
        _create_required_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% include 'skills/shared/nonexistent.md.j2' %}\n")
        with pytest.raises(SystemExit, match="include file not found"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_syntax_error_raises(self, tmp_path: Path) -> None:
        """Template syntax errors produce a clear error."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "mthds-test"
        skill_dir.mkdir(parents=True)
        _create_required_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% if %}\n")
        with pytest.raises(SystemExit, match="syntax error"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_missing_templates_dir_raises(self, tmp_path: Path) -> None:
        """Non-existent templates directory raises a clear error."""
        missing_dir = tmp_path / "templates"
        with pytest.raises(SystemExit, match="Templates directory not found"):
            render_templates(missing_dir, tmp_path, DEFAULT_VARS)

    def test_multiple_templates(self, template_tree: Path) -> None:
        """Multiple .j2 templates are all rendered."""
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "mthds-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nSecond skill content.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"mthds-test", "mthds-second"}

    def test_jinja2_escape_rendering(self, template_tree: Path) -> None:
        """Jinja2 escape sequences render to literal braces in output."""
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "mthds-escape"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Raw Jinja2 `{{ '{{' }} {{ '}}' }}` syntax\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        output_path = template_tree / "skills" / "mthds-escape" / "SKILL.md"
        rendered = results[output_path]
        assert "{{ }}" in rendered
        assert "{{ '{{' }}" not in rendered

    def test_include_skills_filter(self, template_tree: Path) -> None:
        """include_skills parameter filters which skills are rendered."""
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "mthds-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nContent.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS, include_skills=["mthds-test"])
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"mthds-test"}

    def test_empty_skill_filter_still_renders_shared_and_hooks(self, template_tree: Path) -> None:
        """When include_skills matches no skills, shared and hook templates are still rendered."""
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS, include_skills=["nonexistent-skill"])
        # No skill templates, but shared and hooks should be present
        output_names = {path.name for path in results}
        assert "mthds-agent-guide.md" in output_names
        assert "hooks.json" in output_names

    def test_template_vars_injected(self, template_tree: Path) -> None:
        """Custom template variables are accessible in templates."""
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "mthds-var"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Version: {{ min_mthds_version }}\n")

        custom_vars = {**DEFAULT_VARS, "min_mthds_version": "9.9.9"}
        results = render_templates(templates_dir, template_tree, custom_vars)
        output_path = template_tree / "skills" / "mthds-var" / "SKILL.md"
        assert "Version: 9.9.9" in results[output_path]


class TestGenerate:
    def test_writes_files(self, template_tree: Path) -> None:
        result = generate(template_tree, "prod")
        assert result == 0
        output = template_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        assert output.is_file()
        content = output.read_text()
        assert "Preamble content here." in content

    def test_no_templates_fails(self, tmp_path: Path) -> None:
        """Missing shared/hook template files cause a clear SystemExit."""
        (tmp_path / "templates").mkdir()
        targets_dir = tmp_path / "targets"
        targets_dir.mkdir()
        (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\n')
        (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "mthds/"\n')
        with pytest.raises(SystemExit, match="shared template not found"):
            generate(tmp_path, "prod")


class TestCheckFreshness:
    def test_fresh_passes(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        result = check_freshness(template_tree, "prod")
        assert result == 0

    def test_stale_fails(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        output = template_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        output.write_text("outdated content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_missing_md_fails(self, template_tree: Path) -> None:
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_orphaned_md_fails(self, template_tree: Path) -> None:
        """A SKILL.md without a corresponding .j2 is detected as orphan."""
        generate(template_tree, "prod")
        orphan_dir = template_tree / "mthds" / "skills" / "mthds-orphan"
        orphan_dir.mkdir()
        (orphan_dir / "SKILL.md").write_text("orphaned content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_dry_run_no_side_effects(self, template_tree: Path) -> None:
        """check_freshness with a non-root target must not create output directories."""
        targets_dir = template_tree / "targets"
        (targets_dir / "dev.toml").write_text('[plugin]\nname = "mthds-dev"\nversion = "0.1.0"\ndescription = "dev"\nsource = "mthds-dev/"\n')
        dev_dir = template_tree / "mthds-dev"
        assert not dev_dir.exists()
        check_freshness(template_tree, "dev")
        assert not dev_dir.exists(), "check_freshness should not create output directories"

    def test_detects_non_executable_hook(self, template_tree: Path) -> None:
        """A non-executable hook script is detected as stale."""
        generate(template_tree, "prod")
        # Find the generated executable file and remove its exec bit
        for exec_name in EXECUTABLE_OUTPUTS:
            hook_path = template_tree / "mthds" / "hooks" / exec_name
            if hook_path.is_file():
                hook_path.chmod(0o644)
                break
        result = check_freshness(template_tree, "prod")
        assert result == 1
