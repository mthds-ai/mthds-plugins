# TODOS — Codex host support for mthds-agent update-check

## Context (cold start)

A user on the Codex desktop app ran `mthds-agent update-check --force` after upgrading the MTHDS Codex plugin to 0.10.1. Even though the Codex plugin was correctly upgraded, the agent reported:

```
plugin: outdated 0.10.0, required >=0.10.1
Warning: could not write update-check cache (EPERM). Check will run again next time.
```

Investigation showed two independent root causes. Both bugs sit in `mthds-js` (the package that produces the `mthds-agent` binary). The plugin repos (`mthds-plugins`) only need a `min_mthds_version` bump once the fix ships.

### Repo layout reminder

- `mthds-js/` → publishes the `mthds-agent` Node CLI (npm: `mthds`). All code changes happen here.
- `mthds-plugins/` → this repo. Generates Claude + Codex plugins, declares the minimum mthds-agent version in `targets/defaults.toml`.

### Root cause #1 — `mthds-agent` only knows the Claude plugin registry

`mthds-js/src/agent/plugin-version.ts:33-38` hardcodes the lookup to `~/.claude/plugins/installed_plugins.json`. Codex stores plugins in a completely different shape — see `codex-rs/core-plugins/src/store.rs` in the upstream Codex repo (`/Users/lchoquel/repos/OpenSource/codex/`):

- Path: `$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/.codex-plugin/plugin.json`
- `CODEX_HOME` defaults to `~/.codex`
- No registry JSON — the **version is the directory name**. `active_plugin_version()` (store.rs:68) sorts the dir names and picks the highest (or the literal `"local"` if present).

The user has:
- `~/.claude/plugins/installed_plugins.json` → `mthds@mthds-plugins` v0.10.0 (stale Claude install)
- `~/.codex/plugins/cache/mthds-plugins/mthds/0.10.1/.codex-plugin/plugin.json` → v0.10.1 (correct Codex install)

`mthds-agent` reads only the Claude file, sees 0.10.0, reports outdated. The `PLUGIN_UPDATE_CMD` constant at plugin-version.ts:30 (`"claude plugin install mthds@mthds-plugins"`) is also wrong under Codex (Codex uses the `/plugins install mthds` slash command, not a shell command).

### Root cause #2 — Codex sandbox blocks `~/.mthds/state/`

`mthds-js/src/agent/update-cache.ts:50-51` writes to `~/.mthds/state/last-update-check`. The user's Codex session uses `workspaceWrite` sandbox with `writable_roots = [<workspace_dir>]`. Per `codex-rs/protocol/src/protocol.rs:1156` (`SandboxPolicy::get_writable_roots_with_cwd`), `WorkspaceWrite` permits writes only under: configured roots, `cwd`, `/tmp`, and `$TMPDIR`. `~/.mthds/` is none of those → EPERM. The directory and file exist with correct Unix perms — the EPERM is from Seatbelt, not from filesystem permissions, and is not something the user can grant per-call.

### How gstack handles it (for reference)

Checked `gstack/bin/gstack-update-check` and `gstack/hosts/codex.ts`. gstack does **not** solve either problem — same EPERM under restricted sandbox, and gstack reads its own `$GSTACK_DIR/VERSION` file rather than any host registry. Not a model to copy; we need actual host-aware detection plus EPERM fallback.

---

## Plan

### Phase 1 — Host-aware plugin version detection (mthds-js)

Goal: `mthds-agent` correctly reports the installed plugin version under both Claude Code and Codex, and emits the right upgrade hint per host.

- [ ] **1.1** In `mthds-js/src/agent/plugin-version.ts`, introduce a host enum and detection helper.
  - `type PluginHost = "claude" | "codex" | null`
  - `function detectHost(): PluginHost` — order of checks:
    1. If `process.env.CODEX_HOME` is set OR `~/.codex/plugins/cache/` exists → `"codex"`
    2. Else if `~/.claude/plugins/installed_plugins.json` exists → `"claude"`
    3. Else `null` (not in a known host)
  - Reasoning: env-var first is robust for non-default `CODEX_HOME`. Fall back to filesystem probes for the common case. When both hosts have the plugin installed we still pick Codex if `CODEX_HOME` is set — that's the strongest signal that the current process was spawned from Codex.

