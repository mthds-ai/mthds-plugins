"""Tests for shell helpers in bin/install-codex.sh.

Sources the version_ge function into bash and exercises it across semver
comparison cases (regressions the fix for BSD `sort -V` incompatibility).

Also exercises the merge_post_tool_use_hook function, which writes the
PostToolUse(apply_patch) entry into ~/.codex/hooks.json idempotently and
migrates legacy Stop entries left over from pre-0.9.0 installs.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "bin" / "install-codex.sh"


def _extract_shell_function(function_name: str) -> str:
    """Extract a shell function definition from install-codex.sh.

    The function body is parsed by tracking brace depth, but the
    `merge_post_tool_use_hook` body contains a heredoc whose `NODE` close
    line is followed by an unindented `}` that breaks naive matching. We
    skip lines inside heredocs to keep the depth count accurate.
    """
    content = INSTALL_SCRIPT.read_text()
    start = content.index(f"{function_name}() {{")
    lines = content[start:].splitlines(keepends=True)
    captured: list[str] = []
    depth = 0
    in_heredoc = False
    heredoc_terminator: str | None = None

    for line in lines:
        captured.append(line)
        if in_heredoc:
            if line.rstrip("\n") == heredoc_terminator:
                in_heredoc = False
                heredoc_terminator = None
            continue
        # Detect a `<<MARKER` or `<<'MARKER'` heredoc start on this line.
        stripped = line.rstrip("\n")
        if "<<" in stripped:
            after = stripped.split("<<", 1)[1].lstrip("-")
            after = after.strip().strip("'\"")
            terminator = after.split()[0] if after else ""
            if terminator and "$" not in terminator:
                in_heredoc = True
                heredoc_terminator = terminator
                continue

        for char in stripped:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return "".join(captured)
    msg = f"Could not find end of function `{function_name}` in {INSTALL_SCRIPT}"
    raise ValueError(msg)


def _run_shell_function(
    function_name: str,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an extracted shell function from install-codex.sh without side effects."""
    func_src = _extract_shell_function(function_name)
    quoted_args = " ".join(shlex.quote(arg) for arg in args)
    script = f"{func_src}\n{function_name} {quoted_args}\n"
    run_env = dict(os.environ)
    if env is not None:
        run_env.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
    )


def _run_version_ge(left: str, right: str) -> bool:
    """Source install-codex.sh and call version_ge LEFT RIGHT.

    Returns True if the function exits 0 (LEFT >= RIGHT), False otherwise.
    """
    result = _run_shell_function("version_ge", left, right)
    return result.returncode == 0


class TestVersionGe:
    @pytest.mark.parametrize(
        "left, right, expected",
        [
            ("1.2.3", "1.2.0", True),
            ("1.2.0", "1.2.3", False),
            ("1.2.3", "1.2.3", True),
            ("0.4.1", "0.4.0", True),
            ("0.4.0", "0.4.1", False),
            ("0.4.0", "0.4.0", True),
            ("2.0.0", "1.99.99", True),
            ("1.99.99", "2.0.0", False),
            ("1.10.0", "1.9.0", True),
            ("1.9.0", "1.10.0", False),
            ("1.2", "1.2.0", True),
            ("1.2.0", "1.2", True),
            ("10.0.0", "9.9.9", True),
        ],
    )
    def test_version_ge(self, left: str, right: str, expected: bool) -> None:
        assert _run_version_ge(left, right) is expected


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for the merge function")
class TestMergePostToolUseHook:
    """Verify ~/.codex/hooks.json merge: idempotency, legacy Stop migration, structure preservation."""

    def _hooks_file(self, home: Path) -> Path:
        return home / ".codex" / "hooks.json"

    def _invoke(self, home: Path) -> subprocess.CompletedProcess[str]:
        return _run_shell_function("merge_post_tool_use_hook", env={"HOME": str(home)})

    def _read_hooks(self, home: Path) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self._hooks_file(home).read_text()))

    def _post_tool_use(self, parsed: dict[str, object]) -> list[dict[str, object]]:
        hooks = cast(dict[str, object], parsed.get("hooks", {}))
        return cast(list[dict[str, object]], hooks.get("PostToolUse", []))

    def test_creates_fresh_hooks_file(self, tmp_path: Path) -> None:
        result = self._invoke(tmp_path)
        assert result.returncode == 0, result.stderr
        parsed = self._read_hooks(tmp_path)
        entries = self._post_tool_use(parsed)
        assert len(entries) == 1
        assert entries[0]["matcher"] == "apply_patch"
        hook_commands = cast(list[dict[str, object]], entries[0]["hooks"])
        assert "codex-validate-mthds" in str(hook_commands[0]["command"])

    def test_idempotent(self, tmp_path: Path) -> None:
        assert self._invoke(tmp_path).returncode == 0
        first = self._hooks_file(tmp_path).read_text()
        assert self._invoke(tmp_path).returncode == 0
        second = self._hooks_file(tmp_path).read_text()
        assert first == second

    def test_migrates_legacy_stop_entry(self, tmp_path: Path) -> None:
        """A pre-0.9.0 install left a Stop hook pointing at our script — it should be removed
        when the new PostToolUse entry is installed (otherwise it'd fork a no-op process every turn).
        """
        legacy = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/.codex/hooks/codex-validate-mthds.sh", "timeout": 30}]}]}}
        hooks_file = self._hooks_file(tmp_path)
        hooks_file.parent.mkdir(parents=True)
        hooks_file.write_text(json.dumps(legacy))

        result = self._invoke(tmp_path)
        assert result.returncode == 0, result.stderr
        parsed = self._read_hooks(tmp_path)
        hooks_section = cast(dict[str, object], parsed["hooks"])
        assert "Stop" not in hooks_section
        assert len(self._post_tool_use(parsed)) == 1

    def test_preserves_unrelated_hooks(self, tmp_path: Path) -> None:
        """Pre-existing hooks for other tools must survive the merge untouched."""
        existing = {
            "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "/usr/local/bin/audit-bash"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "/usr/local/bin/turn-end-notify"}]}],
            }
        }
        hooks_file = self._hooks_file(tmp_path)
        hooks_file.parent.mkdir(parents=True)
        hooks_file.write_text(json.dumps(existing))

        result = self._invoke(tmp_path)
        assert result.returncode == 0, result.stderr
        parsed = self._read_hooks(tmp_path)
        hooks_section = cast(dict[str, object], parsed["hooks"])
        pre_entries = cast(list[dict[str, object]], hooks_section.get("PreToolUse", []))
        assert pre_entries[0]["matcher"] == "Bash"
        stop_entries = cast(list[dict[str, object]], hooks_section.get("Stop", []))
        stop_commands = cast(list[dict[str, object]], stop_entries[0]["hooks"])
        assert "turn-end-notify" in str(stop_commands[0]["command"])
        assert len(self._post_tool_use(parsed)) == 1

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        hooks_file = self._hooks_file(tmp_path)
        hooks_file.parent.mkdir(parents=True)
        hooks_file.write_text("{not valid json")
        result = self._invoke(tmp_path)
        assert result.returncode != 0
        assert "Invalid JSON" in result.stderr
