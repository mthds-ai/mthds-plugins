#!/usr/bin/env bash
# PostToolUse hook: lint, format, and validate .mthds files after Write/Edit
# Reads tool_input JSON from stdin, then runs (in order):
#   1. plxt lint                  — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt                   — auto-format the file (only if lint passes)
#   3. mthds-agent validate bundle — semantic validation (blocks or warns)
# Blocks if plxt or mthds-agent is not installed. Passes silently if file is not .mthds.
# Uses Node.js for JSON parsing (guaranteed on PATH since mthds-agent requires it).

set -euo pipefail

# --- Read stdin (PostToolUse JSON) and extract file path ---
INPUT=$(cat)

# --- Require Node.js for JSON parsing (guaranteed by mthds-agent dependency) ---
if ! command -v node &>/dev/null; then
  if [[ "$INPUT" =~ \"file_path\"[[:space:]]*:[[:space:]]*\"[^\"]*\.mthds\" ]]; then
    printf '{"decision":"block","reason":"Missing required runtime: Node.js (required by mthds-agent)"}\n'
  fi
  exit 0
fi

# --- JSON helpers (Node.js) ---
# Extract a value from JSON. $1=json_string, $2=JS expression using `d` as the parsed object.
# NOTE: $2 is interpolated into the JS code — must be a trusted literal, never user input.
_jv() { node -e "let d;try{d=JSON.parse(process.argv[1])}catch{d=null};const r=d?($2):undefined;process.stdout.write(r==null?'':String(r))" "$1"; }
# Output a {"decision":"block","reason":...} JSON object. $1=reason string.
_block() {
  node -e "process.stdout.write(JSON.stringify({decision:'block',reason:process.argv[1]})+'\n')" "$1" \
    || printf '{"decision":"block","reason":"Hook error: could not format block reason"}\n'
}

FILE_PATH=$(_jv "$INPUT" "d.tool_input?.file_path")

# Guard: no file path or not a .mthds file → pass silently
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.mthds || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# --- Require plxt and mthds-agent on PATH ---
MISSING=""
command -v plxt &>/dev/null || MISSING="plxt (install via: uv tool install /workspace/vscode-pipelex/)"
command -v mthds-agent &>/dev/null || MISSING="${MISSING:+$MISSING, }mthds-agent (install via: npm install -g /build-src/mthds-js/)"
if [[ -n "$MISSING" ]]; then
  _block "Missing required CLI tool(s): $MISSING"
  exit 0
fi

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
trap 'rm -f "$TMPOUT" "$TMPERR"' EXIT

# =====================================================================
# STAGE 1: plxt lint — TOML/schema-level linting
# =====================================================================
LINT_EXIT=0
plxt lint --quiet "$FILE_PATH" >"$TMPOUT" 2>"$TMPERR" || LINT_EXIT=$?

if [[ "$LINT_EXIT" -ne 0 ]]; then
  LINT_OUTPUT=$(cat "$TMPERR")
  [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT=$(cat "$TMPOUT")
  [[ -z "$LINT_OUTPUT" ]] && LINT_OUTPUT="lint exited with code $LINT_EXIT (no output)"

  _block "TOML/schema lint errors in $FILE_PATH:
$LINT_OUTPUT"
  exit 0
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
  exit 0
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
  echo "[mthds-hook] Warning: Stage 3 decision script failed" >&2
}

exit 0