- [ ] **1.2** Add a Codex-registry reader.
  - `function readCodexPluginVersion(): { version: string | null }` 
  - Resolve `codexHome = process.env.CODEX_HOME ?? join(homedir(), ".codex")`
  - For each `pluginName` in `["mthds", "mthds-dev"]`:
    - `dir = join(codexHome, "plugins", "cache", "mthds-plugins", pluginName)`
    - `readdirSync(dir)` (filter to directory entries, skip dotfiles)
    - If any entry equals `"local"` (Codex's dev sentinel — see `DEFAULT_PLUGIN_VERSION` at store.rs:14), return `{ version: "local" }` (don't nag — treat like `"unknown"` does today)
    - Else parse each name as semver via `semver.coerce`, sort, pick highest
    - Read `<dir>/<version>/.codex-plugin/plugin.json` and prefer its `version` field if present (handles cases where the directory was renamed); fall back to the directory name.
  - Return `{ version: null }` if no entries.
  - Wrap all `fs` calls in try/catch — return null on any error, don't throw.

- [ ] **1.3** Refactor `checkPluginVersion()` (plugin-version.ts:64) to:
  1. Call `detectHost()`. If null → return null (preserves current "not in any host" behavior).
  2. Switch on host:
     - `"claude"` → existing logic (read `installed_plugins.json`)
     - `"codex"` → call `readCodexPluginVersion()`, run the same semver compare as today
  3. Return the `BinaryCheckEntry` with `s/v/r` shape unchanged so callers (`update-check.ts:172`, `bootstrap.ts:222`) don't need to change.

