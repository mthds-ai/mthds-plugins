#!/usr/bin/env bash
# install-codex.sh — wire the MTHDS Codex hooks and env-check helper.
#
# Codex 0.124.0+ installs the plugin itself via:
#   codex plugin marketplace add mthds-ai/mthds-plugins
#   # then /plugins inside Codex to install
#
# This script handles only what Codex doesn't yet do automatically:
#   1. ensures mthds-agent is on PATH (and ≥ MIN_MTHDS_VERSION)
#   2. copies bin/mthds-env-check to ~/.codex/bin/
#   3. copies hooks/codex-validate-mthds.sh to ~/.codex/hooks/
#   4. merges a PostToolUse(apply_patch) entry into ~/.codex/hooks.json
#
# The `[features] codex_hooks` flag is no longer required (Stage::Stable,
# default-enabled in Codex). Plugin auto-loaded hooks are still upstream-
# blocked (no `hooks` field in plugin.json). When that lands, this script
# can be deleted entirely (TODOS.md Phase 2A/2G).
#
# Run from any directory — the script locates its own plugin source.
#
# Usage:
#   bash install-codex.sh          # install
#   bash install-codex.sh --check  # verify (no changes)

set -euo pipefail

# ── Output helpers ─────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${CYAN}▸${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}!${RESET} %s\n" "$*"; }
fail()  { printf "${RED}✗${RESET} %s\n" "$*"; }
fatal() { fail "$*"; exit 1; }

command_exists() { command -v "$1" &>/dev/null; }

version_of() {
  "$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
}

# ── Configuration ──────────────────────────────────────────────────

GITHUB_REPO="mthds-ai/mthds-plugins"
GITHUB_BRANCH="main"
PLUGIN_SOURCE_DIR=""
TMP_REPO_DIR=""

# Minimum mthds-agent version required by this installer. Must match
# `min_mthds_version` in mthds-plugins/targets/defaults.toml. Bump together
# whenever this script depends on a new mthds-agent capability.
MIN_MTHDS_VERSION="0.4.1"

cleanup_tmp_repo() {
  if [[ -n "$TMP_REPO_DIR" && -d "$TMP_REPO_DIR" ]]; then
    rm -rf "$TMP_REPO_DIR"
  fi
}

trap cleanup_tmp_repo EXIT

# Locate the plugin source — the directory containing
# `hooks/codex-validate-mthds.sh` and `bin/mthds-env-check`. Prefer a sibling
# `mthds-codex/` checkout (when this script runs from a clone), otherwise
# shallow-clone the repo so curl-pipe-bash users still work.
resolve_plugin_source() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_dir
  repo_dir="$(dirname "$script_dir")"

  if [[ -d "$repo_dir/mthds-codex/hooks" && -d "$repo_dir/bin" ]]; then
    PLUGIN_SOURCE_DIR="$repo_dir"
    return
  fi

  TMP_REPO_DIR=$(mktemp -d)
  if git clone --depth 1 --branch "$GITHUB_BRANCH" "https://github.com/$GITHUB_REPO.git" "$TMP_REPO_DIR" 2>&1; then
    if [[ -f "$TMP_REPO_DIR/mthds-codex/hooks/codex-validate-mthds.sh" ]]; then
      PLUGIN_SOURCE_DIR="$TMP_REPO_DIR"
    else
      fatal "Plugin source not found in cloned repo — build artifacts missing"
    fi
  else
    fatal "Failed to clone $GITHUB_REPO — check network and GitHub access"
  fi
}

# ── Prerequisite checks ───────────────────────────────────────────

check_prereqs() {
  local missing=0

  if command_exists node; then
    ok "node $(node --version)"
  else
    fail "node not found — install from https://nodejs.org"
    missing=1
  fi

  if command_exists npm; then
    ok "npm $(npm --version)"
  else
    fail "npm not found — install from https://nodejs.org"
    missing=1
  fi

  if command_exists codex; then
    ok "codex $(version_of codex)"
  else
    fail "codex not found — install with: npm install -g @openai/codex"
    missing=1
  fi

  if command_exists uv; then
    ok "uv $(version_of uv)"
  else
    warn "uv not found — Python tools will install on first use"
    warn "  Get it from https://docs.astral.sh/uv/ for a smoother experience"
  fi

  return $missing
}

# ── Install steps ──────────────────────────────────────────────────

