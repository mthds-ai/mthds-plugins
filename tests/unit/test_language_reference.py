"""Pin the corrections the MTHDS language reference and the agent guide carry against the standard and the runtime."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / "templates" / "skills" / "shared"
LANGUAGE_REFERENCE = SHARED_DIR / "mthds-reference.md.j2"
AGENT_GUIDE = SHARED_DIR / "mthds-agent-guide.md.j2"


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

    def test_guide_prints_the_verdict_above_the_pending_heading(self) -> None:
        guide = AGENT_GUIDE.read_text(encoding="utf-8")
        block_start = guide.index("- **Not yet runnable**")
        assert guide.index("⚠️ This method is NOT yet runnable", block_start) < guide.index("  ## Pending signatures (N)", block_start)
