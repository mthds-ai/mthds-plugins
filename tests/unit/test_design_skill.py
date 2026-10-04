"""Pin the design skill's construction model: direct or stepwise, inferred, and gated by strict validation.

`mthds-design` writes a bundle's TOML directly and lets `mthds-agent validate bundle`
judge it, as `pipelex-plugins`' `pipelex-design` does.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_TEMPLATE = REPO_ROOT / "templates" / "skills" / "mthds-design" / "SKILL.md.j2"
STEPWISE_REFERENCE = REPO_ROOT / "skills" / "mthds-design" / "references" / "stepwise.md"


class TestDesignSkill:
    @property
    def design(self) -> str:
        return DESIGN_TEMPLATE.read_text(encoding="utf-8")

    @property
    def stepwise(self) -> str:
        return STEPWISE_REFERENCE.read_text(encoding="utf-8")

    def test_direct_mode_covers_shallow_concrete_graphs(self) -> None:
        body = self.design
        assert "the graph is one concrete operator; or one top-level controller whose children are concrete leaf operators" in body
        assert "every pipe can be concrete in the first coherent artifact" in body
        assert "Include **no temporary `PipeSignature` declarations**" in body
        assert "One controller is a strong fast-path signal, not a rule" in body

    def test_mode_is_inferred_never_asked(self) -> None:
        assert "**Never ask the user to choose the workflow.**" in self.design

    def test_direct_writes_with_the_file_tools(self) -> None:
        assert "Write it with your agent's file tools, never through the shell" in self.design

    def test_runnable_gate_is_strict_validation(self) -> None:
        body = self.design
        assert "mthds-agent validate bundle mthds-wip/<bundle_dir>/bundle.mthds -L mthds-wip/<bundle_dir>/ --graph" in body
        assert "validation **without** `--allow-signatures` must pass" in body

    def test_stepwise_validates_leniently_then_strictly(self) -> None:
        body = self.stepwise
        assert "--allow-signatures --graph" in body
        assert "Every expansion adds exactly one new `<code>.mthds` definition file" in body
        assert "validate once more **without** `--allow-signatures`" in body

    def test_stepwise_reads_the_backlog_from_the_verdict(self) -> None:
        body = self.stepwise
        assert "## Pending signatures (N)" in body
        assert "never hand-track it" in body

    def test_stepwise_describes_the_verdict_in_printed_order(self) -> None:
        body = self.stepwise
        assert body.index("NOT yet runnable") < body.index("## Pending signatures (N)")
