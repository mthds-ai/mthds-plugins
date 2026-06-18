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
command -v plxt &>/dev/null || MISSING="plxt (install via: rm -rf /tmp/vscode-pipelex-build /tmp/vscode-pipelex-build.tar && mkdir -p /tmp/vscode-pipelex-build && tar -C /workspace/vscode-pipelex --exclude=./target --exclude=./.venv --exclude=./.git --exclude=./node_modules -cf /tmp/vscode-pipelex-build.tar . && tar -C /tmp/vscode-pipelex-build -xf /tmp/vscode-pipelex-build.tar && rm -f /tmp/vscode-pipelex-build.tar && uv tool install /tmp/vscode-pipelex-build/)"
command -v mthds-agent &>/dev/null || MISSING="${MISSING:+$MISSING, }mthds-agent (install via: rm -rf /tmp/mthds-js-build /tmp/mthds-js-build.tar && mkdir -p /tmp/mthds-js-build && tar -C /build-src/mthds-js --exclude=./.git -cf /tmp/mthds-js-build.tar . && tar -C /tmp/mthds-js-build -xf /tmp/mthds-js-build.tar && rm -f /tmp/mthds-js-build.tar && npm install -g /tmp/mthds-js-build/)"
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
# Reads the STRUCTURED verdict from JSON, not the exit code or a markdown grep
# (--format json / --error-format json are pinned so the machine read holds under
# ANY configured runner — pipelex or api). A VALID bundle (is_valid:true) PASSES
# even when it is not yet runnable: unimplemented PipeSignature placeholders ride
# the success envelope on stdout with is_valid:true, and validity (not runnability)
# is what a post-edit hook should gate. An INVALID verdict (is_valid:false) rides
# the JSON error envelope on stderr: BLOCK on input-domain errors (agent fixes the
# bundle), emit additionalContext on config/runtime errors (environment issue —
# agent informed, do not edit the file).
# =====================================================================
PARENT_DIR=$(dirname "$FILE_PATH")

EXIT_CODE=0
mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/" --format json --error-format json >"$TMPOUT" 2>"$TMPERR" || EXIT_CODE=$?

# Valid verdict → pass. The success envelope (is_valid:true) rides stdout even when
# the exit code is non-zero (the strict not-runnable signature gate exits non-zero
# while the bundle is structurally valid). Read is_valid, NOT the exit code.
if [[ "$(_jv "$(cat "$TMPOUT")" "d.is_valid === true ? 'y' : ''")" == "y" ]]; then
  exit 0
fi
# A clean exit 0 WITHOUT the structured `is_valid:true` success envelope means we got no
# machine-readable verdict (e.g. an older/regressed mthds-agent that exits 0 with no/garbled
# JSON). This hook treats the structured verdict as the source of truth, so BLOCK rather than
# silently allow an unverifiable edit — fail safe for a write gate.
if [[ "$EXIT_CODE" -eq 0 ]]; then
  _block "Validation failed for $FILE_PATH (mthds-agent exited 0 with no structured success envelope — upgrade mthds-agent)"
  exit 0
fi

# Invalid / no-verdict → the JSON error envelope is on stderr.
ERR_JSON=$(cat "$TMPERR")

# Unparseable / non-error stderr → block (no actionable structured content).
if [[ -z "$(_jv "$ERR_JSON" "(d.error === true || d.is_valid === false) ? 'y' : ''")" ]]; then
  _block "Validation failed for $FILE_PATH (mthds-agent exited $EXIT_CODE with no structured error envelope)"
  exit 0
fi

# error_domain straight from the structured envelope (no markdown grep). Empty when
# the surfaced error class has no error_domain set.
DOMAIN=$(_jv "$ERR_JSON" "d.error_domain")

case "$DOMAIN" in
  config|runtime)
    # Environment issue, not a bundle issue. Surface to user (stderr) AND agent
    # (additionalContext) — both informed, neither blocks the write.
    printf '[mthds-hook] Validation warning (domain=%s) for %s\n' "$DOMAIN" "$FILE_PATH" >&2
    node -e '
      let env; try { env = JSON.parse(process.argv[1]); } catch { env = {}; }
      const file = process.argv[2];
      const domain = process.argv[3];
      const MAX = 9500;
      const body = String(env.message || "(no message)");
      const trimmed = body.length > MAX
        ? body.slice(0, MAX) + "\n\n[truncated, " + (body.length - MAX) + " chars omitted]"
        : body;
      const header = "Validation warning for " + file + " (" + domain + " domain — environment issue, do not edit the file):\n\n";
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "PostToolUse",
          additionalContext: header + trimmed
        }
      }) + "\n");
    ' "$ERR_JSON" "$FILE_PATH" "$DOMAIN" || {
      _block "Hook error: could not format additionalContext for $FILE_PATH"
    }
    exit 0
    ;;
  *)
    # input-domain (or unknown/empty — default to BLOCK for safety). Build the
    # agent-actionable reason from the structured envelope: the message plus each
    # validation_errors item with its locators.
    REASON=$(node -e '
      let env; try { env = JSON.parse(process.argv[1]); } catch { env = {}; }
      const file = process.argv[2];
      const lines = ["Validation failed for " + file + ":", "", String(env.message || "Bundle is invalid.")];
      const errs = Array.isArray(env.validation_errors) ? env.validation_errors : [];
      if (errs.length) {
        lines.push("");
        for (const e of errs) {
          const loc = [
            e.pipe_code && ("pipe " + e.pipe_code),
            e.concept_code && ("concept " + e.concept_code),
            e.field_name && ("field " + e.field_name),
            e.source && ("source " + e.source),
          ].filter(Boolean).join(", ");
          lines.push("- [" + (e.category || "error") + "] " + String(e.message || "") + (loc ? " (" + loc + ")" : ""));
        }
      }
      const MAX = 9500;
      const out = lines.join("\n");
      process.stdout.write(out.length > MAX ? out.slice(0, MAX) + "\n\n[truncated]" : out);
    ' "$ERR_JSON" "$FILE_PATH" 2>/dev/null) || REASON=""
    [[ -z "$REASON" ]] && REASON="Validation failed for $FILE_PATH"
    _block "$REASON"
    exit 0
    ;;
esac