# Returns 0 if $1 >= $2 in semver-ish dotted order, 1 otherwise.
version_ge() {
  # sort -V is GNU-only; use awk for cross-platform semver comparison.
  awk -v a="$1" -v b="$2" 'BEGIN {
    n=split(a,A,"."); m=split(b,B,".");
    max=(n>m)?n:m;
    for(i=1;i<=max;i++){
      x=A[i]+0; y=B[i]+0;
      if(x>y) exit 0;
      if(x<y) exit 1;
    }
    exit 0
  }'
}

install_mthds_cli() {
  if command_exists mthds-agent; then
    local ver
    ver=$(version_of mthds-agent)
    if [ -n "$ver" ] && version_ge "$ver" "$MIN_MTHDS_VERSION"; then
      ok "mthds-agent $ver (>= $MIN_MTHDS_VERSION, no install needed)"
      return 0
    fi
    if [ -n "$ver" ]; then
      info "mthds-agent $ver is older than $MIN_MTHDS_VERSION — upgrading..."
    else
      info "mthds-agent installed but version unknown — reinstalling..."
    fi
  else
    info "Installing mthds npm package globally..."
  fi

  if npm install -g mthds@latest 2>&1; then
    local new_ver
    new_ver=$(version_of mthds-agent)
    if [ -z "$new_ver" ] || ! version_ge "$new_ver" "$MIN_MTHDS_VERSION"; then
      fatal "mthds-agent $new_ver installed but is still below required $MIN_MTHDS_VERSION"
    fi
    ok "mthds-agent $new_ver"
  else
    fatal "npm install -g mthds@latest failed — check npm permissions"
  fi
}

install_env_check() {
  local env_check_dir="$HOME/.codex/bin"
  local source_file="$PLUGIN_SOURCE_DIR/bin/mthds-env-check"

  info "Installing mthds-env-check..."
  mkdir -p "$env_check_dir"

  if [[ -f "$source_file" ]]; then
    cp "$source_file" "$env_check_dir/mthds-env-check"
    chmod +x "$env_check_dir/mthds-env-check"
    ok "mthds-env-check installed to ~/.codex/bin/"
  else
    fatal "mthds-env-check not found at $source_file"
  fi
}

# Merge a PostToolUse(apply_patch) entry into ~/.codex/hooks.json without
# clobbering other hooks the user may already have. Idempotent: re-running
# is a no-op once the entry is present.
#
# The script is hardcoded for the apply_patch matcher because Codex emits
# PostToolUse for the apply_patch tool only — the canonical name we register
# matches `tool_input.command` extraction in codex-validate-mthds.sh.
merge_post_tool_use_hook() {
  local hooks_file="$HOME/.codex/hooks.json"
  local hook_command='~/.codex/hooks/codex-validate-mthds.sh'

  mkdir -p "$(dirname "$hooks_file")"

  HOOK_FILE="$hooks_file" HOOK_COMMAND="$hook_command" node - <<'NODE'
const fs = require("fs");
const path = require("path");

const file = process.env.HOOK_FILE;
const command = process.env.HOOK_COMMAND;
const MARKER = "codex-validate-mthds";

const entry = {
  matcher: "apply_patch",
  hooks: [
    { type: "command", command, timeout: 30 },
  ],
};

function entryMentionsMthds(item) {
  return item && Array.isArray(item.hooks) &&
    item.hooks.some((h) => typeof h?.command === "string" && h.command.includes(MARKER));
}

let parsed = { hooks: { PostToolUse: [entry] } };

if (fs.existsSync(file)) {
  const raw = fs.readFileSync(file, "utf8");
  const trimmed = raw.trim();
  if (trimmed.length > 0) {
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      console.error(`Invalid JSON in ${file}: ${err.message}. Fix the file by hand or delete it and re-run.`);
      process.exit(1);
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      console.error(`${file} does not contain a JSON object at the top level.`);
      process.exit(1);
    }
  }

  if (parsed.hooks === undefined) {
    parsed.hooks = {};
  } else if (typeof parsed.hooks !== "object" || parsed.hooks === null || Array.isArray(parsed.hooks)) {
    console.error(`${file} has an invalid \`hooks\` field. Fix the file by hand.`);
    process.exit(1);
  }

  if (parsed.hooks.PostToolUse === undefined) {
    parsed.hooks.PostToolUse = [];
  } else if (!Array.isArray(parsed.hooks.PostToolUse)) {
    console.error(`${file} has an invalid \`hooks.PostToolUse\` field (expected array). Fix the file by hand.`);
    process.exit(1);
  }

  // Drop any prior Stop entry that pointed at our script (left over from
  // pre-0.9.0 installs). Keeping a stale Stop entry would cost a fork on
  // every Codex turn end.
  if (Array.isArray(parsed.hooks.Stop)) {
    parsed.hooks.Stop = parsed.hooks.Stop.filter((item) => !entryMentionsMthds(item));
    if (parsed.hooks.Stop.length === 0) {
      delete parsed.hooks.Stop;
    }
  }

  if (parsed.hooks.PostToolUse.some(entryMentionsMthds)) {
    process.stdout.write("ALREADY_INSTALLED\n");
  } else {
    parsed.hooks.PostToolUse.push(entry);
    process.stdout.write("MERGED\n");
  }
}

