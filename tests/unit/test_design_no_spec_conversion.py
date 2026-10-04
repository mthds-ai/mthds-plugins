"""Pin that no shipped file converts a concept or a pipe from a JSON spec.

No skill routes a concept or a pipe through `mthds-agent concept` or `mthds-agent pipe`,
whose API-runner arms post to the `/v1/build/*` authoring routes being retired. These
tests render every target, so a regression in any shipped file fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.gen_skill_docs import build_target, list_targets, load_defaults, load_target_config

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_DIR = REPO_ROOT / "targets"
TEMPLATES_DIR = REPO_ROOT / "templates"

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
