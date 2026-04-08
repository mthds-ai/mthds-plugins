#!/usr/bin/env bash
# install-codex.sh — install the MTHDS Codex plugin
#
# Usage:
#   bash install-codex.sh          # install (always overwrites)
#   bash install-codex.sh --check  # verify existing install (no changes)
#
# Exit codes:
#   0 — success
#   1 — prerequisite missing or install failed

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
GITHUB_BRANCH="feature/codex-plugin"
PLUGIN_SOURCE_DIR=""

resolve_plugin_source() {
  # If run from the mthds-plugins repo, use local mthds-codex/ directory
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_dir
  repo_dir="$(dirname "$script_dir")"

  if [[ -d "$repo_dir/mthds-codex/.codex-plugin" ]]; then
    PLUGIN_SOURCE_DIR="$repo_dir/mthds-codex"
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

install_mthds_cli() {
  if command_exists mthds-agent; then
    local ver
    ver=$(version_of mthds-agent)
    if [ -n "$ver" ]; then
      ok "mthds-agent $ver (already installed)"
      return 0
    fi
  fi

  info "Installing mthds npm package globally..."
  if npm install -g mthds 2>&1; then
    ok "mthds-agent $(version_of mthds-agent || echo 'installed')"
  else
    fatal "npm install -g mthds failed — check npm permissions"
  fi
}

setup_plugin() {
  local plugin_dir="$HOME/.codex/plugins/mthds"

  info "Setting up plugin files..."
  rm -rf "$plugin_dir"
  mkdir -p "$plugin_dir"

  if [[ -n "$PLUGIN_SOURCE_DIR" ]]; then
    cp -R "$PLUGIN_SOURCE_DIR/"* "$plugin_dir/"
    cp -R "$PLUGIN_SOURCE_DIR/.codex-plugin" "$plugin_dir/"
    ok "Plugin copied from local build"
  else
    local tmp_dir
    tmp_dir=$(mktemp -d)
    if git clone --depth 1 --branch "$GITHUB_BRANCH" "https://github.com/$GITHUB_REPO.git" "$tmp_dir" 2>&1; then
      if [[ -d "$tmp_dir/mthds-codex/.codex-plugin" ]]; then
        cp -R "$tmp_dir/mthds-codex/"* "$plugin_dir/"
        cp -R "$tmp_dir/mthds-codex/.codex-plugin" "$plugin_dir/"
        ok "Plugin cloned from GitHub ($GITHUB_BRANCH)"
      else
        rm -rf "$tmp_dir"
        fatal "mthds-codex/ not found in repository — build may be needed"
      fi
    else
      rm -rf "$tmp_dir"
      fatal "Failed to clone mthds-plugins — check network and GitHub access"
    fi
    rm -rf "$tmp_dir"
  fi
}

setup_marketplace() {
  local marketplace_file="$HOME/.agents/plugins/marketplace.json"

  info "Setting up marketplace..."
  mkdir -p "$(dirname "$marketplace_file")"

  cat > "$marketplace_file" << 'MARKETPLACE_EOF'
{
  "name": "mthds-plugins",
  "interface": {
    "displayName": "MTHDS Plugins"
  },
  "plugins": [
    {
      "name": "mthds",
      "source": {
        "source": "local",
        "path": "~/.codex/plugins/mthds"
      },
      "policy": {
        "installation": "AVAILABLE"
      },
      "category": "Developer Tools"
    }
  ]
}
MARKETPLACE_EOF
  ok "Marketplace configured"
}

setup_hooks() {
  local hooks_file="$HOME/.codex/hooks.json"
  local hooks_dir="$HOME/.codex/hooks"

  info "Setting up hooks..."
  mkdir -p "$hooks_dir"

  # Copy hook script from plugin
  local plugin_dir="$HOME/.codex/plugins/mthds"
  if [[ -f "$plugin_dir/hooks/codex-validate-mthds.sh" ]]; then
    cp "$plugin_dir/hooks/codex-validate-mthds.sh" "$hooks_dir/codex-validate-mthds.sh"
    chmod +x "$hooks_dir/codex-validate-mthds.sh"
  else
    fatal "Hook script not found — run setup_plugin first"
  fi

  cat > "$hooks_file" << 'HOOKS_EOF'
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.codex/hooks/codex-validate-mthds.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
HOOKS_EOF
  ok "Hooks configured"
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
      sed -i.bak '/\[features\]/a\
codex_hooks = true' "$config_file"
      rm -f "${config_file}.bak"
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

  if [[ -d "$HOME/.codex/plugins/mthds/.codex-plugin" ]]; then
    ok "Plugin files in place"
  else
    fail "Plugin files not found"
    all_ok=1
  fi

  if [[ -f "$HOME/.agents/plugins/marketplace.json" ]]; then
    ok "Marketplace configured"
  else
    fail "Marketplace not configured"
    all_ok=1
  fi

  if [[ -f "$HOME/.codex/hooks.json" ]]; then
    ok "Hooks configured"
  else
    fail "Hooks not configured"
    all_ok=1
  fi

  if [[ -f "$HOME/.codex/hooks/codex-validate-mthds.sh" ]]; then
    ok "Hook script in place"
  else
    fail "Hook script not found"
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
  printf "${YELLOW}Restart Codex and run /plugins to install mthds.${RESET}\n"
  echo ""
}

main "$@"
