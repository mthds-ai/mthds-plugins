#!/usr/bin/env bash
# install.sh — install the MTHDS Claude Code plugin
#
# Usage:
#   bash install.sh          # install (idempotent — safe to re-run)
#   bash install.sh --check  # verify existing install (no changes)
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

  if command_exists claude; then
    ok "claude $(claude --version 2>/dev/null | head -1)"
  else
    fail "claude not found — install from https://claude.ai/code"
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

add_marketplace() {
  # Check if already added
  if claude plugin marketplace list 2>/dev/null | grep -q "mthds-plugins"; then
    ok "Marketplace already configured"
    return 0
  fi

  info "Adding mthds-plugins marketplace..."
  if claude plugin marketplace add mthds-ai/mthds-plugins 2>&1; then
    ok "Marketplace added"
  else
    fatal "Failed to add marketplace — check network and GitHub access"
  fi
}

install_plugin() {
  # Check if already installed (exact match — avoid matching mthds-dev)
  if claude plugin list 2>/dev/null | grep -qE '(^|[[:space:]])mthds([[:space:]]|$)'; then
    ok "Plugin already installed"
    return 0
  fi

  info "Installing mthds plugin..."
  if claude plugin install mthds@mthds-plugins 2>&1; then
    ok "Plugin installed"
  else
    fatal "Failed to install plugin"
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

  if claude plugin list 2>/dev/null | grep -qE '(^|[[:space:]])mthds([[:space:]]|$)'; then
    ok "mthds plugin registered"
  else
    fail "mthds plugin not found in Claude Code"
    all_ok=1
  fi

  return $all_ok
}

# ── Main ───────────────────────────────────────────────────────────

main() {
  local check_only=0
  [ "${1:-}" = "--check" ] && check_only=1

  echo ""
  printf "${BOLD}MTHDS Plugin Installer${RESET}\n"
  echo ""

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
  add_marketplace
  install_plugin
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
  printf "${YELLOW}Restart Claude Code to activate:${RESET} /exit then ${BOLD}claude${RESET}\n"
  echo ""
}

main "$@"
