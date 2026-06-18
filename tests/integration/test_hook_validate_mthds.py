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


def _stub_mthds_agent_validate(bin_dir: Path, stderr_content: str = "", exit_code: int = 0, stdout_content: str = "") -> None:
    """Create an mthds-agent stub that emits given stdout/stderr on 'validate' and exits.

    The refactored hook reads the STRUCTURED JSON verdict: a valid bundle's success
    envelope (is_valid:true) rides stdout; an invalid/no-verdict error envelope rides
    stderr.
    """
    stderr_file = bin_dir / "mthds_agent_stderr.txt"
    stderr_file.write_text(stderr_content)
    stdout_file = bin_dir / "mthds_agent_stdout.txt"
    stdout_file.write_text(stdout_content)
    _make_stub(
        bin_dir / "mthds-agent",
        f'#!/bin/bash\nif [[ "$1" == "validate" ]]; then cat "{stdout_file}"; cat "{stderr_file}" >&2; exit {exit_code}; fi\nexit 0\n',
    )


def _stub_mthds_agent_validate_success(bin_dir: Path, stdout_json: str) -> Path:
    """Create an mthds-agent stub whose 'validate' prints JSON on stdout and exits 0.

    Models the lenient success envelope (--format json). Records the argv it was
    invoked with to mthds_agent_args.txt so a test can assert the invocation shape
    (--allow-signatures, the pinned format streams, -L <library dir>).

    Returns:
        Path to the args file the stub writes its argv to.
    """
    stdout_file = bin_dir / "mthds_agent_stdout.json"
    stdout_file.write_text(stdout_json)
    args_file = bin_dir / "mthds_agent_args.txt"
    _make_stub(
        bin_dir / "mthds-agent",
        f'#!/bin/bash\nif [[ "$1" == "validate" ]]; then printf "%s\\n" "$@" > "{args_file}"; cat "{stdout_file}"; exit 0; fi\nexit 0\n',
    )
    return args_file


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
        # Realistic default: a valid mthds-agent emits the structured success envelope
        # (is_valid:true) on stdout for `validate` — which the hook now requires to pass.
        mthds_agent: str = '#!/bin/bash\nif [[ "$1" == "validate" ]]; then echo \'{"success": true, "is_valid": true}\'; fi\nexit 0\n',
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

    def test_non_mthds_file_passes_silently_when_node_broken(self, hook_env: tuple[Path, Path, dict[str, str]], tmp_path: Path) -> None:
        """Non-.mthds file must pass silently even if `node` is broken.

        Regression: previously, the hook called the Node.js JSON parser before
        checking the .mthds extension, so any Node.js failure produced a block
        decision against unrelated files. The .mthds pre-filter now runs first.
        """
        bin_dir, _, env = hook_env
        (bin_dir / "node").unlink()
        _make_stub(bin_dir / "node", "#!/bin/bash\nexit 1\n")
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
    # The hook reads the STRUCTURED verdict from JSON (--format json /
    # --error-format json): a valid bundle's success envelope (is_valid:true)
    # rides stdout and PASSES even when not yet runnable; an invalid/no-verdict
    # error envelope rides stderr, where the hook reads error_domain to BLOCK
    # (input/unknown) or emit additionalContext (config/runtime).

    def test_all_stages_pass_no_output(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """All stages pass produces no stdout."""
        bin_dir, mthds_file, env = hook_env
        self._add_all_tools(bin_dir)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_valid_verdict_passes(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A success envelope (is_valid:true) on stdout → pass, no output."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps({"success": True, "is_valid": True, "is_runnable": True, "pending_signatures": [], "validated_pipes": []})
        _stub_mthds_agent_validate(bin_dir, stdout_content=envelope, exit_code=0)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_valid_but_not_runnable_passes_with_nudge(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A valid-but-not-runnable bundle (is_valid:true on stdout, exit 1 from the strict
        signature gate) PASSES — validity, not runnability, is what the hook gates — and emits
        the non-blocking pending_signatures nudge even though the CLI exited non-zero (the hook
        reads is_valid from stdout, not the exit code)."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps({"is_valid": True, "is_runnable": False, "pending_signatures": ["dom.todo"], "validated_pipes": []})
        # The signature gate exits non-zero while the success envelope rides stdout.
        _stub_mthds_agent_validate(bin_dir, stdout_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert "decision" not in parsed  # non-blocking
        assert "dom.todo" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_exit_zero_without_structured_envelope_blocks(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A clean exit 0 with NO structured success envelope (e.g. an old/regressed mthds-agent
        emitting no/garbled JSON) → BLOCK, not a silent pass: the hook requires the machine-readable
        verdict, so it fails safe for a write gate."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        _stub_mthds_agent_validate(bin_dir, stdout_content="", exit_code=0)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "no structured success envelope" in parsed["reason"]

    def test_input_domain_blocks_with_structured_reason(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A JSON error envelope with error_domain: input → BLOCK with a reason built from
        the message + validation_errors."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {
                "error": True,
                "error_type": "ValidateBundleError",
                "is_valid": False,
                "error_domain": "input",
                "message": "Validation error(s): Missing required field 'source' in pipe 'extract_info'",
                "validation_errors": [{"category": "pipe_validation", "message": "Missing required field 'source'", "pipe_code": "extract_info"}],
            }
        )
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "extract_info" in parsed["reason"]
        assert "Missing required field" in parsed["reason"]
        assert str(mthds_file) in parsed["reason"]

    def test_no_error_domain_defaults_to_block(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A JSON error envelope without error_domain → BLOCK (safety default)."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {"error": True, "error_type": "LibraryError", "is_valid": False, "message": "Pipe 'build_scorecard' not found. Check for typos."}
        )
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "build_scorecard" in parsed["reason"]

    def test_internal_fields_not_leaked_in_block_reason(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Internal envelope fields (error_source stack frames) never reach the block reason."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {
                "error": True,
                "is_valid": False,
                "message": "Pipe not found",
                "error_source": ["LibraryError @ /usr/local/lib/pipelex/libraries/library.py:140"],
            }
        )
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "library.py:140" not in parsed["reason"]
        assert "error_source" not in parsed["reason"]

    def test_config_domain_emits_additional_context(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A JSON error envelope with error_domain: config → exit 0 with additionalContext."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {
                "error": True,
                "error_type": "TelemetryConfigValidationError",
                "error_domain": "config",
                "message": "Telemetry config missing required field",
            }
        )
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert "decision" not in parsed
        hook_output = parsed["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PostToolUse"
        ctx = hook_output["additionalContext"]
        assert "config domain" in ctx
        assert "do not edit the file" in ctx
        assert "Telemetry config missing required field" in ctx
        assert str(mthds_file) in ctx
        assert "domain=config" in result.stderr

    def test_runtime_domain_emits_additional_context(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A JSON error envelope with error_domain: runtime → additionalContext + stderr warning."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {"error": True, "error_type": "PipeRunError", "error_domain": "runtime", "message": "Pipeline execution failed: connection refused"}
        )
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert "decision" not in parsed
        assert "runtime domain" in parsed["hookSpecificOutput"]["additionalContext"]
        assert "domain=runtime" in result.stderr

    def test_empty_stderr_blocks_generic(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """Non-zero exit with no structured envelope on either stream → BLOCK generic."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        _stub_mthds_agent_validate(bin_dir, stderr_content="", exit_code=2)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["decision"] == "block"
        assert "no structured error envelope" in parsed["reason"]
        assert "exited 2" in parsed["reason"]

    def test_long_message_truncated_in_additional_context(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """A config-domain message >9500 chars → additionalContext is truncated with marker."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        long_message = "x" * 12000
        envelope = json.dumps({"error": True, "error_domain": "config", "message": long_message})
        _stub_mthds_agent_validate(bin_dir, stderr_content=envelope, exit_code=1)
        stdin = _post_tool_use_json(str(mthds_file))
        result = _run_hook(stdin, env)
        assert result.returncode == 0
        ctx = json.loads(result.stdout.strip())["hookSpecificOutput"]["additionalContext"]
        assert "[truncated," in ctx
        assert "chars omitted]" in ctx
        # additionalContext stays within the cap + header + truncation marker.
        assert len(ctx) < 10000

    # --- Stage 3 lenient validation (--allow-signatures) ---
    # The hook validates leniently so recursive/stepwise builds aren't blocked
    # mid-construction, and on a valid verdict reads pending_signatures from the
    # JSON success envelope to emit a non-blocking nudge. Errors are read from the
    # JSON error envelope on stderr (--error-format json) by the classifier tests
    # above; --allow-signatures does not change that path.

    def test_validate_invoked_with_allow_signatures_and_library_dir(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """R1/N3: Stage 3 invokes validate leniently against the library dir.

        Proves the template actually passes --allow-signatures, the pinned
        format streams (--format json / --error-format json), and -L <parent>/
        — the invocation shape recursive builds depend on, and the granularity
        that lets a domain-only child member file (D2) validate against the whole
        assembled library on every save.
        """
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        # A valid success envelope so the hook takes the is_valid:true pass path
        # after recording the invocation argv.
        args_file = _stub_mthds_agent_validate_success(bin_dir, json.dumps({"is_valid": True}))
        result = _run_hook(_post_tool_use_json(str(mthds_file)), env)
        assert result.returncode == 0
        recorded = args_file.read_text().splitlines()
        assert recorded[:3] == ["validate", "bundle", str(mthds_file)]
        assert "--allow-signatures" in recorded
        assert "--format" in recorded
        assert "json" in recorded
        assert "--error-format" in recorded
        assert "-L" in recorded
        assert f"{mthds_file.parent}/" in recorded

    def test_signature_free_success_no_nudge(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """R1: signature-free bundle (no pending_signatures key) → no nudge, no stdout.

        Lenient validation of a signature-free bundle is identical to strict:
        the success envelope carries no pending_signatures, so the hook stays
        silent exactly as it did before --allow-signatures was added.
        """
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps({"is_valid": True, "validated_pipes": ["foo"], "total_pipes": 1})
        _stub_mthds_agent_validate_success(bin_dir, envelope)
        result = _run_hook(_post_tool_use_json(str(mthds_file)), env)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_pending_signatures_emit_nudge(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """N1: leftover signatures → non-blocking additionalContext listing them."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps(
            {
                "is_valid": True,
                "is_runnable": False,
                "pending_signatures": ["research_brief.find_key_findings", "research_brief.assemble_brief"],
            }
        )
        _stub_mthds_agent_validate_success(bin_dir, envelope)
        result = _run_hook(_post_tool_use_json(str(mthds_file)), env)
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert "decision" not in parsed  # non-blocking
        hook_output = parsed["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PostToolUse"
        ctx = hook_output["additionalContext"]
        assert "find_key_findings" in ctx
        assert "assemble_brief" in ctx

    def test_empty_pending_signatures_no_nudge(self, hook_env: tuple[Path, Path, dict[str, str]]) -> None:
        """N2: complete bundle (pending_signatures == []) → no nudge, no stdout."""
        bin_dir, mthds_file, env = hook_env
        _make_stub(bin_dir / "plxt", "#!/bin/bash\nexit 0\n")
        envelope = json.dumps({"is_valid": True, "is_runnable": True, "pending_signatures": []})
        _stub_mthds_agent_validate_success(bin_dir, envelope)
        result = _run_hook(_post_tool_use_json(str(mthds_file)), env)
        assert result.returncode == 0
        assert result.stdout == ""