const tmp = `${file}.tmp-${process.pid}-${Date.now()}`;
fs.writeFileSync(tmp, JSON.stringify(parsed, null, 2) + "\n", { encoding: "utf8", mode: 0o644 });
fs.renameSync(tmp, file);
NODE
}

setup_hooks() {
  local hooks_dir="$HOME/.codex/hooks"
  local source_file="$PLUGIN_SOURCE_DIR/mthds-codex/hooks/codex-validate-mthds.sh"

  info "Setting up hooks..."
  mkdir -p "$hooks_dir"

  if [[ -f "$source_file" ]]; then
    cp "$source_file" "$hooks_dir/codex-validate-mthds.sh"
    chmod +x "$hooks_dir/codex-validate-mthds.sh"
  else
    fatal "Hook script not found at $source_file"
  fi

  info "Merging PostToolUse(apply_patch) hook into ~/.codex/hooks.json..."
  if merge_post_tool_use_hook >/dev/null; then
    ok "Hook entry merged into ~/.codex/hooks.json"
  else
    fatal "Failed to merge hook entry into ~/.codex/hooks.json"
  fi
}

# ── Verify ─────────────────────────────────────────────────────────

verify_install() {
  local all_ok=0

  if command_exists mthds-agent; then
    ok "mthds-agent on PATH"
  else
    fail "mthds-agent not on PATH"
    all_ok=1
  fi

  if [[ -f "$HOME/.codex/hooks.json" ]] && grep -q "codex-validate-mthds" "$HOME/.codex/hooks.json" 2>/dev/null; then
    ok "Hook entry registered in ~/.codex/hooks.json"
  else
    fail "Hook entry missing from ~/.codex/hooks.json"
    all_ok=1
  fi

  if [[ -x "$HOME/.codex/hooks/codex-validate-mthds.sh" ]]; then
    ok "Hook script in place"
  else
    fail "Hook script not found at ~/.codex/hooks/codex-validate-mthds.sh"
    all_ok=1
  fi

  if [[ -x "$HOME/.codex/bin/mthds-env-check" ]]; then
    ok "mthds-env-check installed"
  else
    fail "mthds-env-check not found at ~/.codex/bin/mthds-env-check"
    all_ok=1
  fi

  return $all_ok
}

# ── Main ───────────────────────────────────────────────────────────

main() {
  local check_only=0
  [ "${1:-}" = "--check" ] && check_only=1

  echo ""
  printf "${BOLD}MTHDS Codex Hook Installer${RESET}\n"
  echo ""

  resolve_plugin_source

  info "Checking prerequisites..."
  if ! check_prereqs; then
    echo ""
    fatal "Missing prerequisites — install them first"
  fi
  echo ""

  if [ "$check_only" -eq 1 ]; then
    info "Verifying existing install..."
    if verify_install; then
      echo ""
      ok "All good"
    else
      echo ""
      fail "Install incomplete — run without --check to fix"
      return 1
    fi
    return 0
  fi

  install_mthds_cli
  install_env_check
  setup_hooks
  echo ""

  info "Verifying..."
  if ! verify_install; then
    echo ""
    fail "Install may be incomplete — check errors above"
    return 1
  fi

  echo ""
  printf "${GREEN}${BOLD}Hooks installed.${RESET}\n"
  echo ""
  printf "${YELLOW}Next: codex plugin marketplace add mthds-ai/mthds-plugins${RESET}\n"
  printf "${YELLOW}Then restart Codex and run /plugins to install mthds.${RESET}\n"
  echo ""
}

main "$@"
