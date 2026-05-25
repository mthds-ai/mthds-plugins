# Handoff — Plugin floor bump v0.11.3 (paused 2026-05-25)

**Status:** Paused mid-PR. Working tree has the floor bump staged but uncommitted. PR is blocked on an upstream pipelex fix that surfaced during verification. Resume after pipelex 0.30.1 and mthds-js 0.8.1 ship.

**Branch:** `fix/Pipelex-output-changes` (one commit ahead of `main`: `3193799 feat(todos): add working plan for adapting mthds-plugins to pipelex 0.29.x output changes`)

**Repo:** `/Users/lchoquel/repos/Pipelex/mthds-plugins`

---

## Why this PR exists

mthds-js shipped 0.8.0 (npm) and pipelex shipped 0.30.0 (PyPI) on 2026-05-25. mthds-js 0.8.0 raised its pipelex/pipelex-agent floor to `>=0.30.0` and fixed five `PipelexRunner` `JSON.parse` paths broken by pipelex 0.29.0's agent CLI output-contract changes. pipelex 0.30.0 additionally routed logs to stderr (was stdout, which broke JSON consumers).

The plugin needs to:
1. Raise `min_mthds_version` from 0.7.0 to whatever mthds-js floor release pulls in clean pipelex output (originally 0.8.0; now blocked on 0.8.1 — see below).
2. Cut a plugin patch release (originally 0.11.3) so the floor-bump propagates via plugin upgrade prompts.
3. Adapt any plugin-side code that broke under the new output contract.

See `TODOS.md` in this repo for the full original plan (Phases 1-5). This handoff is the Phase 5 execution, paused mid-flight.

---

## What's already done (working tree, uncommitted)

`git diff HEAD --stat` shows 61 modified files = 5 source edits + 56 regenerated artifacts:

**Source edits (5):**
- `targets/defaults.toml`: `min_mthds_version = "0.7.0"` → `"0.8.0"` *(needs updating to 0.8.1 — see Blocker section)*
- `targets/prod.toml`: plugin `version = "0.11.2"` → `"0.11.3"`
- `targets/dev.toml`: plugin `version = "0.11.2"` → `"0.11.3"`
- `targets/codex.toml`: plugin `version = "0.11.2"` → `"0.11.3"`
- `.claude-plugin/marketplace.json`: `metadata.version` `"0.11.2"` → `"0.11.3"`
- `CHANGELOG.md`: new `## [v0.11.3] - 2026-05-25` entry *(prose needs rewriting — see Resume Plan)*
- `TODOS.md`: `0.29.1` → `0.30.0` string refreshes + new "Upstream status (updated 2026-05-25)" subsection *(committed in `3193799` for the version refreshes; the new subsection is in working tree)*

**Regenerated artifacts (56):** All `mthds/`, `mthds-dev/`, `mthds-codex/` skill `SKILL.md` frontmatter (`min_mthds_version: 0.8.0`) and `shared/preamble.md` (env-check exec arg `"0.8.0"`). Produced by `make build`. Will need re-running after `defaults.toml` updates to the final floor value.

