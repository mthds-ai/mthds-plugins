#!/usr/bin/env bash
# Codex Stop hook: lint, format, and validate all .mthds files in the project
# Finds all .mthds files under the working directory, then runs (in order):
#   1. plxt lint                  — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt                   — auto-format the file (only if lint passes)
#   3. mthds-agent validate bundle — semantic validation (blocks or warns)
# Blocks if plxt or mthds-agent is not installed. Passes silently if no .mthds files found.
# Uses Node.js for JSON parsing (guaranteed on PATH since mthds-agent requires it).

set -euo pipefail

# --- Read stdin (Stop hook JSON) — extract cwd ---
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

# --- Get working directory from hook input ---
CWD=$(_jv "$INPUT" "d.cwd") || true
if [[ -z "$CWD" ]]; then
  CWD="$(pwd)"
fi

# --- Find all .mthds files ---
MTHDS_FILES=()
while IFS= read -r file; do
  [[ -n "$file" ]] && MTHDS_FILES+=("$file")
done < <(find "$CWD" -name "*.mthds" -type f 2>/dev/null)

# No .mthds files — pass silently
if [[ ${#MTHDS_FILES[@]} -eq 0 ]]; then
  exit 0
fi

# --- Require plxt and mthds-agent on PATH ---
MISSING=""
command -v plxt &>/dev/null || MISSING="plxt (install via: uv tool install pipelex-tools)"
command -v mthds-agent &>/dev/null || MISSING="${MISSING:+$MISSING, }mthds-agent (install via: npm install -g mthds)"
if [[ -n "$MISSING" ]]; then
  _block "Missing required CLI tool(s): $MISSING"
  exit 0
fi

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
trap 'rm -f "$TMPOUT" "$TMPERR"' EXIT

ALL_ERRORS=""

for FILE_PATH in "${MTHDS_FILES[@]}"; do

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

  # =====================================================================
  # STAGE 3: mthds-agent validate bundle — semantic validation
  # =====================================================================
  PARENT_DIR=$(dirname "$FILE_PATH")

  EXIT_CODE=0
  mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?

  # --- Parse results ---
  if [[ "$EXIT_CODE" -eq 0 ]]; then
    continue
  fi

  # Error path: parse stderr JSON and decide in a single Node.js call
  ERR_JSON=$(cat "$TMPERR")

  node -e "
const file = process.argv[1];
const exitCode = process.argv[2];
let d;
try { d = JSON.parse(process.argv[3]); } catch { d = null; }

// No valid JSON or missing .error key → warn and pass
if (!d || !d.error) {
  process.stderr.write('[mthds-hook] Warning: mthds-agent validate exited with code ' + exitCode + ' but produced unexpected output:\n');
  process.stderr.write((process.argv[3] || '') + '\n');
  process.exit(0);
}

const domain = d.error_domain || '';
const errType = d.error_type || '';
const message = d.message || '';
const hint = d.hint || '';
const valErrs = Array.isArray(d.validation_errors) ? d.validation_errors : [];
const dryRunErr = d.dry_run_error || null;

function warn(msg) { process.stderr.write('[mthds-hook] ' + msg + '\n'); }
function block(reason) { process.stdout.write(JSON.stringify({decision:'block',reason}) + '\n'); }

// Config or runtime domain → WARN only (not fixable by editing .mthds)
if (domain === 'config' || domain === 'runtime') {
  warn('Warning: ' + message);
  if (hint) warn('Hint: ' + hint);
  process.exit(0);
}

// Structural validation_errors → BLOCK
if (valErrs.length > 0) {
  const pipes = [...new Set(valErrs.map(e => e.pipe_code || 'unknown'))].join(', ');
  const details = valErrs.map(e => '- [' + (e.pipe_code || 'unknown') + '] ' + e.message).join('\n');
  block(file + ' has ' + valErrs.length + ' validation error(s) in pipe(s): ' + pipes + '\n' + details);
  process.exit(0);
}

// dry_run_error only (no validation_errors) → WARN
if (dryRunErr) {
  warn('Warning (dry-run): ' + message);
  warn('Dry-run detail: ' + dryRunErr);
  if (hint) warn('Hint: ' + hint);
  process.exit(0);
}

// Other input-domain errors → WARN
warn('Warning: ' + errType + ' — ' + message);
if (hint) warn('Hint: ' + hint);
process.exit(0);
" "$FILE_PATH" "$EXIT_CODE" "$ERR_JSON" || {
    _block "Stage 3 decision script crashed — treating as validation failure for $FILE_PATH"
  }

done

# --- Report results ---
if [[ -n "$ALL_ERRORS" ]]; then
  REASON=$(printf "$ALL_ERRORS" | sed '/^$/d')
  _block "$REASON"
fi

exit 0

