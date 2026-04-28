"""Tests for scripts/gen_skill_docs.py template rendering."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from scripts.gen_skill_docs import (
    CODEX_DISCOVERY_MARKETPLACE_DST,
    CODEX_DISCOVERY_MARKETPLACE_SRC,
    EXECUTABLE_OUTPUTS,
    HOOK_TEMPLATES,
    HOOK_TEMPLATES_BY_PLATFORM,
    SHARED_TEMPLATES,
    Platform,
    TargetConfig,
    build_target,
    check_freshness,
    generate,
    load_target_config,
    make_plugin_json,
    render_codex_discovery_marketplace,
    render_templates,
)

DEFAULT_VARS = {"min_mthds_version": "1.0.0", "marketplace_name": "mthds-plugins", "plugin_name": "mthds"}


def _create_required_templates(templates_dir: Path) -> None:
    """Create all shared and hook template files required by render_templates."""
    for name in SHARED_TEMPLATES:
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# placeholder\n")
    for name in HOOK_TEMPLATES:
        path = templates_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# placeholder\n")


@pytest.fixture()
def template_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with templates/ directory, skills/ output, and target configs."""
    # Templates directory (source of truth)
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    # All declared shared templates must exist (render_templates enforces this)
    (shared / "preamble.md.j2").write_text("Preamble content here.\n")
    (shared / "mthds-agent-guide.md.j2").write_text("Guide: mthds-agent >= {{ min_mthds_version }}\n")
    (shared / "error-handling.md.j2").write_text("# Error Handling\n")
    (shared / "frontmatter.md.j2").write_text("min_mthds_version: {{ min_mthds_version }}\n")
    (shared / "mthds-reference.md.j2").write_text("# MTHDS Reference\n")
    (shared / "native-content-types.md.j2").write_text("# Native Content Types\n")
    (shared / "python-execution.md.j2").write_text("# Python Execution Reference\n")
    (shared / "upgrade-flow.md.j2").write_text("# Upgrade Flow\n")
    # Hook templates must also exist
    hooks_tmpl = templates_dir / "hooks"
    hooks_tmpl.mkdir()
    (hooks_tmpl / "hooks.json.j2").write_text("{}\n")
    (hooks_tmpl / "validate-mthds.sh.j2").write_text("#!/bin/bash\n")
    (hooks_tmpl / "session-start.sh.j2").write_text("#!/bin/bash\n")

    skill_dir = templates_dir / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n---\n\n### Step 0\n\n{% include 'skills/shared/preamble.md.j2' %}\nRest of skill.\n")

    # plugin-base.json (shared fields for all targets)
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin-base.json").write_text('{"author": {"name": "test"}, "license": "MIT"}\n')

    # Target configs
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\nmarketplace_name = "mthds-plugins"\n')
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "mthds/"\n')

    return tmp_path


