from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_TEMPLATES = REPO_ROOT / "templates" / "skills"
SHARED_DIR = SKILL_TEMPLATES / "shared"

# A command line naming one bundle file with -L, the form that dry-runs only that file's pipes.
FILE_FORM_COMMAND_LINE = re.compile(r"^\s*mthds-agent validate bundle <file>\.mthds -L", re.MULTILINE)
# A command line validating a folder placeholder, possibly indented inside a list item.
FOLDER_COMMAND_LINE = re.compile(r"^\s*mthds-agent validate bundle <(?:bundle-directory|bundle-dir)>/(?: --graph)?$", re.MULTILINE)


def _skill(name: str) -> str:
    return (SKILL_TEMPLATES / name / "SKILL.md.j2").read_text(encoding="utf-8")


def _shared(name: str) -> str:
    return (SHARED_DIR / name).read_text(encoding="utf-8")


class TestValidateTargets:
    @pytest.mark.parametrize("skill", ["mthds-check", "mthds-fix", "mthds-edit", "mthds-explain"])
    def test_skills_validate_the_method_folder(self, skill: str) -> None:
        """Every skill validating a whole method hands `validate bundle` the folder, and states the 0.89.0 caveat."""
        body = _skill(skill)
        assert FOLDER_COMMAND_LINE.search(body) is not None
        assert FILE_FORM_COMMAND_LINE.search(body) is None
        assert "0.89.0 on" in body

    @pytest.mark.parametrize("skill", ["mthds-check", "mthds-fix", "mthds-edit", "mthds-explain"])
    def test_skills_say_what_the_file_form_covers(self, skill: str) -> None:
        body = _skill(skill)
        assert re.search(r"dry-runs only (?:the file's own|that file's) pipes", body) is not None

    @pytest.mark.parametrize("skill", ["mthds-check", "mthds-fix"])
    def test_check_and_fix_read_the_markdown_verdict(self, skill: str) -> None:
        body = _skill(skill)
        assert "`# Validation passed`" in body
        assert "pass no `--format`" in body
        assert "Parse the JSON" not in body
        assert "success: true" not in body

    def test_explain_graphs_the_method_folder(self) -> None:
        assert "```bash\nmthds-agent validate bundle <bundle-dir>/ --graph\n```" in _skill("mthds-explain")

    def test_error_handling_validates_the_method_folder(self) -> None:
        body = _shared("error-handling.md.j2")
        assert "\nmthds-agent validate bundle mthds-wip/pipeline_01/\n" in body
        assert "\nmthds-agent validate bundle ./my_bundle_dir/ -L ./shared_pipes/\n" in body
        assert "from pipelex 0.89.0 on" in body

    def test_agent_guide_validates_the_method_folder(self) -> None:
        body = _shared("mthds-agent-guide.md.j2")
        assert "validate bundle bundle.mthds" not in body
        assert "validate bundle file.mthds" not in body
        assert "validate bundle mthds-wip/pipeline_01/bundle.mthds" not in body
        assert "\nmthds-agent validate bundle <bundle-dir>/ --graph\n" in body
        assert "dry-runs only the file's own pipes" in body

    def test_enclosing_tree_is_stated_in_the_guide_once_and_in_design(self) -> None:
        guide = _shared("mthds-agent-guide.md.j2")
        assert guide.count("The search for a `METHODS.toml` stops at the root of the folder's git repository.") == 1
        design = _skill("mthds-design")
        assert "a bundle home inside a project that has its own `METHODS.toml` is validated, and run, as part of that project's tree" in design

    def test_language_reference_validates_the_method_folder(self) -> None:
        body = _shared("mthds-reference.md.j2")
        assert "so validate the method's folder: `mthds-agent validate bundle <bundle dir>/`" in body
        assert "loads every `.mthds` file beneath it" not in body
