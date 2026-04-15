"""Tests for the version_ge helper in bin/install-codex.sh.

Sources the shell function into bash and exercises it across semver
comparison cases. This regression-tests the fix for the macOS BSD sort
incompatibility (sort -V is GNU-only), which previously broke install on
macOS by making version_ge always return false.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "bin" / "install-codex.sh"


def _extract_shell_function(function_name: str) -> str:
    """Extract a shell function definition from install-codex.sh."""
    content = INSTALL_SCRIPT.read_text()
    start = content.index(f"{function_name}() {{")
    depth = 0
    end = start
    for index_char, char in enumerate(content[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index_char + 1
                break
    return content[start:end]


def _run_shell_function(function_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run an extracted shell function from install-codex.sh without side effects."""
    func_src = _extract_shell_function(function_name)
    quoted_args = " ".join(shlex.quote(arg) for arg in args)
    script = f"{func_src}\n{function_name} {quoted_args}\n"
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_version_ge(left: str, right: str) -> bool:
    """Source install-codex.sh and call version_ge LEFT RIGHT.

    Returns True if the function exits 0 (LEFT >= RIGHT), False otherwise.
    The script's main() is guarded by `[ "${BASH_SOURCE[0]}" = "$0" ]`-style
    conventions in many installers; here we defensively extract only the
    function definition to avoid side effects.
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


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for installer marketplace rendering")
class TestRenderRepoLocalMarketplace:
    def test_rewrites_source_path_and_preserves_policy(self, tmp_path: Path) -> None:
        source = tmp_path / "marketplace.json"
        source.write_text(
            json.dumps(
                {
                    "name": "mthds-plugins",
                    "interface": {"displayName": "MTHDS Plugins"},
                    "plugins": [
                        {
                            "name": "mthds",
                            "source": {"source": "local", "path": "./mthds-codex"},
                            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                            "category": "Developer Tools",
                        }
                    ],
                }
            )
        )

        result = _run_shell_function("render_repo_local_marketplace", str(source))
        assert result.returncode == 0, result.stderr

        rendered = json.loads(result.stdout)
        assert rendered["plugins"][0]["source"]["path"] == "./plugins/mthds"
        assert rendered["plugins"][0]["policy"]["authentication"] == "ON_INSTALL"
        assert rendered["plugins"][0]["category"] == "Developer Tools"