**Validation done:**
- `make check` — green
- `make test` — 116/116 passing
- Integration tests via Docker (TODOS Phase 5.5) — **NOT run** (Docker wasn't started this session)

---

## Verification findings (the blocker)

During code review, three of the three high-priority candidates verified as real bugs. See the verification commands at the end for re-running.

### 1. Hook IS silently broken on the new floor (CONFIRMED)

`templates/hooks/validate-mthds.sh.j2:93` invokes `mthds-agent validate bundle "$FILE_PATH" -L "$PARENT_DIR/"` and the Node parser at line 107 parses stderr as JSON to extract `validation_errors[]` for the block decision.

**Verification (run today with mthds-agent 0.8.0 + pipelex 0.30.0 + plxt 0.4.0):**

```
$ mthds-agent validate bundle wip/bad_bundle.mthds -L wip/ 2>stderr.txt
$ head -3 stderr.txt
DEBUG    🧠: Telemetry is disabled because posthog.mode  telemetry_factory.py:77
         is set to 'off'
# Error: LibraryError
```

Stderr is markdown, not JSON. `JSON.parse(stderr)` fails. Hook hits the "unexpected output, warn and pass" branch (lines 110-113) and **broken `.mthds` files are no longer blocked**. The safety net is silently off.

### 2. Adding `--error-format json` is necessary but NOT sufficient (FIXED in pipelex)

```
$ mthds-agent validate bundle wip/bad_bundle.mthds -L wip/ --error-format json 2>stderr.txt
$ head -3 stderr.txt
DEBUG    🧠: Telemetry is disabled because posthog.mode  telemetry_factory.py:77
         is set to 'off'
{
```

pipelex correctly emits the JSON envelope to stderr — but a leading `DEBUG` telemetry log line pollutes stderr. `JSON.parse(entire_stderr)` still fails.

Source: `pipelex/system/telemetry/telemetry_factory.py:77`:

```python
log.debug("Telemetry is disabled because posthog.mode is set to 'off'")
```

**Original misdiagnosis (recorded here so we don't repeat it):** The earlier note said this "fires at telemetry-factory init, before user log-config kicks in." That is wrong. `log.configure(...)` runs in `Pipelex.__init__` (`pipelex.py:119`) BEFORE `setup()` calls `TelemetryFactory.make_telemetry_manager` (`pipelex.py:272`). Logging IS configured when this line fires.

**Actual cause:** the user's `~/.pipelex/pipelex_override.toml` sets `[pipelex.log_config.package_log_levels] pipelex = "DEBUG"`. Per-package log levels override the root `default_log_level` (applied at `log.py:127` AFTER root), so a `PIPELEX_LOG_LEVEL=ERROR` / `LOG_LEVEL=ERROR` env var — even if it had been wired — would still lose to the per-package override. The DEBUG log fires through fully-configured logging.

**Fix landed in pipelex (NOT released yet — pending 0.30.1):**

The fix is in `pipelex/cli/agent_cli/commands/agent_cli_factory.py`, NOT in `telemetry_factory.py`. The agent CLI factory now pins `default_log_level = OFF` AND `package_log_levels.pipelex = OFF` via `config_overrides` injected into `Pipelex.make()`, so ALL pipelex logs (DEBUG / INFO / WARNING / ERROR / CRITICAL) are suppressed from the very first `log.configure` call — beating any user-TOML override. The agent CLI is machine-consumed: stderr is reserved exclusively for the structured `agent_error` envelope, with no log lines mixed in. There is no `--log-level` flag — suppression is unconditional by design.

Key changes:
- `pipelex/cli/agent_cli/commands/agent_cli_factory.py`: `AGENT_CLI_STDERR_LOG_FIELDS` pins `default_log_level = OFF` and `package_log_levels.pipelex = OFF`. New `AGENT_CLI_CONFIG_OVERRIDES` constant wraps it in the full config-tree shape for `Pipelex.make`. `apply_agent_cli_output_discipline()` and `make_pipelex_for_agent_cli()` no longer take a `log_level` parameter.
- `pipelex/cli/agent_cli/_agent_cli.py`: `--log-level` flag removed from the app callback. No more `ctx.obj["log_level"]`.
- All callers of `make_pipelex_for_agent_cli(...)` (10 sites: validate/run/inputs/models/check-model) drop the `log_level=ctx.obj["log_level"]` arg.
- `pipelex/cli/commands/doctor_cmd.py::setup_doctor_runtime` switched from flat-merge to `deep_update` so the package-log-levels merge preserves third-party levels (anthropic, asyncio, ...) instead of replacing the dict wholesale.

Verified end-to-end with the user's `~/.pipelex/pipelex_override.toml` still setting `pipelex = "DEBUG"`:
- `mthds-agent validate bundle bad_bundle.mthds -L . --error-format json 2>stderr.txt` → stderr is a single clean JSON document, `json.load(stderr)` parses.
- `mthds-agent validate bundle bad_bundle.mthds -L . 2>stderr.txt` (markdown error mode, no `--error-format`) → stderr is the clean markdown error envelope with no DEBUG or WARNING preamble.

For users who want to debug pipelex behavior, the human `pipelex` CLI (not `pipelex-agent`) is the right surface — it respects the user's TOML log config.

### 3. Graph flag rename — docs are stale (CONFIRMED)

`pipelex-agent validate bundle --help` confirms:
- `--graph` / `-g` (boolean) — enable graph output
- `--graph-format` / `-f [mermaidflow|reactflow|both]` — format choice (was `--format` in pre-0.29)
- `--format [json|markdown]` — separate flag, overall output format

`templates/skills/shared/mthds-agent-guide.md.j2:243` still documents the graph flag as `--format <format>` — anyone following the skill on the new floor will hit "unknown option" or get the wrong behavior.

`templates/skills/shared/mthds-agent-guide.md.j2:246` ("The JSON output includes `graph_files` with the paths to generated files") is only true with `--format json`; default is now markdown.

### 4. CHANGELOG entry sentence is provably false

Current draft says:

> The plugin shells out only to `mthds-agent` (never directly to `pipelex-agent`), so no skill, hook, or script invocations needed adapting beyond the floor.

The hook (#1 above) demonstrably needs adapting. Drop this sentence or rewrite it accurately when resuming.

### 5. TODOS upstream-status block contradicts reality

`TODOS.md` (working tree) lines ~18-22 added an "Upstream status (updated 2026-05-25)" subsection that says pipelex 0.30.0 and mthds-js 0.8.0 are "Not yet merged ... Not yet published." Both ARE published as of 2026-05-25 — that's the premise of this PR. Delete the subsection or rewrite it as "Released 2026-05-25."

### 6. Pre-existing stale doc

`docs/build-targets.md:46` example shows `min_mthds_version = "0.3.3"`. Drift across many bumps. Floor bump is the natural moment to refresh per workspace CLAUDE.md's "flag and fix existing bugs" rule.

---

## The release sequence (decided)

`pipelex 0.30.1` → `mthds-js 0.8.1` → `plugin v0.11.3`

1. **pipelex 0.30.1 (in `/Users/lchoquel/repos/Pipelex/pipelex/`):** the fix is LANDED IN SOURCE on the local working tree (see "Verification findings #2" above). The agent CLI factory unconditionally silences pipelex logs (`pipelex = OFF`) via `config_overrides` so neither init-time DEBUG nor command-time WARNING ever reaches stderr regardless of the user's TOML. `--log-level` flag removed. End-to-end verification confirmed: stderr is a single clean envelope (JSON or markdown) under the user's `pipelex = "DEBUG"` override. Run quality checks, cut 0.30.1, publish to PyPI.
2. **mthds-js 0.8.1 (in `/Users/lchoquel/repos/Pipelex/mthds-js/`):** raise pipelex/pipelex-agent floor to `>=0.30.1`. Cut 0.8.1, publish to npm.
3. **plugin v0.11.3 (THIS REPO):** raise `min_mthds_version` to `0.8.1`, add `--error-format json` to the validate hook, fix the smaller bugs, rewrite the CHANGELOG entry honestly, ship.

---

## Resume plan (cold-start checklist)

When resuming in a fresh session, in order:

### Pre-flight

- [ ] Confirm pipelex 0.30.1 (or newer) is on PyPI: `pip index versions pipelex` or `uv tool install pipelex@latest --reinstall`.
- [ ] Confirm mthds-js 0.8.1 (or newer) is on npm: `npm view mthds version`.
- [ ] Confirm local install is current: `mthds-agent --version` should show `>=0.8.1`. `mthds-agent doctor --format json | python3 -c "import json,sys; [print(x['binary'],x.get('version')) for x in json.load(sys.stdin)['dependencies']]"` should show pipelex `>=0.30.1`.
- [ ] Re-run the hook verification (commands in "Verification commands" section below). Confirm stderr with `--error-format json` parses cleanly as JSON now.

### Update the working tree

- [ ] `cd /Users/lchoquel/repos/Pipelex/mthds-plugins && git status` — confirm working tree still has the partial bump from 2026-05-25.
- [ ] Edit `targets/defaults.toml`: bump `min_mthds_version` to the actual published mthds-js version (e.g. `"0.8.1"`).
- [ ] Edit `templates/hooks/validate-mthds.sh.j2:93` to add `--error-format json` to the `mthds-agent validate bundle` invocation. Add a one-line comment explaining why: "pipelex 0.29+ defaults stderr to markdown; the JSON parser below requires structured output."
- [ ] Edit `templates/skills/shared/mthds-agent-guide.md.j2`:
  - Line ~243: `--format <format>` → `--graph-format <format>` for the graph flag.
  - Line ~246: reword the `graph_files` claim — drop "JSON output" framing, say "when `--format json` is set, the JSON envelope includes `graph_files`; otherwise the paths appear in stderr logs."
- [ ] Edit `docs/build-targets.md:46`: `min_mthds_version = "0.3.3"` → current canonical value.
- [ ] Edit `TODOS.md` lines ~18-22: delete the "Upstream status (updated 2026-05-25)" subsection or rewrite as "Released 2026-05-25; floor bumped in v0.11.3."
- [ ] Edit `CHANGELOG.md` v0.11.3 entry:
  - Drop the sentence "no skill, hook, or script invocations needed adapting beyond the floor."
  - Add a `### Fixed` section: "PostToolUse validate hook no longer silently passes broken `.mthds` files on pipelex `>=0.30`. The hook now opts into JSON stderr via `--error-format json`; previously it relied on pipelex's pre-0.29 default of JSON-on-stderr, which flipped to markdown in 0.29.0 and silently broke the parser."

### Rebuild and verify

- [ ] `make build` to regenerate all targets.
- [ ] `make check` — must be green.
- [ ] `make test` — must be 116/116 (may have grown).
- [ ] Smoke test the hook locally: write a broken `.mthds` (the one in `wip/bad_bundle.mthds` has `pipe.build_scorecard_oops` while `screen_all_candidates` references `build_scorecard` — guaranteed `LibraryError`). Run the rendered `mthds-dev/hooks/validate-mthds.sh` against it manually and confirm it BLOCKS (not warn-and-passes).
- [ ] If Docker is available: `make build && make agent-test` from workspace root for the internal-tools integration tests (TODOS Phase 5.5).

### Ship

- [ ] Decide PR title: original ask was `chore: bump min versions for mthds-js 0.8.0 / pipelex 0.30.0` — adjust version numbers, and since the hook fix is bundled, `chore:` may want to become `fix:` for the safety-net regression. Probably: `fix: restore .mthds validation safety net + bump floors for mthds-js 0.8.1 / pipelex 0.30.1`.
- [ ] Commit, push, open PR to `main`. Branch is `fix/Pipelex-output-changes` (already on it).
- [ ] User wants to see the diff before any push or PR creation.

### Explicit out of scope (still deferred)

- TODOS Phase 3 (skill doc markdown-first rewrite for `run` / `validate` / `init`) — quality-of-life, not safety. Follow-up PR.
- TODOS Phase 4 (`/mthds-fix` skill pinning `--format json`) — `/mthds-fix` is run-on-demand by a user; a misparse is loud, not silent. Confirmed-needed but deferrable.

---

## Verification commands (to re-run on resume)

Bundle used for verification is already in the repo: `wip/bad_bundle.mthds`. It contains `[pipe.build_scorecard_oops]` (note suffix) while `[pipe.screen_all_candidates]` references `pipe = "build_scorecard"` — guaranteed `LibraryError / PipeNotFoundError` on validate.

```bash
# 1. Setup
cd /tmp && rm -rf hook_verify && mkdir hook_verify
cp /Users/lchoquel/repos/Pipelex/mthds-plugins/wip/bad_bundle.mthds hook_verify/
cd hook_verify

# 2. Repro the silent-pass bug (without --error-format json)
mthds-agent validate bundle bad_bundle.mthds -L ./ >stdout.txt 2>stderr.txt
echo "exit: $?"
head -5 stderr.txt
python3 -c "import json; json.load(open('stderr.txt'))"  # must FAIL today (markdown stderr)

# 3. Test with --error-format json (after pipelex 0.30.1 ships, this MUST succeed)
mthds-agent validate bundle bad_bundle.mthds -L ./ --error-format json >stdout2.txt 2>stderr2.txt
echo "exit: $?"
head -5 stderr2.txt
python3 -c "
import json
d = json.load(open('stderr2.txt'))
print('PARSED OK')
print('error_type:', d.get('error_type'))
print('validation_errors:', len(d.get('validation_errors', [])))
"
# Pass criterion: no leading DEBUG line in stderr2.txt, json.load succeeds.

# 4. Confirm flag rename
pipelex-agent validate bundle --help | grep -E "graph|format" | head -10
# Expect: --graph-format, NOT --format <reactflow|mermaidflow|both>
```

---

## Files touched in this session (for the curious)

```
working tree (uncommitted):
M  .claude-plugin/marketplace.json     (0.11.2 → 0.11.3)
M  CHANGELOG.md                        (new v0.11.3 entry — needs rewrite)
M  TODOS.md                            (upstream-status subsection added — DELETE on resume)
M  mthds-codex/.codex-plugin/plugin.json (regenerated, 0.11.3)
M  mthds-codex/skills/**/*.md         (regenerated, min_mthds_version: 0.8.0 — will need 0.8.1 rerender)
M  mthds-dev/.claude-plugin/plugin.json (regenerated, 0.11.3)
M  mthds-dev/skills/**/*.md            (regenerated)
M  mthds/.claude-plugin/plugin.json    (regenerated, 0.11.3)
M  mthds/skills/**/*.md                (regenerated)
M  targets/codex.toml                  (0.11.2 → 0.11.3)
M  targets/defaults.toml               (0.7.0 → 0.8.0 — bump to 0.8.1 on resume)
M  targets/dev.toml                    (0.11.2 → 0.11.3)
M  targets/prod.toml                   (0.11.2 → 0.11.3)

(57 generated files; sources are: targets/*.toml + templates/**/*.j2)
```

You can either:
- **Keep working tree as-is** and patch the floor value + add hook fix + smaller bugs on resume (saves re-running `make build` once).
- **Revert and start clean** with `git restore .` then re-execute from the resume plan above (cleaner but redoes the bump mechanics).

Either is fine; recap is self-contained.

---

## References

- `TODOS.md` — original 5-phase plan with full diagnosis and decision history (read this first if anything in this handoff is unclear).
- `CLAUDE.md` (workspace and repo) — development principles, especially "no backward compatibility", "flag and fix existing bugs".
- `.claude/skills/bump-mthds-version/SKILL.md` — canonical floor-bump workflow (defaults.toml edit → `make build` → `make check`).
- `.claude/skills/release/` — release workflow if you want to use it instead of hand-edits.
- pipelex repo: `/Users/lchoquel/repos/Pipelex/pipelex/`. Files changed for 0.30.1 (already on working tree):
  - `pipelex/cli/agent_cli/commands/agent_cli_factory.py` — `AGENT_CLI_STDERR_LOG_FIELDS` pins log targets + `default_log_level=OFF` + `package_log_levels.pipelex=OFF`. New `AGENT_CLI_CONFIG_OVERRIDES` constant. `make_pipelex_for_agent_cli` and `apply_agent_cli_output_discipline` no longer take a `log_level` arg.
  - `pipelex/cli/agent_cli/_agent_cli.py` — `--log-level` flag removed from the app callback.
  - All 10 agent CLI commands (`validate/`, `run/`, `inputs/`, `models_cmd.py`, `check_model_cmd.py`) — dropped `log_level=ctx.obj["log_level"]` from `make_pipelex_for_agent_cli` calls.
  - `pipelex/cli/commands/doctor_cmd.py` — `setup_doctor_runtime` now `deep_update`s `log_config_overrides` instead of flat-merging, so `package_log_levels` merge preserves third-party levels.
  - `tests/unit/pipelex/cli/test_agent_cli_factory_init_overrides.py` — new regression test pinning the init-time OFF-suppression contract.
  - `telemetry_factory.py:77` is NOT modified — the log line is fine for the human pipelex CLI; only the agent CLI suppresses it.
- mthds-js repo: `/Users/lchoquel/repos/Pipelex/mthds-js/`. After pipelex 0.30.1 ships, bump its pipelex floor in `package.json` and cut 0.8.1.
