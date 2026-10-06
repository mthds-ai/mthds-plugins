"""Pin what the MTHDS language reference, the agent guide and mthds-explain teach against the standard and the runtime."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / "templates" / "skills" / "shared"
LANGUAGE_REFERENCE = SHARED_DIR / "mthds-reference.md.j2"
AGENT_GUIDE = SHARED_DIR / "mthds-agent-guide.md.j2"
EXPLAIN_SKILL = REPO_ROOT / "templates" / "skills" / "mthds-explain" / "SKILL.md.j2"


class TestLanguageReference:
    @property
    def reference(self) -> str:
        return LANGUAGE_REFERENCE.read_text(encoding="utf-8")

    def test_bare_string_field_is_required(self) -> None:
        body = self.reference
        assert "**A bare string is a required text field.**" in body
        assert "Simple text field (optional)" not in body

    def test_domain_qualified_pipe_reference_is_valid(self) -> None:
        body = self.reference
        assert "Both forms are valid wherever a concept or a pipe is referenced" in body
        assert "will fail validation" not in body

    def test_model_lookup_uses_the_cli(self) -> None:
        body = self.reference
        assert "mthds-agent models --type <category>" in body
        assert "mthds-agent check-model '<reference>' --type <category>" in body
        assert "mthds_models" not in body

    def test_choices_field_omits_type(self) -> None:
        body = self.reference
        assert "A field with `choices` omits `type`." in body
        assert re.search(r'type = "\w+", choices =', body) is None

    def test_input_names_are_plain(self) -> None:
        body = self.reference
        assert "**An input name is a plain `snake_case` identifier**, matching `[a-z][a-z0-9_]*`" in body
        assert (
            'A key such as `"invoice.total" = "Number"` does not declare a field of `invoice`: validation refuses it as `invalid_input_name`.' in body
        )
        assert re.search(r'inputs\s*=\s*\{[^}\n]*"[a-z_]+\.[a-z_.]+"\s*=', body) is None

    def test_binding_step_is_taught(self) -> None:
        body = self.reference
        assert "\n#### Binding steps\n" in body
        assert "Binding steps need `pipelex` 0.75.0 or later" in body
        assert '    { from = "invoice.total", result = "total_amount" },\n    { pipe = "write_receipt", result = "receipt" },' in body
        assert 'inputs      = { total_amount = "Number" }' in body
        assert "A binding step has exactly two fields, both required" in body
        assert "is refused as `binding_step_invalid`" in body
        assert "is refused as `binding_path_unresolved`" in body

    def test_binding_absence_rule_is_taught(self) -> None:
        body = self.reference
        assert "\n#### Absence through a binding step\n" in body
        assert "a single result may be absent when its root may be absent" in body
        assert "or when its path walks a field that is not `required` and has no `default_value`" in body
        assert "or validation refuses it as `optional_not_handled`" in body
        assert '    { from = "delivery.note", result = "courier_note" },' in body
        assert 'inputs      = { address = "Text", courier_note = "Text?" }' in body

    def test_dotted_batch_over_is_a_binding_then_a_batch(self) -> None:
        body = self.reference
        assert "\n#### Dotted `batch_over`\n" in body
        assert "The step is then a binding followed by a batch" in body
        assert '{ pipe = "write_index_line", batch_over = "catalog.pages", batch_as = "page", result = "index_lines" }' in body
        assert "a binding step or a dotted `batch_over` in `branches` is refused as `binding_step_invalid`" in body
        assert "`batch_over` supports dotted paths" not in body

    def test_bound_prefix_is_reserved(self) -> None:
        body = self.reference
        assert "**Names starting with `_bound_` are reserved**" in body
        assert "a `PipeBatch`'s `input_item_name` must not start with `_bound_`, or they are refused as `invalid_input_name`" in body

    def test_conditional_block_stands_on_its_own_line(self) -> None:
        body = self.reference
        assert "| Conditional block, for an optional input (put on its own line). |" in body
        assert re.search(r"^@\?courier_note$", body, re.MULTILINE) is not None
        assert re.search(r"\S[ \t]+@\?courier_note", body) is None

    def test_explain_reads_a_pipe_batch_by_its_own_fields(self) -> None:
        explain = EXPLAIN_SKILL.read_text(encoding="utf-8")
        assert "For **PipeBatch**: identify the list (`input_list_name`) and the item name (`input_item_name`)" in explain
        assert "then the branch pipe (`branch_pipe_code`) applied to each item" in explain
        assert "identify `batch_over` and `batch_as`" not in explain
        assert "a step carrying `from` is a binding step" in explain

    def test_guide_prints_the_verdict_above_the_pending_heading(self) -> None:
        guide = AGENT_GUIDE.read_text(encoding="utf-8")
        block_start = guide.index("- **Not yet runnable**")
        assert guide.index("⚠️ This method is NOT yet runnable", block_start) < guide.index("  ## Pending signatures (N)", block_start)