class TestRenderTemplates:
    def test_renders_include(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        skill_output = template_tree / "skills" / "mthds-test" / "SKILL.md"
        assert skill_output in results
        rendered = results[skill_output]
        assert "Preamble content here." in rendered
        assert "Rest of skill." in rendered
        assert "{% include" not in rendered

    def test_renders_shared_templates(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        guide_output = template_tree / "skills" / "shared" / "mthds-agent-guide.md"
        assert guide_output in results
        assert "mthds-agent >= 1.0.0" in results[guide_output]

    def test_no_skill_templates(self, tmp_path: Path) -> None:
        """With shared/hook templates but no skill templates, shared and hooks are still rendered."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        _create_required_templates(templates_dir)
        results = render_templates(templates_dir, tmp_path, DEFAULT_VARS)
        # Shared and hook templates are rendered even without skills
        assert len(results) > 0
        output_names = {path.name for path in results}
        assert "mthds-agent-guide.md" in output_names

    def test_preserves_frontmatter(self, template_tree: Path) -> None:
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        output_path = template_tree / "skills" / "mthds-test" / "SKILL.md"
        rendered = results[output_path]
        assert rendered.startswith("---\nname: test\n---\n")

    def test_missing_include_raises(self, tmp_path: Path) -> None:
        """Missing include file produces a clear error, not a raw traceback."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "mthds-test"
        skill_dir.mkdir(parents=True)
        _create_required_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% include 'skills/shared/nonexistent.md.j2' %}\n")
        with pytest.raises(SystemExit, match="include file not found"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_syntax_error_raises(self, tmp_path: Path) -> None:
        """Template syntax errors produce a clear error."""
        templates_dir = tmp_path / "templates"
        skill_dir = templates_dir / "skills" / "mthds-test"
        skill_dir.mkdir(parents=True)
        _create_required_templates(templates_dir)
        (skill_dir / "SKILL.md.j2").write_text("{% if %}\n")
        with pytest.raises(SystemExit, match="syntax error"):
            render_templates(templates_dir, tmp_path, DEFAULT_VARS)

    def test_missing_templates_dir_raises(self, tmp_path: Path) -> None:
        """Non-existent templates directory raises a clear error."""
        missing_dir = tmp_path / "templates"
        with pytest.raises(SystemExit, match="Templates directory not found"):
            render_templates(missing_dir, tmp_path, DEFAULT_VARS)

    def test_multiple_templates(self, template_tree: Path) -> None:
        """Multiple .j2 templates are all rendered."""
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "mthds-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nSecond skill content.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"mthds-test", "mthds-second"}

    def test_jinja2_escape_rendering(self, template_tree: Path) -> None:
        """Jinja2 escape sequences render to literal braces in output."""
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "mthds-escape"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Raw Jinja2 `{{ '{{' }} {{ '}}' }}` syntax\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS)
        output_path = template_tree / "skills" / "mthds-escape" / "SKILL.md"
        rendered = results[output_path]
        assert "{{ }}" in rendered
        assert "{{ '{{' }}" not in rendered

    def test_include_skills_filter(self, template_tree: Path) -> None:
        """include_skills parameter filters which skills are rendered."""
        templates_dir = template_tree / "templates"
        second = templates_dir / "skills" / "mthds-second"
        second.mkdir()
        (second / "SKILL.md.j2").write_text("---\nname: second\n---\n\nContent.\n")

        results = render_templates(templates_dir, template_tree, DEFAULT_VARS, include_skills=["mthds-test"])
        skill_names = {path.parent.name for path in results if path.parent.name not in ("shared", "hooks")}
        assert skill_names == {"mthds-test"}

    def test_empty_skill_filter_still_renders_shared_and_hooks(self, template_tree: Path) -> None:
        """When include_skills matches no skills, shared and hook templates are still rendered."""
        templates_dir = template_tree / "templates"
        results = render_templates(templates_dir, template_tree, DEFAULT_VARS, include_skills=["nonexistent-skill"])
        # No skill templates, but shared and hooks should be present
        output_names = {path.name for path in results}
        assert "mthds-agent-guide.md" in output_names
        assert "hooks.json" in output_names

    def test_template_vars_injected(self, template_tree: Path) -> None:
        """Custom template variables are accessible in templates."""
        templates_dir = template_tree / "templates"
        skill_dir = templates_dir / "skills" / "mthds-var"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text("Version: {{ min_mthds_version }}\n")

        custom_vars = {**DEFAULT_VARS, "min_mthds_version": "9.9.9"}
        results = render_templates(templates_dir, template_tree, custom_vars)
        output_path = template_tree / "skills" / "mthds-var" / "SKILL.md"
        assert "Version: 9.9.9" in results[output_path]


class TestGenerate:
    def test_writes_files(self, template_tree: Path) -> None:
        result = generate(template_tree, "prod")
        assert result == 0
        output = template_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        assert output.is_file()
        content = output.read_text()
        assert "Preamble content here." in content

    def test_no_templates_fails(self, tmp_path: Path) -> None:
        """Missing shared/hook template files cause a clear SystemExit."""
        (tmp_path / "templates").mkdir()
        targets_dir = tmp_path / "targets"
        targets_dir.mkdir()
        (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\n')
        (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "mthds/"\n')
        with pytest.raises(SystemExit, match="shared template not found"):
            generate(tmp_path, "prod")


class TestCheckFreshness:
    def test_fresh_passes(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        result = check_freshness(template_tree, "prod")
        assert result == 0

    def test_stale_fails(self, template_tree: Path) -> None:
        generate(template_tree, "prod")
        output = template_tree / "mthds" / "skills" / "mthds-test" / "SKILL.md"
        output.write_text("outdated content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_missing_md_fails(self, template_tree: Path) -> None:
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_orphaned_md_fails(self, template_tree: Path) -> None:
        """A SKILL.md without a corresponding .j2 is detected as orphan."""
        generate(template_tree, "prod")
        orphan_dir = template_tree / "mthds" / "skills" / "mthds-orphan"
        orphan_dir.mkdir()
        (orphan_dir / "SKILL.md").write_text("orphaned content\n")
        result = check_freshness(template_tree, "prod")
        assert result == 1

    def test_dry_run_no_side_effects(self, template_tree: Path) -> None:
        """check_freshness with a non-root target must not create output directories."""
        targets_dir = template_tree / "targets"
        (targets_dir / "dev.toml").write_text('[plugin]\nname = "mthds-dev"\nversion = "0.1.0"\ndescription = "dev"\nsource = "mthds-dev/"\n')
        dev_dir = template_tree / "mthds-dev"
        assert not dev_dir.exists()
        check_freshness(template_tree, "dev")
        assert not dev_dir.exists(), "check_freshness should not create output directories"

    def test_detects_non_executable_hook(self, template_tree: Path) -> None:
        """A non-executable hook script is detected as stale."""
        generate(template_tree, "prod")
        # Find the generated executable file and remove its exec bit
        for exec_name in EXECUTABLE_OUTPUTS:
            hook_path = template_tree / "mthds" / "hooks" / exec_name
            if hook_path.is_file():
                hook_path.chmod(0o644)
                break
        result = check_freshness(template_tree, "prod")
        assert result == 1


class TestCodexDiscoveryMarketplace:
    """Tests for the .agents/plugins/marketplace.json sync (the file Codex
    reads when resolving `codex plugin marketplace add mthds-ai/mthds-plugins`).
    Covers `render_codex_discovery_marketplace`, `generate`'s sync side-effect,
    and `check_freshness`'s missing-/stale-file detection. Regression suite
    for greptile P2 (PR #11) — these were untested when added."""

    def test_render_returns_none_when_source_absent(self, tmp_path: Path) -> None:
        """A repo without packaging/codex-marketplace.json (Claude-only fork
        or test fixture) skips the discovery sync silently."""
        result = render_codex_discovery_marketplace(tmp_path)
        assert result is None

    def test_render_returns_content_when_source_present(self, tmp_path: Path) -> None:
        """When the canonical source exists, render returns its bytes
        verbatim (no transformation — both files live at the repo root and
        stay byte-identical)."""
        source_path = tmp_path / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        canonical = '{"name": "mthds-plugins", "plugins": []}\n'
        source_path.write_text(canonical, encoding="utf-8")

        result = render_codex_discovery_marketplace(tmp_path)
        assert result == canonical

    def test_generate_writes_discovery_when_source_present(self, tmp_path: Path) -> None:
        """`generate` syncs `.agents/plugins/marketplace.json` whenever the
        canonical packaging file exists."""
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        canonical = '{"name": "mthds-plugins", "plugins": [{"name": "mthds"}]}\n'
        source_path.write_text(canonical, encoding="utf-8")

        result = generate(tree, "codex")
        assert result == 0

        synced = tree / CODEX_DISCOVERY_MARKETPLACE_DST
        assert synced.is_file(), f"{CODEX_DISCOVERY_MARKETPLACE_DST} should be written"
        assert synced.read_text(encoding="utf-8") == canonical

    def test_generate_skips_discovery_when_source_absent(self, template_tree: Path) -> None:
        """Repos without the canonical source (e.g. Claude-only test fixtures)
        must not have an empty discovery file written. The sync block returns
        None and skips the write entirely."""
        # template_tree has no packaging/codex-marketplace.json
        generate(template_tree, "prod")
        synced = template_tree / CODEX_DISCOVERY_MARKETPLACE_DST
        assert not synced.exists(), "discovery file should not be created when source is absent"

    def test_check_freshness_detects_missing_discovery(self, tmp_path: Path) -> None:
        """When the source exists but the discovery copy hasn't been written
        (or got deleted), check_freshness returns non-zero."""
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        source_path.write_text('{"name": "mthds-plugins", "plugins": []}\n', encoding="utf-8")
        # Generate normally to bring everything else fresh.
        generate(tree, "codex")
        # Now delete the discovery copy.
        (tree / CODEX_DISCOVERY_MARKETPLACE_DST).unlink()

        result = check_freshness(tree, "codex")
        assert result == 1

    def test_check_freshness_detects_stale_discovery(self, tmp_path: Path) -> None:
        """When the discovery copy exists but its bytes don't match the
        source, check_freshness returns non-zero (catches forgotten rebuilds
        after editing packaging/codex-marketplace.json)."""
        tree = _create_codex_tree(tmp_path)
        source_path = tree / CODEX_DISCOVERY_MARKETPLACE_SRC
        source_path.parent.mkdir(parents=True)
        source_path.write_text('{"name": "mthds-plugins", "plugins": []}\n', encoding="utf-8")
        generate(tree, "codex")
        # Tamper with the synced copy.
        (tree / CODEX_DISCOVERY_MARKETPLACE_DST).write_text('{"name": "stale", "plugins": []}\n', encoding="utf-8")

        result = check_freshness(tree, "codex")
        assert result == 1


def _create_codex_tree(tmp_path: Path) -> Path:
    """Create a minimal repo with both Claude and Codex targets."""
    templates_dir = tmp_path / "templates"
    shared = templates_dir / "skills" / "shared"
    shared.mkdir(parents=True)
    (shared / "preamble.md.j2").write_text("Preamble.\n")
    (shared / "mthds-agent-guide.md.j2").write_text("Guide.\n")
    (shared / "error-handling.md.j2").write_text("Errors.\n")
    (shared / "frontmatter.md.j2").write_text('{%- if platform != "codex" -%}\nallowed-tools:\n  - Bash\n{% endif -%}\n')
    (shared / "mthds-reference.md.j2").write_text("Ref.\n")
    (shared / "native-content-types.md.j2").write_text("Types.\n")
    (shared / "python-execution.md.j2").write_text("Python.\n")
    (shared / "upgrade-flow.md.j2").write_text("Upgrade.\n")

    # Claude hooks (Codex platform renders no hook files — runtime lives in
    # mthds-agent codex hook, not in a plugin-bundled script)
    hooks_tmpl = templates_dir / "hooks"
    hooks_tmpl.mkdir()
    (hooks_tmpl / "hooks.json.j2").write_text("{}\n")
    (hooks_tmpl / "validate-mthds.sh.j2").write_text("#!/bin/bash\n")
    (hooks_tmpl / "session-start.sh.j2").write_text("#!/bin/bash\n")

    skill_dir = templates_dir / "skills" / "mthds-test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md.j2").write_text("---\nname: test\n{% include 'skills/shared/frontmatter.md.j2' %}---\n\nContent.\n")

    # Claude plugin base
    claude_plugin = tmp_path / ".claude-plugin"
    claude_plugin.mkdir()
    (claude_plugin / "plugin-base.json").write_text('{"author": {"name": "test"}, "license": "MIT"}\n')

    # Codex plugin base
    codex_plugin = tmp_path / ".codex-plugin"
    codex_plugin.mkdir()
    (codex_plugin / "plugin-base.json").write_text(
        '{"author": {"name": "test"}, "license": "MIT", "skills": "./skills/", "interface": {"displayName": "Test"}}\n'
    )

    # Target configs
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    (targets_dir / "defaults.toml").write_text('[vars]\nmin_mthds_version = "1.0.0"\nmarketplace_name = "mthds-plugins"\nplatform = "claude"\n')
    (targets_dir / "prod.toml").write_text('[plugin]\nname = "mthds"\nversion = "1.0.0"\nsource = "mthds/"\n')
    (targets_dir / "codex.toml").write_text('[plugin]\nname = "mthds"\nversion = "0.1.0"\nsource = "mthds-codex/"\n\n[vars]\nplatform = "codex"\n')

    return tmp_path


def _render_codex_preamble_bash() -> str:
    """Render the production Codex skill preamble template and return the
    first ```bash code block (the env-check resolver). Used by the
    TestCodexTarget regression tests that exercise the resolver end-to-end."""
    repo_root = Path(__file__).resolve().parents[2]
    env = Environment(
        loader=FileSystemLoader(str(repo_root / "templates")),
        autoescape=False,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("skills/shared/preamble.md.j2").render(
        platform="codex",
        min_mthds_version="0.5.0",
        marketplace_name="mthds-plugins",
    )
    match = re.search(r"```bash\n(.*?)\n```", rendered, re.DOTALL)
    if match is None:
        raise AssertionError(f"No bash block in rendered preamble:\n{rendered}")
    return match.group(1)


def _make_fake_codex_cache(tmp_path: Path, versions: list[str]) -> Path:
    """Build a fake CODEX_HOME under tmp_path with one stub env-check per
    version. Each stub prints its own version when invoked, so the
    subprocess stdout reveals which one the resolver picked."""
    fake_codex_home = tmp_path / "fake-codex"
    for version in versions:
        bin_dir = fake_codex_home / "plugins" / "cache" / "mthds-plugins" / "mthds" / version / "bin"
        bin_dir.mkdir(parents=True)
        stub = bin_dir / "mthds-env-check"
        stub.write_text(f"#!/usr/bin/env bash\necho {version}\n")
        stub.chmod(0o755)
    return fake_codex_home


def _run_preamble_bash(bash_cmd: str, codex_home: Path) -> "subprocess.CompletedProcess[str]":
    """Run the rendered preamble bash with a minimal clean env. LC_ALL=C
    pins lex-compare ordering — the keys are digit-only by construction
    so this is defensive, not load-bearing."""
    return subprocess.run(
        ["bash", "-c", bash_cmd],
        env={
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
        },
        capture_output=True,
        text=True,
        check=False,
    )


class TestCodexTarget:
    """Tests for Codex platform support in the build system."""

    def test_target_config_platform_default(self) -> None:
        """TargetConfig.platform defaults to 'claude' when not set."""
        config = TargetConfig(
            name="test",
            plugin_name="test",
            plugin_version="1.0.0",
            plugin_description="",
            source="test/",
            template_vars={"min_mthds_version": "1.0.0"},
        )
        assert config.platform == "claude"

    def test_target_config_platform_codex(self) -> None:
        """TargetConfig.platform returns 'codex' when set."""
        config = TargetConfig(
            name="test",
            plugin_name="test",
            plugin_version="1.0.0",
            plugin_description="",
            source="test/",
            template_vars={"platform": "codex"},
        )
        assert config.platform == "codex"

    def test_load_codex_target_config(self, tmp_path: Path) -> None:
        """load_target_config loads Codex target with platform='codex'."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        assert config.platform == "codex"
        assert config.plugin_name == "mthds"
        assert config.source == "mthds-codex/"

    def test_codex_renders_no_hook_files(self, tmp_path: Path) -> None:
        """Codex platform ships no hook files — the validation runtime lives in
        `mthds-agent codex hook` (mthds-js npm package), wired into
        ~/.codex/hooks.json by `mthds-agent codex install-hook`."""
        tree = _create_codex_tree(tmp_path)
        codex_vars = {**DEFAULT_VARS, "platform": "codex"}
        results = render_templates(tree / "templates", tree, codex_vars)
        output_names = {path.name for path in results}
        assert "codex-hooks.json" not in output_names
        assert "codex-validate-mthds.sh" not in output_names
        assert "hooks.json" not in output_names
        assert "validate-mthds.sh" not in output_names

    def test_claude_uses_claude_hook_templates(self, tmp_path: Path) -> None:
        """Claude platform still renders Claude hook templates (regression)."""
        tree = _create_codex_tree(tmp_path)
        claude_vars = {**DEFAULT_VARS, "platform": "claude"}
        results = render_templates(tree / "templates", tree, claude_vars)
        output_names = {path.name for path in results}
        assert "hooks.json" in output_names
        assert "validate-mthds.sh" in output_names
        assert "codex-hooks.json" not in output_names

    def test_codex_frontmatter_no_allowed_tools(self, tmp_path: Path) -> None:
        """Codex skills do not include allowed-tools in frontmatter."""
        tree = _create_codex_tree(tmp_path)
        codex_vars = {**DEFAULT_VARS, "platform": "codex"}
        results = render_templates(tree / "templates", tree, codex_vars)
        skill_path = tree / "skills" / "mthds-test" / "SKILL.md"
        assert skill_path in results
        assert "allowed-tools" not in results[skill_path]

    def test_claude_frontmatter_has_allowed_tools(self, tmp_path: Path) -> None:
        """Claude skills still include allowed-tools in frontmatter (regression)."""
        tree = _create_codex_tree(tmp_path)
        claude_vars = {**DEFAULT_VARS, "platform": "claude"}
        results = render_templates(tree / "templates", tree, claude_vars)
        skill_path = tree / "skills" / "mthds-test" / "SKILL.md"
        assert skill_path in results
        assert "allowed-tools" in results[skill_path]

    def test_codex_plugin_json_uses_codex_base(self, tmp_path: Path) -> None:
        """make_plugin_json reads from .codex-plugin/plugin-base.json for Codex."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["name"] == "mthds"
        assert plugin_json["version"] == "0.1.0"
        assert "skills" in plugin_json
        assert "interface" in plugin_json

    def test_claude_plugin_json_uses_claude_base(self, tmp_path: Path) -> None:
        """make_plugin_json reads from .claude-plugin/plugin-base.json for Claude (regression)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        plugin_json = make_plugin_json(tree, config)
        assert plugin_json["name"] == "mthds"
        assert "skills" not in plugin_json
        assert "interface" not in plugin_json

    def test_build_codex_target_writes_codex_plugin_dir(self, tmp_path: Path) -> None:
        """build_target creates .codex-plugin/plugin.json for Codex, not .claude-plugin/."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "codex")
        result = build_target(tree, config)
        codex_manifest = tree / "mthds-codex" / ".codex-plugin" / "plugin.json"
        claude_manifest = tree / "mthds-codex" / ".claude-plugin" / "plugin.json"
        assert codex_manifest in result.files
        assert claude_manifest not in result.files
        # Verify plugin.json content
        plugin_data = json.loads(result.files[codex_manifest])
        assert plugin_data["name"] == "mthds"
        assert "interface" in plugin_data

    def test_build_claude_target_still_writes_claude_plugin_dir(self, tmp_path: Path) -> None:
        """build_target creates .claude-plugin/plugin.json for Claude (regression)."""
        tree = _create_codex_tree(tmp_path)
        config = load_target_config(tree / "targets", "prod")
        result = build_target(tree, config)
        claude_manifest = tree / "mthds" / ".claude-plugin" / "plugin.json"
        codex_manifest = tree / "mthds" / ".codex-plugin" / "plugin.json"
        assert claude_manifest in result.files
        assert codex_manifest not in result.files

    def test_codex_preamble_globs_pick_latest_env_check(self, tmp_path: Path) -> None:
        """The Codex preamble bash must exec the env-check from the version
        with the highest **semver** (not the lex-greatest). Cache contains
        0.8.1, 0.9.0, 0.10.0, 0.11.5 — pure lex order would pick 0.9.0 (since
        '9' > '1' lex-wise); semver-aware order picks 0.11.5. Regression for
        greptile P1 (PR #11) and the follow-up demand for proper ordering."""
        cache = _make_fake_codex_cache(tmp_path, ["0.8.1", "0.9.0", "0.10.0", "0.11.5"])
        result = _run_preamble_bash(_render_codex_preamble_bash(), cache)
        assert result.returncode == 0, f"bash exited {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
        assert result.stdout.strip() == "0.11.5", (
            f"Expected the highest semver (0.11.5) to be exec'd, got: stdout={result.stdout!r}, stderr={result.stderr!r}"
        )

    def test_codex_preamble_handles_two_digit_minor(self, tmp_path: Path) -> None:
        """Minimal regression: 0.9.0 vs 0.10.0 cached, the latter must win.
        This is the precise case lex order gets backwards ('0.10.0' < '0.9.0'
        lex-wise) and is the headline reason we abandoned the lex hack."""
        cache = _make_fake_codex_cache(tmp_path, ["0.9.0", "0.10.0"])
        result = _run_preamble_bash(_render_codex_preamble_bash(), cache)
        assert result.returncode == 0
        assert result.stdout.strip() == "0.10.0", f"Expected 0.10.0 to win over 0.9.0 (semver-aware), got: stdout={result.stdout!r}"

    def test_codex_preamble_handles_prerelease_versions(self, tmp_path: Path) -> None:
        """Prerelease/build-metadata segments are stripped before sort-key
        construction (we don't model full SemVer 2.0.0 prerelease precedence
        in bash). Cache has 0.5.0-beta and 0.5.0; either may win the
        tiebreaker, but both must run successfully without throwing."""
        cache = _make_fake_codex_cache(tmp_path, ["0.5.0-beta", "0.5.0"])
        result = _run_preamble_bash(_render_codex_preamble_bash(), cache)
        assert result.returncode == 0, f"bash exited {result.returncode}: stderr={result.stderr!r}"
        assert result.stdout.strip() in {"0.5.0", "0.5.0-beta"}, f"Expected one of 0.5.0/0.5.0-beta, got: stdout={result.stdout!r}"

    def test_codex_preamble_handles_single_cached_version(self, tmp_path: Path) -> None:
        """When only one version is cached, the resolver picks it without
        entering the comparison branch. Locks in the loop's first-iteration
        path (empty `_best_k` < anything non-empty)."""
        cache = _make_fake_codex_cache(tmp_path, ["0.5.0"])
        result = _run_preamble_bash(_render_codex_preamble_bash(), cache)
        assert result.returncode == 0
        assert result.stdout.strip() == "0.5.0"

    def test_codex_preamble_skips_non_semver_directory_names(self, tmp_path: Path) -> None:
        """A non-semver version dir (e.g. 'local') must not be picked over a
        real semver entry. The numeric strip turns 'local' into a sort key
        of all-zeros (six chars), which loses the lex compare against any
        real version's longer padded key."""
        cache = _make_fake_codex_cache(tmp_path, ["local", "0.10.0"])
        result = _run_preamble_bash(_render_codex_preamble_bash(), cache)
        assert result.returncode == 0
        assert result.stdout.strip() == "0.10.0", f"Expected 0.10.0 to win over non-semver 'local', got: stdout={result.stdout!r}"

    def test_codex_preamble_falls_back_when_no_env_check_cached(self, tmp_path: Path) -> None:
        """When CODEX_HOME has no cached env-check at all, the preamble's
        bash must fall through to the `MTHDS_ENV_CHECK_MISSING` echo (which
        the skill's preamble logic treats as a WARN, not a STOP)."""
        empty_codex_home = tmp_path / "empty-codex"
        empty_codex_home.mkdir()
        result = _run_preamble_bash(_render_codex_preamble_bash(), empty_codex_home)
        assert result.returncode == 0
        assert result.stdout.strip() == "MTHDS_ENV_CHECK_MISSING", f"Expected fallback echo, got: stdout={result.stdout!r}, stderr={result.stderr!r}"

    def test_hook_templates_by_platform_has_both(self) -> None:
        """HOOK_TEMPLATES_BY_PLATFORM defines templates for both platforms.
        Claude renders the bundled hook script; Codex renders nothing because
        its hook runtime lives in the agent (out-of-repo)."""
        assert "claude" in HOOK_TEMPLATES_BY_PLATFORM
        assert "codex" in HOOK_TEMPLATES_BY_PLATFORM
        assert len(HOOK_TEMPLATES_BY_PLATFORM[Platform.CLAUDE]) == 3
        assert HOOK_TEMPLATES_BY_PLATFORM[Platform.CODEX] == []
