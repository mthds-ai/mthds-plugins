"""Tests for the version_ge helper in bin/install-codex.sh.

Sources the shell function into bash and exercises it across semver
comparison cases. This regression-tests the fix for the macOS BSD sort
incompatibility (sort -V is GNU-only), which previously broke install on
macOS by making version_ge always return false.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "bin" / "install-codex.sh"


def _run_version_ge(left: str, right: str) -> bool:
    """Source install-codex.sh and call version_ge LEFT RIGHT.

    Returns True if the function exits 0 (LEFT >= RIGHT), False otherwise.
    The script's main() is guarded by `[ "${BASH_SOURCE[0]}" = "$0" ]`-style
    conventions in many installers; here we defensively extract only the
    function definition to avoid side effects.
    """
    content = INSTALL_SCRIPT.read_text()
    start = content.index("version_ge() {")
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
    func_src = content[start:end]

    script = f"{func_src}\nversion_ge {left} {right}\n"
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
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