- [ ] **1.4** Make `PLUGIN_UPDATE_CMD` host-aware.
  - Replace the constant export with a function `function pluginUpdateCommand(host: PluginHost): string`:
    - `"claude"` → `"claude plugin install mthds@mthds-plugins"` (current value)
    - `"codex"` → `"/plugins install mthds"` (Codex slash command — confirm exact form by checking how the user runs it; the user's transcript shows `/plugins install mthds`)
    - `null` → fall back to the Claude string (preserves current behavior for unknown contexts)
  - Update `bootstrap.ts:222-233` to call `detectHost()` once, pass it to both `checkPluginVersion()` and `pluginUpdateCommand()`, then emit `PLUGIN_UPDATE_AVAILABLE` with the right `cmd`.
  - Consider adding `host` to the emitted JSON payload so skill docs / preambles can render host-specific instructions.

- [ ] **1.5** Update tests in `mthds-js/tests/unit/agent/plugin-version.test.ts`:
  - Existing tests already mock `readFileSync` returning ENOENT — keep them, they exercise the Claude branch and the "not in any host" branch.
  - Add a parallel test block that mocks `readdirSync` + `statSync` for the Codex branch. Cover:
    - Single version dir → reported version
    - Multiple version dirs → highest wins
    - `local` sentinel → returns null (don't nag)
    - Mixed `mthds` + `mthds-dev` → `mthds` takes precedence (matches current `PLUGIN_KEYS` order)
    - Codex dir exists but is empty → `missing`
    - `CODEX_HOME` env override is respected
    - Plugin manifest version disagrees with dir name → manifest wins
  - Add `detectHost` unit tests covering the env-var / filesystem precedence.

**Checkpoint 1** — Phase 1 lands as a self-contained PR. After review and merge, the `mthds-js` patch can ship to npm (next mthds-js minor — likely 0.6.3). Code freeze any other agent CLI changes until this is in. Document the new `PLUGIN_UPDATE_AVAILABLE` payload shape (add `host` field) in `pipelex/docs/contracts/mthds-agent-cli.md` if that field is added.

### Phase 2 — Sandbox-safe cache writes (mthds-js)

Goal: When `~/.mthds/state/last-update-check` is unwritable (Codex sandbox), fall back to a writable location instead of warning every run.

- [ ] **2.1** In `mthds-js/src/agent/update-cache.ts`, introduce a `resolveCachePath()` helper that returns the path to use for reads + writes:
  - Primary: `~/.mthds/state/last-update-check` (today's `CACHE_PATH`)
  - Fallback: `join(tmpdir(), "mthds-agent", "last-update-check")` — use `os.tmpdir()` which respects `TMPDIR` (always writable under Codex `workspaceWrite` unless `excludeTmpdirEnvVar` is set, in which case `/tmp` still works as long as `excludeSlashTmp` is also false; if both are excluded, the user is opting into pain and we just warn once).
  - The function probes by attempting `mkdirSync(dir, { recursive: true })` then a `fs.accessSync(dir, W_OK)` on the parent. Cache the resolved path in a module-level variable so we don't probe on every call within the same process.

- [ ] **2.2** Update `writeCache()` (update-cache.ts:150):
  - On EPERM/EACCES/EROFS, retry with the fallback path.
  - If the fallback also fails, emit the existing warning **once per process** (track via a module-level flag) instead of on every invocation.
  - On fallback success, do NOT print a warning — silent fallback is the right behavior; spamming stderr scared the user.

- [ ] **2.3** Update `readCache()` (update-cache.ts:111):
  - Try primary path first.
  - If primary returns null (missing/expired/corrupt), try fallback path.
  - Return whichever yields a valid `CacheResult`.

- [ ] **2.4** Update `clearCache()` (update-cache.ts:165):
  - Delete both primary and fallback paths. Ignore ENOENT on either.

- [ ] **2.5** Tests in `mthds-js/tests/unit/agent/update-cache.test.ts`:
  - Add a test where the primary path throws EPERM on write → expect fallback to be written.
  - Add a test where the primary write succeeds → fallback should NOT be created.
  - Add a test that `readCache()` reads the fallback when the primary doesn't exist.
  - Add a test that the warning fires at most once per process when both writes fail.

**Checkpoint 2** — Phases 1 + 2 ship together as `mthds-agent` 0.6.3. Manually verify the EPERM fallback inside an actual Codex `workspaceWrite` session before tagging the release (see verification block below).

### Phase 3 — Plugin-side wiring (mthds-plugins, this repo)

Goal: Bump the minimum `mthds-agent` version so the plugin's preamble nags users until they upgrade past the bug.

- [ ] **3.1** Bump `targets/defaults.toml [vars].min_mthds_version` to the version released in Checkpoint 2 (likely `0.6.3`).
- [ ] **3.2** Bump `targets/prod.toml [plugin].version` and `targets/codex.toml [plugin].version` to the next plugin version (e.g. 0.10.2). Dev target bumps if also being released.
- [ ] **3.3** Run `make build` to regenerate `mthds/` and the Codex target. Verify no other template variables changed unexpectedly.
- [ ] **3.4** Run `make check` (covers `check-shared`, `check-claude`, `check-codex`). Fix anything that breaks.
- [ ] **3.5** Update `CHANGELOG.md` with a 0.10.2 entry naming both fixes (host-aware plugin version detection + sandbox-safe cache writes). Reference the bug symptoms so users searching for "EPERM" / "plugin outdated 0.10.0" find it.
- [ ] **3.6** Release per `release` skill (cuts the release branch, opens PR to main).

### Verification (manual, before tagging mthds-agent 0.6.3)

- [ ] **V1** Install the patched `mthds` build globally (`npm install -g .` from the mthds-js workspace) so `mthds-agent` points at the new code. Confirm via `which mthds-agent` and `mthds-agent --version`.
- [ ] **V2** In Claude Code, run `mthds-agent update-check --force`. Expect: `plugin: ok <version>` (or whatever the actual installed version is). No EPERM warning. Behavior matches today for the Claude path.
- [ ] **V3** In a Codex session with `workspaceWrite` sandbox + a workspace OUTSIDE `~/.codex` and `~/.mthds`, run `mthds-agent update-check --force`:
  - Plugin should be detected from the Codex registry (~/.codex/plugins/cache/...).
  - Cache file should land in `$TMPDIR/mthds-agent/last-update-check`.
  - No EPERM warning.
  - `PLUGIN_UPDATE_AVAILABLE` (if emitted) should suggest `/plugins install mthds`, not `claude plugin install ...`.
- [ ] **V4** Repeat V3 after explicitly setting `CODEX_HOME` to a non-default dir. The agent must respect the env var.
- [ ] **V5** Repeat V3 with the user's actual environment to confirm their exact failure mode is fixed: plugin reports current version, no EPERM warning.

### Out of scope (do not do as part of this work)

- Don't add a `mthds-agent codex` subcommand or special-case the Codex hook path — that's already handled separately in `mthds-agent codex install-hook` (see CLAUDE.md "PostToolUse Hook" section).
- Don't change `JUST_UPGRADED_PATH` / upgrade marker plumbing in this PR. If it has the same EPERM problem, fix in a follow-up — keep this PR scoped to the update-check flow that the user hit.
- Don't try to widen Codex's sandbox to include `~/.mthds/`. That's a Codex policy decision, not something the agent should require.
- Don't write a registry-shim or a "fake installed_plugins.json" inside `~/.codex/`. Read Codex's real layout.

---

## Files to touch

| File | Change |
| --- | --- |
| `mthds-js/src/agent/plugin-version.ts` | Add `detectHost()`, `readCodexPluginVersion()`, `pluginUpdateCommand()`. Refactor `checkPluginVersion()`. |
| `mthds-js/src/agent/commands/bootstrap.ts` | Use `pluginUpdateCommand(host)` instead of the old constant. |
| `mthds-js/src/agent/update-cache.ts` | Add `resolveCachePath()`. Update `readCache`, `writeCache`, `clearCache`. |
| `mthds-js/tests/unit/agent/plugin-version.test.ts` | Codex-branch tests, host-detection tests. |
| `mthds-js/tests/unit/agent/update-cache.test.ts` | EPERM-fallback tests. |
| `mthds-js/CHANGELOG.md` | 0.6.3 entry. |
| `mthds-js/package.json` | Version bump. |
| `mthds-plugins/targets/defaults.toml` | `min_mthds_version` bump. |
| `mthds-plugins/targets/prod.toml`, `codex.toml` | Plugin version bumps. |
| `mthds-plugins/CHANGELOG.md` | 0.10.2 entry. |
| `mthds-plugins/mthds/`, `mthds-codex/` | Regenerated by `make build`. |
| `pipelex/docs/contracts/mthds-agent-cli.md` (optional) | Document new `host` field if added to `PLUGIN_UPDATE_AVAILABLE`. |

## Key code references

- Plugin version reader (the bug): `mthds-js/src/agent/plugin-version.ts:33-38`, `:64-124`
- Update command constant: `mthds-js/src/agent/plugin-version.ts:30`
- Cache writer (EPERM site): `mthds-js/src/agent/update-cache.ts:50-51`, `:150-162`
- Cache reader: `mthds-js/src/agent/update-cache.ts:111-147`
- Codex plugin store layout: `OpenSource/codex/codex-rs/core-plugins/src/store.rs:14-16`, `:51-95`
- Codex sandbox writable-root rules: `OpenSource/codex/codex-rs/protocol/src/protocol.rs:1156-1230`
- User's live sandbox config: `~/.codex/.codex-global-state.json` under `heartbeat-thread-permissions-by-id.<thread>.sandboxPolicy`
