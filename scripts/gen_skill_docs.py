#!/usr/bin/env python3
"""Generate SKILL.md from SKILL.md.j2 templates.

Renders all Jinja2 templates under skills/ and writes the corresponding
SKILL.md files. Both .j2 (source of truth) and .md (build artifact) are
checked into git.

Usage:
    python scripts/gen_skill_docs.py          # generate all SKILL.md files
    python scripts/gen_skill_docs.py --check  # verify .md files are fresh
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

# Must match CANONICAL_VERSION_PATTERN in check.py — keep both in sync
CANONICAL_VERSION_PATTERN = re.compile(r"mthds-agent >= (\d+\.\d+\.\d+)")


def extract_min_mthds_version(skills_dir: Path) -> str:
    """Extract the canonical min_mthds_version from shared/mthds-agent-guide.md.

    This version is baked into the rendered SKILL.md files so the preamble's
    bash block can compare the installed mthds-agent version against the
    plugin's minimum requirement at runtime.
    """
    guide = skills_dir / "shared" / "mthds-agent-guide.md"
    if not guide.is_file():
        msg = f"Cannot find {guide} — needed to extract min_mthds_version"
        raise SystemExit(msg)
    text = guide.read_text(encoding="utf-8")
    match = CANONICAL_VERSION_PATTERN.search(text)
    if not match:
        msg = f"Cannot extract 'mthds-agent >= X.Y.Z' from {guide}"
        raise SystemExit(msg)
    return match.group(1)


def render_templates(skills_dir: Path) -> dict[Path, str]:
    """Render all .j2 templates and return {output_path: rendered_content}.

    Injects min_mthds_version as a template variable so shared/preamble.md
    can include a version comparison in the rendered bash block.

    Raises:
        SystemExit: On missing include files or template syntax errors.
    """
    if not skills_dir.is_dir():
        msg = f"Skills directory not found: {skills_dir}"
        raise SystemExit(msg)

    env = Environment(
        loader=FileSystemLoader(str(skills_dir)),
        keep_trailing_newline=True,
    )

    j2_paths = sorted(skills_dir.glob("*/SKILL.md.j2"))
    if not j2_paths:
        return {}

    min_mthds_version = extract_min_mthds_version(skills_dir)

    # Template variables available to all .j2 templates and their includes
    template_vars = {
        "min_mthds_version": min_mthds_version,
    }

    results: dict[Path, str] = {}
    for j2_path in j2_paths:
        template_name = j2_path.relative_to(skills_dir).as_posix()
        try:
            template = env.get_template(template_name)
            rendered = template.render(**template_vars)
        except TemplateNotFound as exc:
            msg = f"{template_name}: include file not found: {exc.name}"
            raise SystemExit(msg) from exc
        except TemplateSyntaxError as exc:
            msg = f"{template_name}: syntax error at line {exc.lineno}: {exc.message}"
            raise SystemExit(msg) from exc
        output_path = j2_path.with_suffix("")  # .md.j2 -> .md
        results[output_path] = rendered

    return results


def generate(base_dir: Path) -> int:
    """Render all templates and write SKILL.md files."""
    skills_dir = base_dir / "skills"
    results = render_templates(skills_dir)

    if not results:
        print("No .j2 templates found.")
        return 1

    for output_path, rendered in results.items():
        output_path.write_text(rendered, encoding="utf-8")
        rel = output_path.relative_to(base_dir)
        print(f"  Generated {rel}")

    print(f"Generated {len(results)} SKILL.md files.")
    return 0


def check_freshness(base_dir: Path) -> int:
    """Verify that all SKILL.md files match their .j2 template output."""
    skills_dir = base_dir / "skills"
    results = render_templates(skills_dir)

    if not results:
        print("No .j2 templates found.")
        return 1

    stale: list[str] = []
    for output_path, rendered in results.items():
        rel = output_path.relative_to(base_dir)
        if not output_path.is_file():
            stale.append(f"  MISSING: {rel}")
        elif output_path.read_text(encoding="utf-8") != rendered:
            stale.append(f"  STALE: {rel}")

    # Detect orphaned .md files with no corresponding .j2 template
    j2_parents = {path.parent for path in results}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        if skill_md.parent not in j2_parents:
            rel = skill_md.relative_to(base_dir)
            stale.append(f"  ORPHAN: {rel} (no corresponding .j2 template)")

    if stale:
        for msg in stale:
            print(msg)
        print("FAIL: SKILL.md files are out of date. Run `make gen-skill-docs` to regenerate.")
        return 1

    print(f"  All {len(results)} SKILL.md files are fresh.")
    return 0


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent
    if "--check" in sys.argv:
        return check_freshness(base_dir)
    return generate(base_dir)


if __name__ == "__main__":
    sys.exit(main())
