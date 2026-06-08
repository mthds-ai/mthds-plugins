"""Tests for the `can_run_methods` template flag.

`can_run_methods` (defaults.toml) gates the instructions/suggestions to RUN
methods (`mthds-agent run`, dry-run/mock next-steps, the synthesis pipeline in
mthds-inputs). Targets where execution happens elsewhere (e.g. a locked-down
sandbox behind a platform UI) set `can_run_methods = false` so the agent never
runs or suggests running.

These render the REAL skill templates so removing/rewording a gate fails CI.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULTS_TOML = REPO_ROOT / "targets" / "defaults.toml"

RUN_MARKER = "mthds-agent run"
# Skills that carry "run a method" suggestions and must gate them.
GATED_SKILLS = ["mthds-build", "mthds-edit", "mthds-inputs", "mthds-explain", "mthds-vibe"]


def _default_vars() -> dict[str, object]:
    return dict(tomllib.loads(DEFAULTS_TOML.read_text())["vars"])


def _render(skill: str, *, can_run_methods: bool) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), keep_trailing_newline=True)
    template = env.get_template(f"skills/{skill}/SKILL.md.j2")
    return template.render(**{**_default_vars(), "can_run_methods": can_run_methods})


class TestCanRunMethodsFlag:
    def test_default_is_true(self) -> None:
        assert _default_vars()["can_run_methods"] is True

    @pytest.mark.parametrize("skill", GATED_SKILLS)
    def test_on_keeps_off_removes_run_suggestions(self, skill: str) -> None:
        rendered_on = _render(skill, can_run_methods=True)
        assert RUN_MARKER in rendered_on, f"{skill} expected a run suggestion when on"
        rendered_off = _render(skill, can_run_methods=False)
        assert RUN_MARKER not in rendered_off
        assert "{% if" not in rendered_off

    def test_inputs_off_drops_image_synthesis_section(self) -> None:
        # The runnable "Image Generation" section invokes a synthesis pipeline —
        # the whole section is gated out (a few prose mentions elsewhere remain,
        # but no executable run command survives — see the parametrized test).
        assert "## Image Generation" in _render("mthds-inputs", can_run_methods=True)
        assert "## Image Generation" not in _render("mthds-inputs", can_run_methods=False)

    def test_build_off_keeps_non_run_delivery(self) -> None:
        # Gating run suggestions must not remove the rest of "Present Results".
        off = _render("mthds-build", can_run_methods=False)
        assert "Input schema" in off
        assert "NEVER write `inputs.json` manually" in off
