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

    @pytest.mark.parametrize(
        "body_source",
        [("skill", "mthds-fix"), ("shared", "error-handling.md.j2")],
        ids=["fix", "error-handling"],
    )
    def test_error_tables_key_on_codes_beside_older_types(self, body_source: tuple[str, str]) -> None:
        """The fix table and the error-handling table match the 0.90.0 code first, keeping the older type beside it."""
        kind, name = body_source
        body = _skill(name) if kind == "skill" else _shared(name)
        assert "| Code | Type before 0.90.0 |" in body
        assert "match the **Code** column" in body
        assert "match the **Type before 0.90.0** column" in body
        for code, older_type in [
            ("method.input_undeclared", "missing_input_variable"),
            ("method.input_unused", "extraneous_input_variable"),
            ("method.input_concept_mismatch", "input_stuff_spec_mismatch"),
            ("method.output_concept_mismatch", "inadequate_output_concept"),
            ("method.output_multiplicity_mismatch", "inadequate_output_multiplicity"),
            ("method.identifier_invalid", "invalid_pipe_code_syntax"),
            ("method.name_conflict", "batch_item_name_collision"),
            ("method.field_path_unresolved", "binding_path_unresolved"),
        ]:
            assert f"| `{code}` | `{older_type}` |" in body
        assert "| `method.cycle` | none:" in body
        assert "circular_dependency_error" not in body
        assert "error_type" not in body

    def test_error_handling_says_errors_print_in_markdown(self) -> None:
        body = _shared("error-handling.md.j2")
        assert "prints JSON to **stderr**" not in body
        assert "prints its error report to **stderr**" in body
        assert "`--error-format json` gives JSON" in body

    def test_error_handling_names_the_090_domains_beside_the_older_ones(self) -> None:
        """The domain table is pipelex 0.90.0's five domains, and the older three are mapped onto them."""
        body = _shared("error-handling.md.j2")
        for domain in ["input", "method", "account", "operator", "runtime"]:
            assert f"\n| `{domain}` |" in body
        assert "\n| `config` |" not in body
        assert "`` - Code: `method.invalid` (domain method, retry no) ``" in body
        assert "its `code`, `domain` and `retry` members" in body
        assert "Before pipelex 0.90.0 a report gave one of three domains in its `error_domain` field" in body
        assert "`config`, which covered what is now `account` and `operator`" in body

    def test_error_handling_reads_a_failed_run_from_the_markdown_report(self) -> None:
        """A failed run is read off the Markdown report's Location line, with the JSON members and the older fields as fallbacks."""
        body = _shared("error-handling.md.j2")
        assert "the error JSON" not in body
        assert "in error JSON" not in body
        assert "failure_memory_path" not in body
        assert "BuildPipeError" not in body
        assert "`run` prints the report in Markdown by default" in body
        assert "`- Location: pipe 'summarize', path main > summarize`" in body
        assert "`location.pipe` and `location.path`" in body
        assert "reported as `run.failed`" in body
        assert "| A failed run: its root fault's code (`PipelineExecutionError` before 0.90.0) |" in body
        assert "(`pipe_code` and `pipe_stack` before 0.90.0)" in body

    def test_design_stops_on_the_090_domains(self) -> None:
        body = _skill("mthds-design")
        assert "| an error in the `method` or `input` domain (`input` alone before pipelex 0.90.0) |" in body
        assert "| an error in the `account`, `operator` or `runtime` domain (`config` or `runtime` before pipelex 0.90.0) |" in body
        assert "| an error in the `config` or `runtime` domain |" not in body
