"""Integration tests for the validate-mthds.sh hook with mocked CLI tools.

Creates stub scripts for plxt and mthds-agent on an isolated PATH,
then runs the full hook pipeline and verifies stdout/stderr decisions.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = REPO_ROOT / "mthds" / "hooks" / "validate-mthds.sh"


def _make_stub(path: Path, content: str) -> None:
    """Create an executable stub script."""
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _post_tool_use_json(file_path: str) -> str:
    """Build a PostToolUse hook JSON payload."""
    return json.dumps({"tool_input": {"file_path": file_path}})


def _isolated_env(bin_dir: Path) -> dict[str, str]:
    """Build an isolated env where only bin_dir + system dirs are on PATH.

    Symlinks node into bin_dir so it's reachable. Excludes directories like
    /usr/local/bin and npm global paths where real plxt/mthds-agent might live,
    ensuring tools are only found if explicitly stubbed into bin_dir.
    """
    node_path = shutil.which("node")
    if node_path and not (bin_dir / "node").exists():
        (bin_dir / "node").symlink_to(node_path)
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
    }


def _run_hook(stdin_data: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the hook script with given stdin and environment."""
    return subprocess.run(
        ["bash", str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _stub_mthds_agent_validate(bin_dir: Path, stderr_content: str, exit_code: int) -> None:
    """Create an mthds-agent stub that outputs given stderr on 'validate' and exits."""
    stderr_file = bin_dir / "mthds_agent_stderr.txt"
    stderr_file.write_text(stderr_content)
    _make_stub(
        bin_dir / "mthds-agent",
        f'#!/bin/bash\nif [[ "$1" == "validate" ]]; then cat "{stderr_file}" >&2; exit {exit_code}; fi\nexit 0\n',
    )


class TestHookValidateMthds:
    """Integration tests for the full validate-mthds.sh hook pipeline."""

    @pytest.fixture()
    def hook_env(self, tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
        """Create an isolated environment with a .mthds file and restricted PATH.

        Returns:
            Tuple of (bin_dir, mthds_file, env).
        """
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mthds_file = tmp_path / "test.mthds"
        mthds_file.write_text("[method]\nname = 'test'\n")
        env = _isolated_env(bin_dir)
        return bin_dir, mthds_file, env

    def _add_all_tools(
        self,
        bin_dir: Path,
        plxt: str = "#!/bin/bash\nexit 0\n",
        mthds_agent: str = "#!/bin/bash\nexit 0\n",
    ) -> None:
        """Add both plxt and mthds-agent stubs."""
        _make_stub(bin_dir / "plxt", plxt)
        _make_stub(bin_dir / "mthds-agent", mthds_agent)

    # --- Guard tests: early exit paths ---

    def test_non_mthds_file_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]], tmp_path: Path) -> None:
        """Non-.mthds file produces no output."""
        _, _, env = hook_env
        stdin = _post_tool_use_json(str(tmp_path / "test.py"))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_missing_file_path_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Missing file_path in JSON input produces no output."""
        _, _, env = hook_env
        stdin = json.dumps({"tool_input": {}})
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_nonexistent_file_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]], tmp_path: Path) -> None:
        """File path pointing to nonexistent file produces no output."""
        _, _, env = hook_env
        stdin = _post_tool_use_json(str(tmp_path / "ghost.mthds"))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_malformed_stdin_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Malformed JSON on stdin does not crash the hook."""
        _, _, env = hook_env
        result = _run_hook("this is not json at all", env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_empty_stdin_passes_silently(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Empty stdin does not crash the hook."""
        _, _, env = hook_env
        result = _run_hook("", env)
        assert result.returncode == 0
        assert result.stdout == ""

    # --- Missing tools ---

    def test_missing_plxt_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Missing plxt blocks with install instructions."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "mthds-agent", "#!/bin/bash\nexit 0\n")
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "plxt" in parsed["reason"]

    def test_missing_mthds_agent_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Missing mthds-agent blocks with install instructions."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "mthds-agent" in parsed["reason"]

    def test_both_tools_missing_blocks_with_both(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Both tools missing lists both in the block reason."""
        _, mthds_file, env = hook_env
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "plxt" in parsed["reason"]
        assert "mthds-agent" in parsed["reason"]

    # --- Stage 1: plxt lint ---

    def test_lint_failure_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """plxt lint failure produces a block with lint output."""
        bin_dir, mthds_file, env = hook_env
        self._add_all_tools(
            bin_dir,
            plxt='#!/bin/bash\nif [[ "$1" == "lint" ]]; then echo "bad toml syntax" >&2; exit 1; fi\nexit 0\n',
        )
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "lint" in parsed["reason"].lower()
        assert "bad toml syntax" in parsed["reason"]

    # --- Stage 2: plxt fmt ---

    def test_fmt_failure_warns_but_continues(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """plxt fmt failure warns on stderr but validation continues."""
        bin_dir, mthds_file, env = hook_env
        self._add_all_tools(
            bin_dir,
            plxt='#!/bin/bash\nif [[ "$1" == "fmt" ]]; then echo "fmt error" >&2; exit 1; fi\nexit 0\n',
        )
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert "block" not in result.stdout
        assert "plxt fmt failed" in result.stderr

    # --- Stage 3: mthds-agent validate ---

    def test_all_stages_pass_no_output(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """All stages pass produces no stdout."""
        bin_dir, mthds_file, env = hook_env
        self._add_all_tools(bin_dir)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_validation_errors_block(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Validation errors from mthds-agent produce a block decision."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        _stub_mthds_agent_validate(
            bin_dir,
            json.dumps(
                {
                    "error": True,
                    "error_domain": "input",
                    "message": "Validation failed",
                    "validation_errors": [
                        {"pipe_code": "extract_info", "message": "Missing required field 'source'"},
                    ],
                }
            ),
            exit_code=1,
        )
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "extract_info" in parsed["reason"]
        assert "Missing required field" in parsed["reason"]

    def test_config_error_warns_not_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Config domain error warns on stderr without blocking."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        _stub_mthds_agent_validate(
            bin_dir,
            json.dumps(
                {
                    "error": True,
                    "error_domain": "config",
                    "message": "Config not found",
                    "hint": "Run mthds init",
                }
            ),
            exit_code=1,
        )
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "Config not found" in result.stderr
        assert "Run mthds init" in result.stderr

    def test_unexpected_stderr_warns_not_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Non-JSON stderr from mthds-agent warns without blocking."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        _stub_mthds_agent_validate(bin_dir, "segfault or something", exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "unexpected output" in result.stderr
