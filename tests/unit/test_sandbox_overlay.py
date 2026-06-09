"""Tests for the per-target SKILL overlay mechanism.

A `templates/skills/<skill>/SKILL.<target_name>.md.j2` file is appended to that
skill's output ONLY when building <target_name> — letting a target add content
without touching the shared skill template (so every other target stays
byte-identical). The mthds-sandbox target uses this for the silent workspace
check on mthds-build / mthds-vibe.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from scripts.gen_skill_docs import render_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULTS_TOML = REPO_ROOT / "targets" / "defaults.toml"
OVERLAY_MARKER = "Workspace check (silent"


def _default_vars() -> dict[str, str | bool]:
    return cast("dict[str, str | bool]", dict(tomllib.loads(DEFAULTS_TOML.read_text())["vars"]))


def _build_skill(target_name: str | None) -> str:
    rendered = render_templates(TEMPLATES_DIR, REPO_ROOT, _default_vars(), ["mthds-build"], target_name=target_name)
    return next(content for path, content in rendered.items() if path.parent.name == "mthds-build" and path.name == "SKILL.md")


class TestSandboxOverlay:
    def test_sandbox_target_appends_overlay(self) -> None:
        # mthds-build/SKILL.sandbox.md.j2 is appended only for the sandbox target.
        assert OVERLAY_MARKER in _build_skill("sandbox")

    def test_target_without_overlay_file_is_unchanged(self) -> None:
        # prod has no SKILL.prod.md.j2, so the overlay never appears.
        assert OVERLAY_MARKER not in _build_skill("prod")

    def test_no_target_name_skips_overlays(self) -> None:
        assert OVERLAY_MARKER not in _build_skill(None)
