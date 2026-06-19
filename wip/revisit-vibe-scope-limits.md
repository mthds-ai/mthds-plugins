# Revisit: vibe scope limits (deferred)

`mthds-vibe` deliberately excludes some MTHDS constructs (see `templates/skills/mthds-vibe/SKILL.md.j2` and `skills/mthds-vibe/references/vibe-cheat-sheet.md`):

- `dict` field types
- `PipeStructure`
- inline `templating_style` blocks

These limits are kept **as-is** through the recursive-building work ([recursive/design.md](recursive/design.md)) — the building strategy is orthogonal to which constructs are emittable.

**To revisit later:** recursive decomposition makes complex methods more tractable, which may justify lifting some of these limits (especially `PipeStructure`, now that intermediate concepts are refined layer by layer). Decide as a separate, dedicated change — not folded into the recursive-building rollout.
