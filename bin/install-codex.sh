#!/usr/bin/env bash
# install-codex.sh — install the MTHDS Codex plugin into the current repo
#
# Must be run from inside a project directory. Copies plugin files into
# $PWD/plugins/mthds/ and creates the marketplace + hooks config.
#
# Usage:
#   cd my-project && bash install-codex.sh          # install
#   cd my-project && bash install-codex.sh --check  # verify (no changes)
#
# Exit codes:
#   0 — success
#   1 — prerequisite missing or install failed
#
# TODO-WHEN-0.119.0:
#   - Replace repo-local install with `codex marketplace add` when it ships (PR #17087)
#   - Switch from PostToolUse(Bash) to PostToolUse(Write|Edit) if Codex adds support
#   - Test if `~/.agents/plugins/marketplace.json` personal install works reliably
#   - Test if plugin.json `"hooks"` field auto-loads hooks from plugins

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
MARKETPLACE_SOURCE_FILE=""
TMP_REPO_DIR=""

# Minimum mthds-agent version required by this installer. Must match
# the `min_mthds_version` in mthds-plugins/targets/defaults.toml. Bump
# together whenever install-codex.sh calls a new mthds-agent subcommand.
MIN_MTHDS_VERSION="0.4.1"

cleanup_tmp_repo() {
  if [[ -n "$TMP_REPO_DIR" && -d "$TMP_REPO_DIR" ]]; then
    rm -rf "$TMP_REPO_DIR"
  fi
}

trap cleanup_tmp_repo EXIT

