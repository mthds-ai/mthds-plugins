#!/usr/bin/env bash
# Codex Stop hook: lint and format .mthds files touched during the turn
# Parses the session transcript to find which .mthds files were written via apply_patch,
# then runs:
#   1. plxt lint   — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt    — auto-format the file (only if lint passes)
# Blocks if plxt is not installed. Passes silently if no .mthds files were touched.
# Uses Node.js for JSON parsing (guaranteed on PATH since mthds-agent requires it).

set -euo pipefail

# --- Read stdin (Stop hook JSON) ---
INPUT=$(cat)

# --- Require Node.js for JSON parsing ---
if ! command -v node &>/dev/null; then
  printf '{"decision":"block","reason":"Missing required runtime: Node.js (required by mthds-agent)"}\n'
  exit 0
fi

# --- JSON helpers (Node.js) ---
_jv() { node -e "let d;try{d=JSON.parse(process.argv[1])}catch{d=null};const r=d?($2):undefined;process.stdout.write(r==null?'':String(r))" "$1"; }
_block() {
  node -e "process.stdout.write(JSON.stringify({decision:'block',reason:process.argv[1]})+'\n')" "$1" \
    || printf '{"decision":"block","reason":"Hook error: could not format block reason"}\n'
}

# --- Extract transcript_path from hook input ---
TRANSCRIPT=$(_jv "$INPUT" "d.transcript_path") || true

if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  # No transcript available — pass silently
  exit 0
fi

# --- Parse transcript for .mthds files written via apply_patch ---
MTHDS_FILES=$(node -e "
const fs = require('fs');
const lines = fs.readFileSync(process.argv[1], 'utf8').split('\n');
const files = new Set();
for (const line of lines) {
  if (!line) continue;
  let entry;
  try { entry = JSON.parse(line); } catch { continue; }
  // apply_patch entries contain file paths in the input field
  const input = entry?.payload?.input || '';
  if (typeof input !== 'string') continue;
  // Match 'Update File:' or 'Add File:' lines in apply_patch format
  const matches = input.match(/(?:Update File|Add File):\s*(\S+\.mthds)/g);
  if (matches) {
    for (const match of matches) {
      const path = match.replace(/^(?:Update File|Add File):\s*/, '').trim();
      if (path.endsWith('.mthds')) files.add(path);
    }
  }
}
process.stdout.write([...files].join('\n'));
" "$TRANSCRIPT" 2>/dev/null) || true

# No .mthds files touched — pass silently
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
    ALL_ERRORS="${ALL_ERRORS}TOML/schema lint errors in $FILE_PATH:\n$LINT_OUTPUT\n\n"
    continue
  fi

  # =====================================================================
  # STAGE 2: plxt fmt — auto-format the file in-place (lint passed)
  # =====================================================================
  FMT_EXIT=0
  plxt fmt "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || FMT_EXIT=$?
  if [[ "$FMT_EXIT" -ne 0 ]]; then
    FMT_ERR=$(cat "$TMPERR")
    echo "[mthds-hook] Warning: plxt fmt failed (exit $FMT_EXIT): ${FMT_ERR:-no output}" >&2
  fi

  # STAGE 3: mthds-agent validate bundle — DISABLED (sandbox blocks remote config fetch)
  # TODO: re-enable when mthds-agent supports offline validation
  true

done <<< "$MTHDS_FILES"

# --- Report results ---
if [[ -n "$ALL_ERRORS" ]]; then
  REASON=$(printf "$ALL_ERRORS" | sed '/^$/d')
  _block "$REASON"
fi

exit 0

