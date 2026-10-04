"""Pin that the build removes what nothing produces any more, and that `make check` reports it first."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.gen_skill_docs import orphan_skill_directories, reference_copy_mismatches, setup_static_assets


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

    def test_check_reports_a_retired_skill_left_without_its_skill_md(self, tmp_path: Path) -> None:
        base = tmp_path / "repo"
        skills_dir = base / "out" / "skills"
        (skills_dir / "retired" / "references").mkdir(parents=True)
        (skills_dir / "retired" / "references" / "cheat-sheet.md").write_text("old\n")
        (skills_dir / "kept").mkdir()
        (skills_dir / "shared").mkdir()
        findings = orphan_skill_directories(base, skills_dir, ["kept"])
        assert findings == ["  ORPHAN: out/skills/retired/ (no skill renders it: `make build` removes it)"]

    def test_check_leaves_a_retired_skill_md_to_its_own_finding(self, tmp_path: Path) -> None:
        base = tmp_path / "repo"
        skills_dir = base / "out" / "skills"
        (skills_dir / "retired").mkdir(parents=True)
        (skills_dir / "retired" / "SKILL.md").write_text("old\n")
        assert orphan_skill_directories(base, skills_dir, ["kept"]) == []
