"""Tests for the `env_check` template flag.

The `env_check` var (defaults.toml) gates the "Step 0 — Environment Check"
preamble across all skills, plus the "Pipelex Runtime Check" in mthds-run. Some
deployment targets render in a pre-provisioned, locked-down environment where the
agent must never run env/doctor/upgrade commands; they set `env_check = false`.

These tests render the REAL skill templates so that removing or rewording the
gate (which would silently re-introduce the env-check) fails CI. They also assert
that env_check = false drops the standalone env-check artifacts entirely — the
preamble doc, the doctor/version session hook, and the env-check binary — not
just the in-skill sections.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest
from jinja2 import Environment, FileSystemLoader

from scripts.gen_skill_docs import render_templates, setup_static_assets

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

    def test_off_omits_preamble_and_session_hook_artifacts(self) -> None:
        # Gating the in-skill sections is not enough: env_check = false must also
        # stop emitting the standalone preamble doc and the doctor/version
        # session hook, which would otherwise ship as dead, contradictory files.
        base_vars = cast("dict[str, str | bool]", _default_vars())
        rendered_on = render_templates(TEMPLATES_DIR, REPO_ROOT, {**base_vars, "env_check": True})
        rendered_off = render_templates(TEMPLATES_DIR, REPO_ROOT, {**base_vars, "env_check": False})
        on_paths = {path.as_posix() for path in rendered_on}
        off_paths = {path.as_posix() for path in rendered_off}

        preamble = (REPO_ROOT / "skills" / "shared" / "preamble.md").as_posix()
        session_hook = (REPO_ROOT / "hooks" / "session-start.sh").as_posix()

        assert preamble in on_paths
        assert session_hook in on_paths
        assert preamble not in off_paths
        assert session_hook not in off_paths

    def test_off_omits_env_check_binary(self, tmp_path: Path) -> None:
        # The env-check binary is unused once the sections are gated out, so a
        # env_check = false target must not ship it — while keeping other bin/ files.
        out_off = tmp_path / "off"
        out_off.mkdir()
        setup_static_assets(REPO_ROOT, out_off, TEMPLATES_DIR, None, env_check=False)
        assert not (out_off / "bin" / "mthds-env-check").exists()
        assert (out_off / "bin" / "install.sh").is_file()

        out_on = tmp_path / "on"
        out_on.mkdir()
        setup_static_assets(REPO_ROOT, out_on, TEMPLATES_DIR, None, env_check=True)
        assert (out_on / "bin" / "mthds-env-check").is_file()
