"""Tests for the per-target SKILL overlay mechanism.

A `templates/skills/<skill>/SKILL.<target_name>.md.j2` file is appended to that
skill's output ONLY when building <target_name> — letting a target add content
without touching the shared skill template (so every other target stays
byte-identical). The mthds-sandbox target uses this for the silent workspace
check (mthds-build / mthds-vibe) and the "method summary on request only" rule
(mthds-build / mthds-vibe / mthds-check).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest

from scripts.gen_skill_docs import load_defaults, load_target_config, render_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
TARGETS_DIR = REPO_ROOT / "targets"
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

    @pytest.mark.parametrize("skill", ["mthds-build", "mthds-vibe", "mthds-check", "mthds-edit", "mthds-fix"])
    def test_sandbox_suppresses_summary(self, skill: str) -> None:
        # The sandbox build/edit/fix/validate surface must not auto-emit a summary.
        assert NO_SUMMARY_MARKER in _build_skill("sandbox", skill)

    @pytest.mark.parametrize("skill", ["mthds-build", "mthds-vibe", "mthds-check", "mthds-edit", "mthds-fix"])
    def test_prod_keeps_summary_behavior(self, skill: str) -> None:
        # Only the sandbox target carries the no-summary rule.
        assert NO_SUMMARY_MARKER not in _build_skill("prod", skill)


REMOTE_RULE_MARKER = "Remote-storage rule (HARD)"


def _build_inputs_skill_for_target(target_name: str) -> str:
    """Render mthds-inputs with the target's FULLY MERGED vars (defaults + target .toml),
    so a var overridden only in the target file (e.g. `remote_storage_inputs`) is honored —
    unlike the overlay tests, which render from defaults alone."""
    defaults = load_defaults(TARGETS_DIR)
    config = load_target_config(TARGETS_DIR, target_name, defaults)
    rendered = render_templates(TEMPLATES_DIR, REPO_ROOT, config.template_vars, ["mthds-inputs"], target_name=target_name)
    return next(content for path, content in rendered.items() if path.parent.name == "mthds-inputs" and path.name == "SKILL.md")


class TestRemoteStorageInputs:
    """`remote_storage_inputs` (true only in sandbox.toml) forces inputs.json to carry
    remote `pipelex-storage://` URIs — never a local path. Guards against the sandbox
    inputs-skill regressing to local-path guidance (which cannot resolve on the hosted
    runner) and against the rule leaking into non-sandbox targets."""

    def test_sandbox_enforces_remote_uris(self) -> None:
        skill = _build_inputs_skill_for_target("sandbox")
        assert REMOTE_RULE_MARKER in skill
        assert "mthds-agent inputs upload" in skill

    def test_sandbox_has_no_local_path_in_any_url_field(self) -> None:
        # No `"url": "inputs/…"`, relative, or absolute local path may appear in a JSON
        # example — every url must be a remote URI in this environment.
        skill = _build_inputs_skill_for_target("sandbox")
        for bad in ('"url": "inputs/', '"url": "./', '"url": "../', '"url": "/'):
            assert bad not in skill, f"sandbox inputs skill leaks a local path: {bad}"

    def test_prod_keeps_local_path_guidance(self) -> None:
        skill = _build_inputs_skill_for_target("prod")
        assert REMOTE_RULE_MARKER not in skill
        assert "pipelex-storage://" not in skill
        assert '"url": "inputs/invoice.pdf"' in skill
