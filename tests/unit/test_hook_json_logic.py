"""Tests for the Stage 3 JSON decision logic in validate-mthds.sh hook.

Extracts the inline Node.js script from the generated hook and runs it
directly with crafted error JSON payloads, verifying each decision branch.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = REPO_ROOT / "mthds" / "hooks" / "validate-mthds.sh"


def _extract_stage3_js() -> str:
    """Extract the inline Node.js script from Stage 3 of the hook."""
    content = HOOK_SCRIPT.read_text()
    match = re.search(
        r'node -e "\n(.*?)\n" "\$FILE_PATH" "\$EXIT_CODE" "\$ERR_JSON"[^\n]*',
        content,
        re.DOTALL,
    )
    assert match, f"Could not extract Stage 3 Node.js script from {HOOK_SCRIPT}"
    return match.group(1)


def _run_stage3(
    js_code: str,
    err_json: str,
    file_path: str = "/tmp/test.mthds",
) -> subprocess.CompletedProcess[str]:
    """Run the Stage 3 decision logic with given error JSON."""
    return subprocess.run(
        ["node", "-e", js_code, file_path, "1", err_json],
        capture_output=True,
        text=True,
        timeout=10,
    )


# --- Error payloads ---

INVALID_JSON = "this is not json"

JSON_NO_ERROR_KEY = json.dumps({"message": "something"})

JSON_CONFIG_DOMAIN = json.dumps(
    {
        "error": True,
        "error_domain": "config",
        "message": "Missing config file",
        "hint": "Run mthds init",
    }
)

JSON_RUNTIME_DOMAIN = json.dumps(
    {
        "error": True,
        "error_domain": "runtime",
        "message": "Connection failed",
    }
)

JSON_VALIDATION_ERRORS = json.dumps(
    {
        "error": True,
        "error_domain": "input",
        "message": "Validation failed",
        "validation_errors": [
            {"pipe_code": "pipe_a", "message": "Missing required field"},
            {"pipe_code": "pipe_b", "message": "Invalid type"},
        ],
    }
)

JSON_VALIDATION_DEDUP = json.dumps(
    {
        "error": True,
        "error_domain": "input",
        "message": "Validation failed",
        "validation_errors": [
            {"pipe_code": "pipe_a", "message": "Error 1"},
            {"pipe_code": "pipe_a", "message": "Error 2"},
        ],
    }
)

JSON_MISSING_PIPE_CODE = json.dumps(
    {
        "error": True,
        "error_domain": "input",
        "message": "Validation failed",
        "validation_errors": [
            {"message": "Error without pipe_code"},
        ],
    }
)

JSON_DRY_RUN_ERROR = json.dumps(
    {
        "error": True,
        "error_domain": "input",
        "message": "Dry-run failed",
        "dry_run_error": "Could not resolve model",
        "hint": "Check your config",
    }
)

JSON_OTHER_INPUT_ERROR = json.dumps(
    {
        "error": True,
        "error_domain": "input",
        "error_type": "parse_error",
        "message": "Could not parse bundle",
        "hint": "Check TOML syntax",
    }
)


class TestStage3JsonLogic:
    """Unit tests for the Stage 3 Node.js JSON decision logic in validate-mthds.sh."""

    @pytest.fixture(scope="class")
    def js_code(self) -> str:
        """Extract the JS script once for all tests in this class."""
        return _extract_stage3_js()

    # --- Malformed input: warn and pass ---

    @pytest.mark.parametrize(
        "topic, err_json",
        [
            ("invalid JSON", INVALID_JSON),
            ("empty string", ""),
            ("JSON without .error key", JSON_NO_ERROR_KEY),
        ],
    )
    def test_malformed_input_warns_and_passes(self, js_code: str, topic: str, err_json: str) -> None:
        """Malformed or unexpected error JSON warns on stderr, does not block."""
        result = _run_stage3(js_code, err_json)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "unexpected output" in result.stderr

    # --- Non-blocking errors: warn on stderr ---

    @pytest.mark.parametrize(
        "topic, err_json, expect_stderr",
        [
            ("config domain", JSON_CONFIG_DOMAIN, "Missing config file"),
            ("runtime domain", JSON_RUNTIME_DOMAIN, "Connection failed"),
            ("dry-run error", JSON_DRY_RUN_ERROR, "Could not resolve model"),
            ("other input error", JSON_OTHER_INPUT_ERROR, "parse_error"),
        ],
    )
    def test_non_blocking_errors_warn(self, js_code: str, topic: str, err_json: str, expect_stderr: str) -> None:
        """Non-blocking error types produce warnings on stderr without blocking."""
        result = _run_stage3(js_code, err_json)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert expect_stderr in result.stderr

    # --- Hints ---

    @pytest.mark.parametrize(
        "topic, err_json, expect_hint",
        [
            ("config domain hint", JSON_CONFIG_DOMAIN, "Run mthds init"),
            ("dry-run hint", JSON_DRY_RUN_ERROR, "Check your config"),
            ("other input hint", JSON_OTHER_INPUT_ERROR, "Check TOML syntax"),
        ],
    )
    def test_hints_included_in_warnings(self, js_code: str, topic: str, err_json: str, expect_hint: str) -> None:
        """Hint text is included in stderr warnings when present."""
        result = _run_stage3(js_code, err_json)
        assert expect_hint in result.stderr

    # --- Validation errors: block ---

    def test_validation_errors_block(self, js_code: str) -> None:
        """Validation errors produce a block decision with pipe names and details."""
        result = _run_stage3(js_code, JSON_VALIDATION_ERRORS)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "2 validation error(s)" in parsed["reason"]
        assert "pipe_a" in parsed["reason"]
        assert "pipe_b" in parsed["reason"]
        assert "Missing required field" in parsed["reason"]
        assert "Invalid type" in parsed["reason"]

    def test_validation_errors_dedup_pipe_names(self, js_code: str) -> None:
        """Duplicate pipe codes appear only once in the pipe summary."""
        result = _run_stage3(js_code, JSON_VALIDATION_DEDUP)
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        # The "in pipe(s): ..." prefix should list pipe_a once
        first_line = parsed["reason"].split("\n")[0]
        assert first_line.count("pipe_a") == 1

    def test_validation_errors_missing_pipe_code_uses_unknown(self, js_code: str) -> None:
        """Validation errors without pipe_code fall back to 'unknown'."""
        result = _run_stage3(js_code, JSON_MISSING_PIPE_CODE)
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "unknown" in parsed["reason"]

    def test_block_reason_includes_file_path(self, js_code: str) -> None:
        """Block reason includes the file path passed to the script."""
        result = _run_stage3(js_code, JSON_VALIDATION_ERRORS, file_path="/my/bundle.mthds")
        parsed = json.loads(result.stdout.strip())
        assert "/my/bundle.mthds" in parsed["reason"]
