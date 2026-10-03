"""Pin the design skill's construction model, the language reference it writes from, and the build's pruning.

`mthds-design` writes a bundle's TOML directly and lets `mthds-agent validate bundle`
judge it, as `pipelex-plugins`' `pipelex-design` does: no skill routes a concept or a
pipe through `mthds-agent concept` or `mthds-agent pipe`, whose API-runner arms post to
the `/v1/build/*` authoring routes being retired. These tests render every target, so a
regression in any shipped file fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.gen_skill_docs import (
    build_target,
    list_targets,
    load_defaults,
    load_target_config,
    reference_copy_mismatches,
    setup_static_assets,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_DIR = REPO_ROOT / "targets"
TEMPLATES_DIR = REPO_ROOT / "templates"
DESIGN_TEMPLATE = TEMPLATES_DIR / "skills" / "mthds-design" / "SKILL.md.j2"
STEPWISE_REFERENCE = REPO_ROOT / "skills" / "mthds-design" / "references" / "stepwise.md"
LANGUAGE_REFERENCE = TEMPLATES_DIR / "skills" / "shared" / "mthds-reference.md.j2"

SPEC_CONVERSION_CALL = re.compile(r"mthds-agent\s+(concept|pipe)\b")


def _rendered_files_of_every_target() -> dict[Path, str]:
    defaults = load_defaults(TARGETS_DIR)
    files: dict[Path, str] = {}
    for name in list_targets(TARGETS_DIR):
        config = load_target_config(TARGETS_DIR, name, defaults)
        files.update(build_target(REPO_ROOT, config, dry_run=True).files)
    return files


class TestNoSpecConversion:
    def test_no_rendered_file_runs_concept_or_pipe(self) -> None:
        offenders = [
            str(path.relative_to(REPO_ROOT)) for path, content in _rendered_files_of_every_target().items() if SPEC_CONVERSION_CALL.search(content)
        ]
        assert offenders == []

    def test_no_static_reference_runs_concept_or_pipe(self) -> None:
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in (REPO_ROOT / "skills").rglob("*.md")
            if SPEC_CONVERSION_CALL.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == []

    def test_retired_skills_are_gone(self) -> None:
        skills = {path.parent.name for path in TEMPLATES_DIR.glob("skills/*/SKILL.md.j2")}
        assert "mthds-design" in skills
        assert "mthds-build" not in skills
        assert "mthds-recursive" not in skills


class TestDesignSkill:
    @property
    def design(self) -> str:
        return DESIGN_TEMPLATE.read_text(encoding="utf-8")

    @property
    def stepwise(self) -> str:
        return STEPWISE_REFERENCE.read_text(encoding="utf-8")

    def test_direct_mode_covers_shallow_concrete_graphs(self) -> None:
        body = self.design
        assert "the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators" in body
        assert "every pipe can be concrete in the first coherent artifact" in body
        assert "Include **no temporary `PipeSignature` declarations**" in body
        assert "One controller is a strong fast-path signal, not a rule" in body

    def test_mode_is_inferred_never_asked(self) -> None:
        assert "**Never ask the user to choose the workflow.**" in self.design

    def test_direct_writes_with_the_file_tools(self) -> None:
        assert "Write it with your agent's file tools, never through the shell" in self.design

    def test_runnable_gate_is_strict_validation(self) -> None:
        body = self.design
        assert "mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph" in body
        assert "validation **without** `--allow-signatures` must pass" in body

    def test_stepwise_validates_leniently_then_strictly(self) -> None:
        body = self.stepwise
        assert "--allow-signatures --graph" in body
        assert "Every expansion adds exactly one new `<code>.mthds` definition file" in body
        assert "validate once more **without** `--allow-signatures`" in body

    def test_stepwise_reads_the_backlog_from_the_verdict(self) -> None:
        body = self.stepwise
        assert "## Pending signatures (N)" in body
        assert "never hand-track it" in body


class TestLanguageReference:
    @property
    def reference(self) -> str:
        return LANGUAGE_REFERENCE.read_text(encoding="utf-8")

    def test_bare_string_field_is_required(self) -> None:
        body = self.reference
        assert "**A bare string is a required text field.**" in body
        assert "Simple text field (optional)" not in body

    def test_domain_qualified_pipe_reference_is_valid(self) -> None:
        body = self.reference
        assert "Both forms are valid wherever a concept or a pipe is referenced" in body
        assert "will fail validation" not in body

    def test_model_lookup_uses_the_cli(self) -> None:
        body = self.reference
        assert "mthds-agent models --type <category>" in body
        assert "mthds-agent check-model '<reference>' --type <category>" in body
        assert "mthds_models" not in body


class TestBuildPruning:
    @staticmethod
    def _repo(tmp_path: Path, skills: list[str]) -> Path:
        base = tmp_path / "repo"
        for skill in skills:
            (base / "templates" / "skills" / skill).mkdir(parents=True)
            (base / "templates" / "skills" / skill / "SKILL.md.j2").write_text("x\n")
        return base

    def test_build_removes_a_retired_skill_directory(self, tmp_path: Path) -> None:
        base = self._repo(tmp_path, ["kept"])
        output = base / "out"
        (output / "skills" / "retired" / "references").mkdir(parents=True)
        (output / "skills" / "retired" / "SKILL.md").write_text("old\n")
        (output / "skills" / "shared").mkdir(parents=True)
        setup_static_assets(base, output, base / "templates", None)
        assert not (output / "skills" / "retired").exists()
        assert (output / "skills" / "shared").is_dir()
        assert (output / "skills" / "kept").is_dir()

    def test_build_removes_a_references_copy_whose_source_is_gone(self, tmp_path: Path) -> None:
        base = self._repo(tmp_path, ["kept"])
        output = base / "out"
        (output / "skills" / "kept" / "references").mkdir(parents=True)
        (output / "skills" / "kept" / "references" / "old.md").write_text("old\n")
        setup_static_assets(base, output, base / "templates", None)
        assert not (output / "skills" / "kept" / "references").exists()

    @pytest.mark.parametrize(
        ("source", "copy", "expected"),
        [
            ({"a.md": "new\n"}, {"a.md": "old\n"}, "STALE"),
            ({"a.md": "same\n"}, {"a.md": "same\n", "b.md": "gone\n"}, "ORPHAN"),
            ({"a.md": "same\n"}, {}, "MISSING"),
            (None, {"a.md": "gone\n"}, "ORPHAN"),
        ],
    )
    def test_check_reports_a_mismatched_references_copy(
        self, tmp_path: Path, source: dict[str, str] | None, copy: dict[str, str], expected: str
    ) -> None:
        base = tmp_path / "repo"
        output = base / "out"
        if source is not None:
            for name, text in source.items():
                (base / "skills" / "kept" / "references").mkdir(parents=True, exist_ok=True)
                (base / "skills" / "kept" / "references" / name).write_text(text)
        for name, text in copy.items():
            (output / "skills" / "kept" / "references").mkdir(parents=True, exist_ok=True)
            (output / "skills" / "kept" / "references" / name).write_text(text)
        findings = reference_copy_mismatches(base, output, ["kept"])
        assert any(finding.strip().startswith(expected) for finding in findings), findings

    def test_check_is_silent_on_a_fresh_copy(self, tmp_path: Path) -> None:
        base = tmp_path / "repo"
        output = base / "out"
        for root in (base / "skills" / "kept" / "references", output / "skills" / "kept" / "references"):
            root.mkdir(parents=True)
            (root / "a.md").write_text("same\n")
        assert reference_copy_mismatches(base, output, ["kept"]) == []
