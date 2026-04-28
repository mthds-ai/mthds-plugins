"""Integration tests for the Codex PostToolUse(apply_patch) hook.

Creates stub scripts for plxt on an isolated PATH, then runs the full hook
pipeline against synthetic apply_patch payloads. The hook is the same
shape as the Claude hook except it parses `tool_input.command` (the raw
apply_patch envelope) instead of `tool_input.file_path`.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = REPO_ROOT / "mthds-codex" / "hooks" / "codex-validate-mthds.sh"


def _make_stub(path: Path, content: str) -> None:
    """Create an executable stub script."""
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _post_tool_use_json(command: str) -> str:
    """Build a PostToolUse(apply_patch) hook JSON payload with the raw patch envelope."""
    return json.dumps({"tool_name": "apply_patch", "tool_input": {"command": command}})


def _patch_envelope(*entries: tuple[str, str]) -> str:
    """Build a synthetic apply_patch envelope with the given (header, path) pairs.

    Each entry is one of: (`Update File`, path), (`Add File`, path), (`Move to`, path),
    (`Delete File`, path). The body content is irrelevant to the hook — only the headers
    are parsed.
    """
    lines = ["*** Begin Patch"]
    for header, path in entries:
        lines.append(f"*** {header}: {path}")
        lines.append("@@ stub body")
    lines.append("*** End Patch")
    return "\n".join(lines)


def _isolated_env(bin_dir: Path) -> dict[str, str]:
    """Build an isolated env where only bin_dir + system dirs are on PATH.

    Symlinks node into bin_dir so it's reachable. Excludes directories like
    /usr/local/bin and npm global paths where real plxt might live, ensuring
    tools are only found if explicitly stubbed into bin_dir.
    """
    node_path = shutil.which("node")
    if node_path and not (bin_dir / "node").exists():
        (bin_dir / "node").symlink_to(node_path)
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
    }


def _run_hook(stdin_data: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the Codex hook script with given stdin and environment."""
    return subprocess.run(
        ["bash", str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _plxt_recording_stub() -> str:
    """Build a plxt stub that records each invocation (subcommand + last arg) to a sidecar file."""
    return dedent(
        """\
        #!/bin/bash
        echo "$1 ${@: -1}" >> "$PLXT_LOG"
        exit 0
        """
    )


class TestCodexHookValidateMthds:
    """Integration tests for the Codex PostToolUse(apply_patch) hook."""

    @pytest.fixture()
    def hook_env(self, tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
        """Create an isolated environment with a working dir, a plxt log, and restricted PATH.

        Returns:
            Tuple of (bin_dir, work_dir, env). work_dir is the cwd seen by `*** Update File:`
            paths — the hook checks file existence before running plxt, so paths in tests
            should resolve to files inside this dir.
        """
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        env = _isolated_env(bin_dir)
        env["PLXT_LOG"] = str(tmp_path / "plxt.log")
        return bin_dir, work_dir, env

    # --- Guard tests: early exit paths ---

    def test_no_command_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Missing tool_input.command produces no output."""
        bin_dir, _, env = hook_env
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())
        stdin = json.dumps({"tool_name": "apply_patch", "tool_input": {}})
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_malformed_stdin_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Malformed JSON on stdin does not crash the hook."""
        _, _, env = hook_env
        result = _run_hook("not json at all", env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_empty_stdin_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        _, _, env = hook_env
        result = _run_hook("", env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_no_mthds_files_in_patch_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Patch touching only non-.mthds files produces no output."""
        bin_dir, work_dir, env = hook_env
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())
        py_file = work_dir / "script.py"
        py_file.write_text("print('hi')\n")
        stdin = _post_tool_use_json(_patch_envelope(("Update File", str(py_file))))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""
        assert not Path(env["PLXT_LOG"]).exists()

    def test_nonexistent_mthds_file_skipped(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Patch referencing a .mthds path that doesn't exist on disk (e.g. rename source)
        is silently skipped — no plxt invocation, no output.
        """
        bin_dir, work_dir, env = hook_env
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())
        ghost = work_dir / "ghost.mthds"
        stdin = _post_tool_use_json(_patch_envelope(("Update File", str(ghost))))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""
        assert not Path(env["PLXT_LOG"]).exists()

    # --- Missing tools ---

    def test_missing_plxt_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Missing plxt blocks with install instructions when an .mthds file is in the patch."""
        _, work_dir, env = hook_env
        bundle = work_dir / "bundle.mthds"
        bundle.write_text("[method]\nname = 'test'\n")
        stdin = _post_tool_use_json(_patch_envelope(("Update File", str(bundle))))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "plxt" in parsed["reason"]

    # --- Stage 1: plxt lint ---

    def test_lint_failure_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """plxt lint failure produces a block with lint output."""
        bin_dir, work_dir, env = hook_env
        bundle = work_dir / "bundle.mthds"
        bundle.write_text("[method]\nname = 'test'\n")
        _make_stub(
            bin_dir / "plxt",
            '#!/bin/bash\nif [[ "$1" == "lint" ]]; then echo "bad toml syntax" >&2; exit 1; fi\nexit 0\n',
        )
        stdin = _post_tool_use_json(_patch_envelope(("Update File", str(bundle))))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "lint" in parsed["reason"].lower()
        assert "bad toml syntax" in parsed["reason"]

    # --- Stage 2: plxt fmt ---

    def test_all_stages_pass_no_output(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """All stages pass produces no stdout."""
        bin_dir, work_dir, env = hook_env
        bundle = work_dir / "bundle.mthds"
        bundle.write_text("[method]\nname = 'test'\n")
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())
        stdin = _post_tool_use_json(_patch_envelope(("Update File", str(bundle))))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""
        # Both lint and fmt should have run for the single file.
        log = Path(env["PLXT_LOG"]).read_text().splitlines()
        assert any(line.startswith("lint ") and str(bundle) in line for line in log)
        assert any(line.startswith("fmt ") and str(bundle) in line for line in log)

    # --- Multi-file apply_patch ---

    def test_multi_file_patch_validates_each_mthds(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A single apply_patch touching multiple .mthds files runs plxt against each one."""
        bin_dir, work_dir, env = hook_env
        bundle_a = work_dir / "a.mthds"
        bundle_b = work_dir / "b.mthds"
        non_mthds = work_dir / "README.md"
        for path in (bundle_a, bundle_b, non_mthds):
            path.write_text("[method]\nname = 't'\n")
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())

        stdin = _post_tool_use_json(
            _patch_envelope(
                ("Update File", str(bundle_a)),
                ("Add File", str(bundle_b)),
                ("Update File", str(non_mthds)),
            )
        )
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        log = Path(env["PLXT_LOG"]).read_text().splitlines()
        lint_targets = {line.split(" ", 1)[1] for line in log if line.startswith("lint ")}
        assert str(bundle_a) in lint_targets
        assert str(bundle_b) in lint_targets
        assert str(non_mthds) not in lint_targets

    def test_rename_validates_destination(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A rename emits `*** Update File: src` and `*** Move to: dest`. Only `dest` exists
        after the patch, so only `dest` is linted (`src` is silently skipped).
        """
        bin_dir, work_dir, env = hook_env
        # Source no longer exists (was renamed); destination does.
        renamed = work_dir / "renamed.mthds"
        renamed.write_text("[method]\nname = 'r'\n")
        _make_stub(bin_dir / "plxt", _plxt_recording_stub())

        stdin = _post_tool_use_json(
            _patch_envelope(
                ("Update File", str(work_dir / "old.mthds")),
                ("Move to", str(renamed)),
            )
        )
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        log = Path(env["PLXT_LOG"]).read_text().splitlines()
        lint_targets = {line.split(" ", 1)[1] for line in log if line.startswith("lint ")}
        assert lint_targets == {str(renamed)}
