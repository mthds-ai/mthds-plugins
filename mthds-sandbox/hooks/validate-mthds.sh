#!/usr/bin/env bash
# PostToolUse hook: lint, format, and validate .mthds files after Write/Edit
# Reads tool_input JSON from stdin, then runs (in order):
#   1. plxt lint                  — TOML/schema-level linting (blocks on errors)
#   2. plxt fmt                   — auto-format the file (only if lint passes)
#   3. mthds-agent validate bundle — semantic validation (blocks on input-domain
#      errors; emits agent additionalContext for config/runtime errors)
# Blocks if plxt or mthds-agent is not installed. Passes silently if file is not .mthds.
# Uses Node.js for JSON encoding of the PostToolUse hook output (decision/additionalContext).

set -euo pipefail

# --- Read stdin (PostToolUse JSON) and extract file path ---
INPUT=$(cat)

# Fast pre-filter: this hook only cares about .mthds files. Exit silently
# for everything else — no Node, no plxt, no mthds-agent, no risk of
# blocking unrelated edits if any later stage misbehaves.
if ! [[ "$INPUT" =~ \"file_path\"[[:space:]]*:[[:space:]]*\"[^\"]*\.mthds\" ]]; then
  exit 0
fi

# --- Require Node.js for JSON parsing (guaranteed by mthds-agent dependency) ---
if ! command -v node &>/dev/null; then
  printf '{"decision":"block","reason":"Missing required runtime: Node.js (required by mthds-agent)"}\n'
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

FILE_PATH=$(_jv "$INPUT" "d.tool_input?.file_path") || {
  _block "Failed to parse tool input JSON (Node.js error)"
  exit 0
}

# Guard: no file path or not a .mthds file → pass silently
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.mthds || ! -f "$FILE_PATH" ]]; then
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
# Markdown stderr is the canonical agent-facing artifact. BLOCK on
# input-domain errors (agent fixes the bundle); emit additionalContext
# for config/runtime errors (agent informed, do not edit the file).
# =====================================================================
PARENT_DIR=$(dirname "$FILE_PATH")

EXIT_CODE=0
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?

if [[ "$EXIT_CODE" -eq 0 ]]; then
  exit 0
fi

# Strip pipelex's internal stack trace (## Error source section to EOF).
# The current floor (mthds-agent >=0.8.1 → pipelex >=0.30.2) already drops
# the section from markdown, so this is a no-op on the supported path;
# kept as defense-in-depth in case a user runs a pipelex build that
# re-introduces it (custom install, downstream fork, etc.).
ERR_MD=$(sed '/^## Error source/,$d' "$TMPERR")

# Empty/whitespace-only stderr → block with generic reason (no actionable content).
if [[ -z "${ERR_MD//[[:space:]]/}" ]]; then
  _block "Validation failed for $FILE_PATH (mthds-agent exited $EXIT_CODE with no stderr output)"
  exit 0
fi

# Extract error_domain from the ## Details section. Pipelex emits each
# field as `- **<key>:** <value>`. Empty when the surfaced error class has
# no error_domain set and is not in pipelex's AGENT_ERROR_DOMAINS lookup.
DOMAIN=$(printf '%s\n' "$ERR_MD" | sed -n 's/^- \*\*error_domain:\*\* *//p' | head -1 | tr -d '[:space:]')

case "$DOMAIN" in
  config|runtime)
    # Environment issue, not a bundle issue. Surface to user (stderr) AND
    # agent (additionalContext) — both informed, neither blocks the write.
    printf '[mthds-hook] Validation warning (domain=%s) for %s:\n%s\n' "$DOMAIN" "$FILE_PATH" "$ERR_MD" >&2
    node -e '
      const md = process.argv[1];
      const file = process.argv[2];
      const domain = process.argv[3];
      const MAX = 9500;
      const trimmed = md.length > MAX
        ? md.slice(0, MAX) + "\n\n[truncated, " + (md.length - MAX) + " chars omitted]"
        : md;
      const header = "Validation warning for " + file + " (" + domain + " domain — environment issue, do not edit the file):\n\n";
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "PostToolUse",
          additionalContext: header + trimmed
        }
      }) + "\n");
    ' "$ERR_MD" "$FILE_PATH" "$DOMAIN" || {
      _block "Hook error: could not format additionalContext for $FILE_PATH"
    }
    exit 0
    ;;
  *)
    # input-domain (or unknown/empty — default to BLOCK for safety).
    # Pass the trimmed markdown verbatim as the block reason; the agent
    # reads it and revises the bundle.
    _block "Validation failed for $FILE_PATH:

$ERR_MD"
    exit 0
    ;;
esac
