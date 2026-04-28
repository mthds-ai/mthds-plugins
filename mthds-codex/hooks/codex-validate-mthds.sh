#!/usr/bin/env bash
# Codex PostToolUse(apply_patch) hook: lint and format .mthds files after apply_patch.
# Reads PostToolUse JSON from stdin, extracts the patch envelope from
# tool_input.command, parses *** Update File: / *** Add File: / *** Move to:
# headers to find touched .mthds files, then runs (per file):
#   1. plxt lint  — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt   — auto-format the file (only if lint passes)
# Stage 3 (mthds-agent validate bundle) stays disabled until offline-mode
# validation lands in mthds-agent — the Codex sandbox blocks the eager S3
# remote-config fetch and the command would hang. See docs/codex-vs-claude-hooks.md.
# Passes silently if no .mthds files were touched.

set -euo pipefail

INPUT=$(cat)

# --- Require Node.js for JSON parsing (already required by mthds-agent) ---
if ! command -v node &>/dev/null; then
  printf '{"decision":"block","reason":"Missing required runtime: Node.js (required by mthds-agent)"}\n'
  exit 0
fi

# --- JSON helpers (Node.js) ---
# $1 = JSON string, $2 = JS expression using `d` as the parsed object.
# NOTE: $2 is interpolated into the JS source — must be a trusted literal.
_jv() { node -e "let d;try{d=JSON.parse(process.argv[1])}catch{d=null};const r=d?($2):undefined;process.stdout.write(r==null?'':String(r))" "$1"; }
_block() {
  node -e "process.stdout.write(JSON.stringify({decision:'block',reason:process.argv[1]})+'\n')" "$1" \
    || printf '{"decision":"block","reason":"Hook error: could not format block reason"}\n'
}

# --- Extract the apply_patch envelope from PostToolUse stdin ---
# tool_input.command is the raw patch text the model emitted, with
# `*** Begin Patch / *** Update File: <path> / ... / *** End Patch` framing.
COMMAND=$(_jv "$INPUT" "d.tool_input?.command") || true

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# --- Parse `*** Update File:` / `*** Add File:` / `*** Move to:` headers ---
# A single apply_patch call can touch several files; we collect every .mthds
# path mentioned. `Move to:` carries the destination of a rename — we want to
# validate the destination, not the (now gone) source.
MTHDS_FILES=$(node -e "
const cmd = process.argv[1];
const files = new Set();
const re = /^\*\*\* (?:Update File|Add File|Move to):\s*(.+\.mthds)\s*$/gm;
let match;
while ((match = re.exec(cmd)) !== null) {
  files.add(match[1].trim());
}
process.stdout.write([...files].join('\n'));
" "$COMMAND" 2>/dev/null) || true

if [[ -z "$MTHDS_FILES" ]]; then
  exit 0
fi

# --- Require plxt on PATH ---
if ! command -v plxt &>/dev/null; then
_block "Missing required CLI tool: plxt (install via: uv tool install pipelex-tools)"
exit 0
fi

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
trap 'rm -f "$TMPOUT" "$TMPERR"' EXIT

ALL_ERRORS=""

while IFS= read -r FILE_PATH; do
  # Renamed-source paths and `*** Delete File:` targets won't exist on disk
  # after the patch applies, so skipping nonexistent paths is the right thing.
  [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]] && continue

  # =====================================================================
  # STAGE 1: plxt lint — TOML/schema-level linting
  # =====================================================================
  LINT_EXIT=0
  plxt lint --quiet "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || LINT_EXIT=$?

  if [[ "$LINT_EXIT" -ne 0 ]]; then
    LINT_OUTPUT=$(cat "$TMPERR")
    [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT=$(cat "$TMPOUT")
    [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT="lint exited with code $LINT_EXIT (no output)"
    ALL_ERRORS="${ALL_ERRORS}TOML/schema lint errors in $FILE_PATH:\n$LINT_OUTPUT\n\nFix it.\n\n"
    continue
  fi

  # =====================================================================
  # STAGE 2: plxt fmt — auto-format in place (lint passed)
  # =====================================================================
  FMT_EXIT=0
  plxt fmt "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || FMT_EXIT=$?
  if [[ "$FMT_EXIT" -ne 0 ]]; then
    FMT_ERR=$(cat "$TMPERR")
    ALL_ERRORS="${ALL_ERRORS}plxt fmt failed on $FILE_PATH (exit $FMT_EXIT):\n${FMT_ERR:-no output}\n\nFix it.\n\n"
  fi

  # STAGE 3: mthds-agent validate bundle — DISABLED in the Codex sandbox.
  # The eager S3 remote-config fetch in mthds-agent hangs when network is
  # restricted; re-enable once mthds-agent supports offline validation
  # (tracked as Phase 2D in TODOS.md).
  true

done <<< "$MTHDS_FILES"

if [[ -n "$ALL_ERRORS" ]]; then
  REASON=$(printf "$ALL_ERRORS" | sed '/^$/d')
  _block "$REASON"
fi

exit 0

