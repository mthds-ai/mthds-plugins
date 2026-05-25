# Cold-start prompt for pipelex 0.30.2

Paste the block below into a fresh session opened in `/Users/lchoquel/repos/Pipelex/pipelex/`.

---

```
Repo: /Users/lchoquel/repos/Pipelex/pipelex/

I need you to cut pipelex 0.30.2. The only change vs 0.30.1: drop the `## Error
source` section from the agent CLI's MARKDOWN error envelope.

## Context (why)

The mthds-plugins Claude Code plugin is being rewritten to use pipelex's
markdown error output directly as the agent-facing feedback in its PostToolUse
validate hook. The full architectural plan is in
`../mthds-plugins/wip/plan-validate-hook-rewrite.md` (section A is your scope) —
read it for context if anything below is unclear.

The principle: markdown output is for humans and LLMs. JSON output keeps the
full diagnostic surface (`error_source`, structured per-error fields) for
programmatic consumers. The `## Error source` section in markdown is internal
stack frames (e.g. `LibraryError @ pipelex/libraries/library.py:140`) — useless
to an LLM trying to fix a `.mthds` file, and noisy enough that the hook would
otherwise have to strip it.

## What to change

1. Locate the markdown error formatter that emits `## Error source` in the
   agent CLI error path. Likely under `pipelex/cli/agent_cli/` or a shared
   error-rendering helper. Grep for `## Error source` to find it fast.

2. Remove the section from the markdown output entirely. Do NOT change the JSON
   output — `error_source` must still appear in the JSON envelope for
   programmatic consumers.

3. Keep the `## Details` section (it carries `error_domain`, which the hook
   relies on to decide BLOCK vs warn). Only `## Error source` goes away.

4. Update any tests that snapshot the markdown error format. Search for
   `Error source` in pipelex's test suite.

## Verification

Repro the current markdown error output before and after:

    # Use any broken .mthds — the mthds-plugins repo has one at
    # ../mthds-plugins/wip/bad_bundle.mthds. Or write a one-liner with a
    # missing pipe reference.

    pipelex-agent validate bundle bad_bundle.mthds -L . 2>err.md
    cat err.md

Expected after the change: the output ends after `## Details` (or after the
message body if there are no details). No `## Error source` section. No stack
frames.

For the JSON path (must remain unchanged):

    pipelex-agent validate bundle bad_bundle.mthds -L . --error-format json 2>err.json
    python3 -c "import json; d=json.load(open('err.json')); print('error_source' in d, len(d.get('error_source', [])))"

Expected: `True 2` (or however many frames). JSON unchanged.

## Release steps

1. Make the code change + test updates.
2. Bump version 0.30.1 → 0.30.2 in `pyproject.toml` (and anywhere else pipelex
   version is sourced from — usually `pipelex/__init__.py` or similar).
3. Update `CHANGELOG.md` with a `### Changed` entry: "Markdown error envelope
   no longer includes `## Error source` stack frames. The `error_source` field
   remains in the JSON envelope (`--error-format json`) for programmatic
   consumers. Markdown is for humans / LLMs; JSON for tooling."
4. Run pipelex's checks — `make agent-check` and `make agent-test` (or
   whatever the repo's standard pre-release commands are; check `Makefile` or
   the `/release` skill if one exists in `.claude/skills/`).
5. Cut a release branch and PR via the repo's `/release` workflow, or hand-
   commit per the repo's convention. Don't push or merge without showing me
   the diff first.

## Out of scope

- Don't touch the JSON envelope shape.
- Don't change error categorization, `error_domain` values, or message
  wording — only the stack-trace section is going away.
- Don't change the agent CLI's stdout/stderr routing (already correct in
  0.30.1).

When you're done, just tell me "pipelex 0.30.2 ready for review" and I'll come
look at the diff before publish.
```
