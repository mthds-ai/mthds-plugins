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


def _render_doc(rel_path: str, *, can_run_methods: bool) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), keep_trailing_newline=True)
    return env.get_template(rel_path).render(**{**_default_vars(), "can_run_methods": can_run_methods})


# Skills that carry the "No backend setup needed → /mthds-runner-setup" pointer.
RUNNER_SETUP_SKILLS = ["mthds-build", "mthds-check", "mthds-edit", "mthds-explain", "mthds-inputs", "mthds-fix", "mthds-vibe"]


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

    def test_off_strips_run_content_from_shared_guide(self) -> None:
        # The shared CLI guide must not instruct a can_run_methods=false target to
        # set up runners, run methods, or pipe their output.
        on = _render_doc("skills/shared/mthds-agent-guide.md.j2", can_run_methods=True)
        off = _render_doc("skills/shared/mthds-agent-guide.md.j2", can_run_methods=False)
        for marker in ["### Runner Setup", "mthds-agent run bundle", "## Piping Methods", "## Inputs"]:
            assert marker in on, f"guide: {marker!r} expected when on"
            assert marker not in off, f"guide: {marker!r} must be gated when off"

    def test_off_strips_run_recovery_from_error_handling(self) -> None:
        # Error recovery that runs methods / configures runners only applies when
        # the target can run — gate it so the sandbox never follows it.
        on = _render_doc("skills/shared/error-handling.md.j2", can_run_methods=True)
        off = _render_doc("skills/shared/error-handling.md.j2", can_run_methods=False)
        for marker in ["/mthds-runner-setup", "mthds-agent doctor", "mthds-agent run bundle"]:
            assert marker in on, f"error-handling: {marker!r} expected when on"
            assert marker not in off, f"error-handling: {marker!r} must be gated when off"

    @pytest.mark.parametrize("skill", RUNNER_SETUP_SKILLS)
    def test_off_drops_runner_setup_pointer(self, skill: str) -> None:
        # The "No backend setup needed" blockquote points at /mthds-runner-setup,
        # which is not part of a can_run_methods=false surface.
        assert "/mthds-runner-setup" in _render(skill, can_run_methods=True), f"{skill} expected the pointer when on"
        assert "/mthds-runner-setup" not in _render(skill, can_run_methods=False), f"{skill} must drop the pointer when off"

    def test_off_fixes_inputs_image_anchor(self) -> None:
        # The Image Generation section is gated out, so its in-page link must go
        # too (else a broken anchor) — while the Document Generation link stays.
        off = _render("mthds-inputs", can_run_methods=False)
        assert "(#image-generation)" not in off
        assert "(#document-generation)" in off
