"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import check_freshness, generate, render_templates


@pytest.fixture()
def template_tree(tmp_path: Path) -> Path:
    """Create a minimal skill directory with a .j2 template and shared include."""
    skills_dir = tmp_path / "skills"
    shared = skills_dir / "shared"
    shared.mkdir(parents=True)
    (shared / "preamble.md").write_text("Preamble content here.\n")
    (shared / "mthds-agent-guide.md").write_text("mthds-agent >= 1.0.0\n")

    skill_dir = skills_dir / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n---\n\n### Step 0\n\n{% include 'shared/preamble.md' %}\nRest of skill.\n")

    return tmp_path


class TestRenderTemplates:
    def test_renders_include(self, template_tree: Path) -> None:
        skills_dir = template_tree / "skills"
        results = render_templates(skills_dir)
        assert len(results) == 1
        output_path = skills_dir / "mthds-test" / "SKILL.md"
        assert output_path in results
        rendered = results[output_path]
        assert "Preamble content here." in rendered
        assert "Rest of skill." in rendered
        assert "{% include" not in rendered

    def test_no_templates(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        results = render_templates(skills_dir)
        assert results == {}

    def test_preserves_frontmatter(self, template_tree: Path) -> None:
        skills_dir = template_tree / "skills"
        results = render_templates(skills_dir)
        output_path = skills_dir / "mthds-test" / "SKILL.md"
        rendered = results[output_path]
        assert rendered.startswith("---\nname: test\n---\n")

    def test_missing_include_raises(self, tmp_path: Path) -> None:
        """Missing include file produces a clear error, not a raw traceback."""
        skills_dir = tmp_path / "skills"
        shared = skills_dir / "shared"
        shared.mkdir(parents=True)
        (shared / "mthds-agent-guide.md").write_text("mthds-agent >= 1.0.0\n")
        skill_dir = skills_dir / "mthds-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md.j2").write_text("{% include 'shared/preamble.md' %}\n")
        with pytest.raises(SystemExit, match="include file not found"):
            render_templates(skills_dir)

    def test_syntax_error_raises(self, tmp_path: Path) -> None:
        """Template syntax errors produce a clear error."""
        skills_dir = tmp_path / "skills"
        shared = skills_dir / "shared"
        shared.mkdir(parents=True)
        (shared / "mthds-agent-guide.md").write_text("mthds-agent >= 1.0.0\n")
        skill_dir = skills_dir / "mthds-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md.j2").write_text("{% if %}\n")
        with pytest.raises(SystemExit, match="syntax error"):
            render_templates(skills_dir)

    def test_missing_skills_dir_raises(self, tmp_path: Path) -> None:
        """Non-existent skills directory raises a clear error."""
        missing_dir = tmp_path / "skills"
        with pytest.raises(SystemExit, match="Skills directory not found"):
            render_templates(missing_dir)

    def test_multiple_templates(self, template_tree: Path) -> None:
        """Multiple .j2 templates are all rendered."""
        skills_dir = template_tree / "skills"
        second = skills_dir / "mthds-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nSecond skill content.\n")

        results = render_templates(skills_dir)
        assert len(results) == 2
        paths = {path.parent.name for path in results}
        assert paths == {"mthds-test", "mthds-second"}

    def test_jinja2_escape_rendering(self, template_tree: Path) -> None:
        """Jinja2 escape sequences render to literal braces in output."""
        skills_dir = template_tree / "skills"
        skill_dir = skills_dir / "mthds-escape"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Raw Jinja2 `{{ '{{' }} {{ '}}' }}` syntax\n")

        results = render_templates(skills_dir)
        output_path = skills_dir / "mthds-escape" / "SKILL.md"
        rendered = results[output_path]
        assert "{{ }}" in rendered
        assert "{{ '{{' }}" not in rendered


class TestGenerate:
    def test_writes_files(self, template_tree: Path) -> None:
        result = generate(template_tree)
        assert result == 0
        output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        assert output.is_file()
        content = output.read_text()
        assert "Preamble content here." in content

    def test_no_templates_fails(self, tmp_path: Path) -> None:
        (tmp_path / "skills").mkdir()
        result = generate(tmp_path)
        assert result == 1


class TestCheckFreshness:
    def test_fresh_passes(self, template_tree: Path) -> None:
        generate(template_tree)
        result = check_freshness(template_tree)
        assert result == 0

    def test_stale_fails(self, template_tree: Path) -> None:
        generate(template_tree)
        output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        output.write_text("outdated content\n")
        result = check_freshness(template_tree)
        assert result == 1

    def test_missing_md_fails(self, template_tree: Path) -> None:
        result = check_freshness(template_tree)
        assert result == 1

    def test_orphaned_md_fails(self, template_tree: Path) -> None:
        """A SKILL.md without a corresponding .j2 is detected as orphan."""
        generate(template_tree)
        orphan_dir = template_tree / "skills" / "mthds-orphan"
        orphan_dir.mkdir()
        (orphan_dir / "SKILL.md").write_text("orphaned content\n")
        result = check_freshness(template_tree)
        assert result == 1
