"""Tests for the `env_check` template flag.

The `env_check` var (defaults.toml) gates the "Step 0 — Environment Check"
preamble across all skills, plus the "Pipelex Runtime Check" in mthds-run. Some
deployment targets render in a pre-provisioned, locked-down environment where the
agent must never run env/doctor/upgrade commands; they set `env_check = false`.

These tests render the REAL skill templates so that removing or rewording the
gate (which would silently re-introduce the env-check) fails CI.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULTS_TOML = REPO_ROOT / "targets" / "defaults.toml"

ENV_CHECK_MARKER = "Environment Check"
RUNTIME_CHECK_MARKER = "Pipelex Runtime Check"


def _default_vars() -> dict[str, object]:
    """All template vars from defaults.toml, so rendering never hits an undefined var."""
    data = tomllib.loads(DEFAULTS_TOML.read_text())
    return dict(data["vars"])


def _env() -> Environment:
    # Mirror scripts/gen_skill_docs.py's Jinja configuration.
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), keep_trailing_newline=True)


def _skill_template_names() -> list[str]:
    return sorted(path.parent.name for path in (TEMPLATES_DIR / "skills").glob("*/SKILL.md.j2"))


def _render(skill: str, *, env_check: bool) -> str:
    template = _env().get_template(f"skills/{skill}/SKILL.md.j2")
    return template.render(**{**_default_vars(), "env_check": env_check})


class TestEnvCheckFlag:
    def test_default_is_true(self) -> None:
        assert _default_vars()["env_check"] is True

    @pytest.mark.parametrize("skill", _skill_template_names())
    def test_on_keeps_off_removes_env_check(self, skill: str) -> None:
        rendered_on = _render(skill, env_check=True)
        if ENV_CHECK_MARKER not in rendered_on:
            pytest.skip(f"{skill} has no environment check section")
        rendered_off = _render(skill, env_check=False)
        assert ENV_CHECK_MARKER not in rendered_off
        # No dangling Jinja tags and no orphaned "Step 0" heading left behind.
        assert "{% if" not in rendered_off
        assert "Step 0" not in rendered_off

    def test_off_removes_pipelex_runtime_check_in_run(self) -> None:
        assert RUNTIME_CHECK_MARKER in _render("mthds-run", env_check=True)
        assert RUNTIME_CHECK_MARKER not in _render("mthds-run", env_check=False)

    def test_off_does_not_collapse_into_following_content(self) -> None:
        # When the section is removed, the next block must keep its own heading
        # and not run together with the preceding content.
        rendered_off = _render("mthds-run", env_check=False)
        assert "### Step 2: Identify the Target" in rendered_off
        assert "\n\n\n\n" not in rendered_off  # no run of blank lines from the cut
