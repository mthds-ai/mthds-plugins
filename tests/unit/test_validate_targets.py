"""Pin the method's folder as the target `mthds-check` and `mthds-fix` validate.

Handed a folder, `validate bundle` judges every bundle of the method's tree from pipelex 0.89.0 on,
where a file plus `-L` dry-runs only that file's pipes; the skills keep the file form for one file
alone and for an older pipelex.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_TEMPLATES = REPO_ROOT / "templates" / "skills"


def _skill(name: str) -> str:
    return (SKILL_TEMPLATES / name / "SKILL.md.j2").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", ["mthds-check", "mthds-fix"])
def test_validates_the_method_folder(skill: str) -> None:
    body = _skill(skill)
    assert "```bash\nmthds-agent validate bundle <bundle-directory>/" in body
    assert "```bash\nmthds-agent validate bundle <file>.mthds" not in body
    assert "judges every bundle of that tree" in body


@pytest.mark.parametrize("skill", ["mthds-check", "mthds-fix"])
def test_keeps_the_one_file_form_with_its_coverage(skill: str) -> None:
    body = _skill(skill)
    assert "`mthds-agent validate bundle <file>.mthds -L <bundle-directory>/" in body
    assert "dry-runs only the file's own pipes" in body
    assert "pipelex judges a folder whole from 0.89.0 on" in body
