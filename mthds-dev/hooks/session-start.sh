#!/usr/bin/env bash
# SessionStart hook: display installed MTHDS tool versions (dev only)
set -uo pipefail
exec 2>/dev/null

# If mthds-agent is not installed, report and exit
if ! command -v mthds-agent &>/dev/null; then
  echo "MTHDS stack: mthds-agent NOT INSTALLED (npm install -g /build-src/mthds-js/)"
  exit 0
fi

MTHDS_VER=$(mthds-agent --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "?")

# Get tool versions from doctor --format json
DOCTOR_JSON=$(mthds-agent doctor --format json 2>/dev/null) || {
  echo "MTHDS stack: mthds-agent $MTHDS_VER"
  exit 0
}

# Parse with node (guaranteed available since mthds-agent requires it)
node -e "
const doc = JSON.parse(process.argv[1]);
const deps = doc.dependencies || [];
const parts = ['mthds-agent $MTHDS_VER'];

for (const dep of deps) {
  if (dep.binary === 'pipelex-agent') continue;
  parts.push(dep.binary + ' ' + (dep.installed ? dep.version : 'MISSING'));
}

try {
  const fs = require('fs');
  const os = require('os');
  const path = require('path');
  const fp = path.join(os.homedir(), '.claude', 'plugins', 'installed_plugins.json');
  const data = JSON.parse(fs.readFileSync(fp, 'utf-8'));
  const keys = ['mthds@mthds-plugins', 'mthds-dev@mthds-plugins'];
  let pv = null;
  for (const k of keys) {
    const entries = data.plugins?.[k];
    if (entries?.length) {
      const entry = entries.find(x => x.scope === 'user') || entries[0];
      pv = entry.version;
      break;
    }
  }
  parts.push('plugin ' + (pv || 'NOT INSTALLED'));
} catch { parts.push('plugin N/A'); }

console.log('MTHDS stack: ' + parts.join(', '));
" "$DOCTOR_JSON"
exit 0