resolve_plugin_source() {
  # If run from the mthds-plugins repo, use local mthds-codex/ directory
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_dir
  repo_dir="$(dirname "$script_dir")"

  if [[ -d "$repo_dir/mthds-codex/.codex-plugin" ]]; then
    PLUGIN_SOURCE_DIR="$repo_dir/mthds-codex"
    MARKETPLACE_SOURCE_FILE="$repo_dir/packaging/codex-marketplace.json"
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

setup_plugin() {
  local plugin_dir="$PWD/plugins/mthds"

  info "Setting up plugin files..."
  rm -rf "$plugin_dir"
  mkdir -p "$plugin_dir"

  # Use cp -RL to dereference symlinks (mthds-codex/bin and
  # mthds-codex/skills/*/references are symlinks into the repo root; preserving
  # them as symlinks produces dangling links at the install destination).
  if [[ -n "$PLUGIN_SOURCE_DIR" ]]; then
    cp -RL "$PLUGIN_SOURCE_DIR/"* "$plugin_dir/"
    cp -RL "$PLUGIN_SOURCE_DIR/.codex-plugin" "$plugin_dir/"
    ok "Plugin copied from local build"
  else
    TMP_REPO_DIR=$(mktemp -d)
    if git clone --depth 1 --branch "$GITHUB_BRANCH" "https://github.com/$GITHUB_REPO.git" "$TMP_REPO_DIR" 2>&1; then
      PLUGIN_SOURCE_DIR="$TMP_REPO_DIR/mthds-codex"
      MARKETPLACE_SOURCE_FILE="$TMP_REPO_DIR/packaging/codex-marketplace.json"
      if [[ -d "$PLUGIN_SOURCE_DIR/.codex-plugin" ]]; then
        cp -RL "$PLUGIN_SOURCE_DIR/"* "$plugin_dir/"
        cp -RL "$PLUGIN_SOURCE_DIR/.codex-plugin" "$plugin_dir/"
        ok "Plugin cloned from GitHub ($GITHUB_BRANCH)"
      else
        fatal "mthds-codex/ not found in repository — build may be needed"
      fi
    else
      fatal "Failed to clone mthds-plugins — check network and GitHub access"
    fi
  fi
}

# Rewrites the canonical packaging/codex-marketplace.json (which points at the
# build-output dir ./mthds-codex) to the on-disk runtime path ./plugins/<name>
# where this installer copies each plugin. Canonical and runtime paths are
# intentionally different: the canonical file is validated by scripts/check.py
# against target configs, the runtime file is what Codex actually reads.
render_repo_local_marketplace() {
  local source_file="$1"
  node - "$source_file" <<'NODE'
const fs = require("fs");

const [sourceFile] = process.argv.slice(2);
const payload = JSON.parse(fs.readFileSync(sourceFile, "utf8"));

if (!Array.isArray(payload.plugins)) {
  throw new Error("marketplace.json missing plugins array");
}

for (const plugin of payload.plugins) {
  if (!plugin || typeof plugin !== "object" || typeof plugin.name !== "string" || plugin.name.length === 0) {
    throw new Error("marketplace.json contains plugin entry without a valid name");
  }
  if (!plugin.source || typeof plugin.source !== "object" || plugin.source.source !== "local") {
    throw new Error(`marketplace.json plugin '${plugin.name}' must use a local source`);
  }
  plugin.source = {
    ...plugin.source,
    path: `./plugins/${plugin.name}`,
  };
}

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE
}

setup_marketplace() {
  local marketplace_file="$PWD/.agents/plugins/marketplace.json"

  info "Setting up marketplace..."
  mkdir -p "$(dirname "$marketplace_file")"

  if [[ -z "$MARKETPLACE_SOURCE_FILE" || ! -f "$MARKETPLACE_SOURCE_FILE" ]]; then
    fatal "Canonical Codex packaging marketplace not found at $MARKETPLACE_SOURCE_FILE"
  fi

  if ! render_repo_local_marketplace "$MARKETPLACE_SOURCE_FILE" > "$marketplace_file"; then
    fatal "Failed to render repo-local marketplace.json from $MARKETPLACE_SOURCE_FILE"
  fi

  ok "Marketplace configured"
}

install_env_check() {
  local env_check_dir="$HOME/.codex/bin"
  local plugin_dir="$PWD/plugins/mthds"

  info "Installing mthds-env-check..."
  mkdir -p "$env_check_dir"

  if [[ -f "$plugin_dir/bin/mthds-env-check" ]]; then
    cp "$plugin_dir/bin/mthds-env-check" "$env_check_dir/mthds-env-check"
    chmod +x "$env_check_dir/mthds-env-check"
    ok "mthds-env-check installed to ~/.codex/bin/"
  else
    fatal "mthds-env-check not found in plugin at $plugin_dir/bin/mthds-env-check"
  fi
}

setup_hooks() {
  local hooks_dir="$HOME/.codex/hooks"

  info "Setting up hooks..."
  mkdir -p "$hooks_dir"

  # Copy hook script from plugin
  local plugin_dir="$PWD/plugins/mthds"
  if [[ -f "$plugin_dir/hooks/codex-validate-mthds.sh" ]]; then
    cp "$plugin_dir/hooks/codex-validate-mthds.sh" "$hooks_dir/codex-validate-mthds.sh"
    chmod +x "$hooks_dir/codex-validate-mthds.sh"
  else
    fatal "Hook script not found in plugin"
  fi

  # Delegate JSON merge to mthds-agent — handles idempotency, existing
  # hooks of other categories, and any hooks.json shape without clobbering.
  # Requires mthds-agent >= 0.4.1 (shipped via install_mthds_cli above).
  info "Merging Stop hook into ~/.codex/hooks.json..."
  if mthds-agent codex install-hook >/dev/null; then
    ok "Hooks merged into ~/.codex/hooks.json"
  else
    fatal "mthds-agent codex install-hook failed (see error above)"
  fi
}

enable_hooks_feature() {
  local config_file="$HOME/.codex/config.toml"

  info "Enabling hooks feature flag..."
  mkdir -p "$(dirname "$config_file")"

  if [[ -f "$config_file" ]]; then
    if grep -q "codex_hooks = true" "$config_file" 2>/dev/null; then
      ok "Hooks feature flag already enabled"
      return 0
    fi
    if grep -q "\[features\]" "$config_file" 2>/dev/null; then
      awk '/\[features\]/{print; print "codex_hooks = true"; next}1' "$config_file" > "${config_file}.tmp" && mv "${config_file}.tmp" "$config_file"
    else
      printf '\n[features]\ncodex_hooks = true\n' >> "$config_file"
    fi
  else
    cat > "$config_file" << 'CONFIG_EOF'
[features]
codex_hooks = true
CONFIG_EOF
  fi
  ok "Hooks feature flag enabled"
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

  if [[ -d "$PWD/plugins/mthds/.codex-plugin" ]]; then
    ok "Plugin files in place"
  else
    fail "Plugin files not found"
    all_ok=1
  fi

  if [[ -f "$PWD/.agents/plugins/marketplace.json" ]]; then
    ok "Marketplace configured"
  else
    fail "Marketplace not configured"
    all_ok=1
  fi

  if [[ -f "$HOME/.codex/hooks.json" ]] && grep -q "codex-validate-mthds" "$HOME/.codex/hooks.json" 2>/dev/null; then
    ok "Hooks configured"
  else
    fail "Hooks not configured (no codex-validate-mthds entry in ~/.codex/hooks.json)"
    all_ok=1
  fi

  if [[ -f "$HOME/.codex/hooks/codex-validate-mthds.sh" ]]; then
    ok "Hook script in place"
  else
    fail "Hook script not found"
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
  printf "${BOLD}MTHDS Codex Plugin Installer${RESET}\n"
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
  setup_plugin
  install_env_check
  setup_marketplace
  setup_hooks
  enable_hooks_feature
  echo ""

  info "Verifying..."
  if ! verify_install; then
    echo ""
    fail "Install may be incomplete — check errors above"
    return 1
  fi

  echo ""
  printf "${GREEN}${BOLD}Installed.${RESET}\n"
  echo ""
  printf "${YELLOW}Restart Codex, run /plugins, find MTHDS, and install it.${RESET}\n"
  echo ""
}

main "$@"
