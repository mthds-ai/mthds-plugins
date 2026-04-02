#!/usr/bin/env bash
# PostToolUse hook: lint, format, and validate .mthds files after Write/Edit
# Reads tool_input JSON from stdin, then runs (in order):
#   1. plxt lint                  — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt                   — auto-format the file (only if lint passes)
#   3. mthds-agent validate bundle — semantic validation (blocks or warns)
# Blocks if jq, plxt, or mthds-agent is not installed. Passes silently if file is not .mthds.

set -euo pipefail

# --- Read stdin (PostToolUse JSON) and extract file path ---
INPUT=$(cat)

# --- Require jq before any JSON parsing ---
if ! command -v jq &>/dev/null; then
  # Can't parse input without jq — check for .mthds via bash pattern
  if [[ "$INPUT" == *".mthds"* ]]; then
    printf '{"decision":"block","reason":"Missing required CLI tool: jq (install via your package manager)"}\n'
  fi
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Guard: no file path or not a .mthds file → pass silently
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.mthds || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# --- Require plxt and mthds-agent on PATH ---
MISSING=""
command -v plxt &>/dev/null || MISSING="plxt (install via: uv tool install pipelex-tools)"
command -v mthds-agent &>/dev/null || MISSING="${MISSING:+$MISSING, }mthds-agent (install via: npm install -g mthds)"
if [[ -n "$MISSING" ]]; then
  jq -n --arg reason "Missing required CLI tool(s): $MISSING" \
    '{"decision":"block","reason":$reason}'
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

  jq -n --arg reason "TOML/schema lint errors in $FILE_PATH:
$LINT_OUTPUT" \
    '{"decision":"block","reason":$reason}'
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

# Error path: parse the stderr JSON
ERR_JSON=$(cat "$TMPERR")

# Check if we got valid JSON with .error key; warn if not (don't block — may be version mismatch)
if ! echo "$ERR_JSON" | jq -e '.error' &>/dev/null; then
  echo "[mthds-hook] Warning: mthds-agent validate exited with code $EXIT_CODE but produced unexpected output:" >&2
  echo "$ERR_JSON" >&2
  exit 0
fi

ERROR_DOMAIN=$(echo "$ERR_JSON" | jq -r '.error_domain // empty')
ERROR_TYPE=$(echo "$ERR_JSON" | jq -r '.error_type // empty')
MESSAGE=$(echo "$ERR_JSON" | jq -r '.message // empty')
HINT=$(echo "$ERR_JSON" | jq -r '.hint // empty')
HAS_VALIDATION_ERRORS=$(echo "$ERR_JSON" | jq 'has("validation_errors") and (.validation_errors | length > 0)')
HAS_DRY_RUN_ERROR=$(echo "$ERR_JSON" | jq 'has("dry_run_error") and (.dry_run_error != null)')

# --- Decision logic ---

# Config or runtime domain → WARN only (not fixable by editing .mthds)
if [[ "$ERROR_DOMAIN" == "config" || "$ERROR_DOMAIN" == "runtime" ]]; then
  echo "[mthds-hook] Warning: $MESSAGE" >&2
  if [[ -n "$HINT" ]]; then
    echo "[mthds-hook] Hint: $HINT" >&2
  fi
  exit 0
fi

# Structural validation_errors present → BLOCK
if [[ "$HAS_VALIDATION_ERRORS" == "true" ]]; then
  # Build a summary of validation errors for the block reason
  PIPE_NAMES=$(echo "$ERR_JSON" | jq -r '[.validation_errors[].pipe_code // "unknown"] | unique | join(", ")')
  ERROR_COUNT=$(echo "$ERR_JSON" | jq '.validation_errors | length')
  ERROR_DETAILS=$(echo "$ERR_JSON" | jq -r '.validation_errors[] | "- [\(.pipe_code // "unknown")] \(.message)"')

  REASON=$(jq -n --arg pipe_names "$PIPE_NAMES" \
                  --arg error_count "$ERROR_COUNT" \
                  --arg details "$ERROR_DETAILS" \
                  --arg file "$FILE_PATH" \
    '$file + " has " + $error_count + " validation error(s) in pipe(s): " + $pipe_names + "\n" + $details')
  # Remove surrounding quotes from jq -n output
  REASON=$(echo "$REASON" | sed 's/^"//;s/"$//')

  jq -n --arg reason "$REASON" '{"decision":"block","reason":$reason}'
  exit 0
fi

# dry_run_error only (no validation_errors) → WARN
if [[ "$HAS_DRY_RUN_ERROR" == "true" ]]; then
  DRY_RUN_MSG=$(echo "$ERR_JSON" | jq -r '.dry_run_error // empty')
  echo "[mthds-hook] Warning (dry-run): $MESSAGE" >&2
  if [[ -n "$DRY_RUN_MSG" ]]; then
    echo "[mthds-hook] Dry-run detail: $DRY_RUN_MSG" >&2
  fi
  if [[ -n "$HINT" ]]; then
    echo "[mthds-hook] Hint: $HINT" >&2
  fi
  exit 0
fi

# Other input-domain errors without validation_errors → WARN
echo "[mthds-hook] Warning: $ERROR_TYPE — $MESSAGE" >&2
if [[ -n "$HINT" ]]; then
  echo "[mthds-hook] Hint: $HINT" >&2
fi
exit 0
