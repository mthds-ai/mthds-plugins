"""Tests for the per-target SKILL overlay mechanism.

A `templates/skills/<skill>/SKILL.<target_name>.md.j2` file is appended to that
skill's output ONLY when building <target_name> — letting a target add content
without touching the shared skill template (so every other target stays
byte-identical). The mthds-sandbox target uses this for the silent workspace
check (mthds-build / mthds-recursive) and the "method summary on request only" rule
(mthds-build / mthds-recursive / mthds-check).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest

from scripts.gen_skill_docs import render_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULTS_TOML = REPO_ROOT / "targets" / "defaults.toml"
WORKSPACE_MARKER = "Workspace check (silent"
NO_SUMMARY_MARKER = "Method summary (on request only)"


def _default_vars() -> dict[str, str | bool]:
    return cast("dict[str, str | bool]", dict(tomllib.loads(DEFAULTS_TOML.read_text())["vars"]))


def _build_skill(target_name: str | None, skill: str = "mthds-build") -> str:
    rendered = render_templates(TEMPLATES_DIR, REPO_ROOT, _default_vars(), [skill], target_name=target_name)
    return next(content for path, content in rendered.items() if path.parent.name == skill and path.name == "SKILL.md")


class TestSandboxOverlay:
    def test_sandbox_target_appends_overlay(self) -> None:
        # mthds-build/SKILL.sandbox.md.j2 is appended only for the sandbox target.
        assert WORKSPACE_MARKER in _build_skill("sandbox")

    def test_target_without_overlay_file_is_unchanged(self) -> None:
        # prod has no SKILL.prod.md.j2, so the overlay never appears.
        assert WORKSPACE_MARKER not in _build_skill("prod")

    def test_no_target_name_skips_overlays(self) -> None:
        assert WORKSPACE_MARKER not in _build_skill(None)

    @pytest.mark.parametrize("skill", ["mthds-build", "mthds-recursive", "mthds-check", "mthds-edit", "mthds-fix"])
    def test_sandbox_suppresses_summary(self, skill: str) -> None:
        # The sandbox build/edit/fix/validate surface must not auto-emit a summary.
        assert NO_SUMMARY_MARKER in _build_skill("sandbox", skill)

    @pytest.mark.parametrize("skill", ["mthds-build", "mthds-recursive", "mthds-check", "mthds-edit", "mthds-fix"])
    def test_prod_keeps_summary_behavior(self, skill: str) -> None:
        # Only the sandbox target carries the no-summary rule.
        assert NO_SUMMARY_MARKER not in _build_skill("prod", skill)
