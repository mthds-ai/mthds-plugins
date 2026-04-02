"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import check_freshness, generate, render_templates

DEFAULT_VARS = {"min_mthds_version": "1.0.0", "marketplace_name": "mthds-plugins", "plugin_name": "mthds"}


@pytest.fixture()
def template_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with templates/ directory, skills/ output, and target configs."""
    # Templates directory (source of truth)
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    (shared / "preamble.md.j2").write_text("Preamble content here.\n")
    (shared / "mthds-agent-guide.md.j2").write_text("Guide: mthds-agent >= {{ min_mthds_version }}\n")

    skill_dir = templates_dir / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n---\n\n### Step 0\n\n{% include 'skills/shared/preamble.md.j2' %}\nRest of skill.\n")

    # Output directories (will be populated by generate)
    (tmp_path / "skills" / "shared").mkdir(parents=True)
    (tmp_path / "hooks").mkdir(parents=True)

    # Root plugin.json (needed for non-root targets)
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "mthds", "version": "1.0.0", "description": "test"}\n')

    # Target configs
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\nmarketplace_name = "mthds-plugins"\n')
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "./"\n')

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

    def test_no_templates(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        results = render_templates(templates_dir, tmp_path, DEFAULT_VARS)
        assert results == {}

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
        (skill_dir / "SKILL.md.j2").write_text("{% include 'skills/shared/preamble.md.j2' %}\n")
        with pytest.raises(SystemExit, match="include file not found"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_syntax_error_raises(self, tmp_path: Path) -> None:
        """Template syntax errors produce a clear error."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "mthds-test"
        skill_dir.mkdir(parents=True)
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
        skill_names = {path.parent.name for path in results if path.parent.name != "shared"}
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
        skill_names = {path.parent.name for path in results if path.parent.name != "shared"}
        assert skill_names == {"mthds-test"}

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
        output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        assert output.is_file()
        content = output.read_text()
        assert "Preamble content here." in content

    def test_no_templates_fails(self, tmp_path: Path) -> None:
        (tmp_path / "templates").mkdir()
        targets_dir = tmp_path / "targets"
        targets_dir.mkdir()
        (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\n')
        (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "./"\n')
        result = generate(tmp_path, "prod")
        assert result == 1


class TestCheckFreshness:
    def test_fresh_passes(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        result = check_freshness(template_tree, "prod")
        assert result == 0

    def test_stale_fails(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        output.write_text("outdated content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_missing_md_fails(self, template_tree: Path) -> None:
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_orphaned_md_fails(self, template_tree: Path) -> None:
        """A SKILL.md without a corresponding .j2 is detected as orphan."""
        generate(template_tree, "prod")
        orphan_dir = template_tree / "skills" / "mthds-orphan"
        orphan_dir.mkdir()
        (orphan_dir / "SKILL.md").write_text("orphaned content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1
