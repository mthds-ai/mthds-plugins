# Cold-start prompt — re-enable Stage 3 in the Codex hook

Copy everything from `---` below into a fresh session opened in `/Users/lchoquel/repos/Pipelex/mthds-js/`. The prompt is self-contained.

---

You are picking up work on **mthds-js**. The goal is to re-enable Stage 3 (`pipelex-agent validate bundle`) in the Codex PostToolUse hook so that broken `.mthds` files saved through Codex get blocked — currently only Stages 1 (`plxt lint`) and 2 (`plxt fmt`) run. This brings Codex to parity with the Claude Code hook in `mthds-plugins` v0.11.3, which shipped a markdown-first validation flow on 2026-05-26.

## Repo state

- Repo: `/Users/lchoquel/repos/Pipelex/mthds-js/`
- Likely branch: `release/v0.8.1` is cut and version-bumped (commits `001dcad`, `759a1cd`) but not yet published to npm (`npm view mthds version` still returns `0.8.0`). Decide with the user whether to fold this work into 0.8.1 or cut 0.8.2.
- Target file: `src/agent/commands/codex-hook.ts` — Stage 3 is currently a comment-only stub at lines 235-237.
- Tests: `tests/unit/agent/codex-hook.test.ts` — uses vitest with the dependency-injection pattern (`CodexHookDeps` interface, exported helpers).

## Why this is unblocked now

The codex-hook.ts comment (lines 15-16 and 235-237) says Stage 3 is disabled because "the Codex sandbox blocks the eager S3 fetch." That premise is **stale**. Pipelex's `validate bundle` command path already runs `make_pipelex_for_agent_cli(..., needs_inference=False, needs_model_specs=True)` — see `pipelex/cli/agent_cli/commands/validate/bundle_cmd.py:129`. No gateway / inference setup runs for bundle validation; the offline-safety is baked in, not gated on a CLI flag.

**Verify first:** run `pipelex-agent validate bundle <some.mthds> -L <dir>/` with no network access and no API keys set. It should exit with either 0 (valid) or 1 (markdown error envelope on stderr), never with a `RemoteConfigUnavailableError` / `GatewayUnknownModelError`. If it does try to fetch, escalate back to pipelex — `needs_model_specs=True` may be doing something that needs trimming too. Don't proceed with Stage 3 until this is confirmed offline-clean in the sandbox.

## Reference implementation: the bash hook for Claude Code

The Claude side just shipped with this exact decision tree, in bash. **Read these files in `/Users/lchoquel/repos/Pipelex/mthds-plugins/` first** — they are the source of truth for the markdown parsing, decision routing, and additionalContext shape:

- `templates/hooks/validate-mthds.sh.j2` lines 87-156 — Stage 3 bash logic. Note the comment at the top and the strip / extract / case-statement structure.
- `tests/integration/test_hook_validate_mthds.py` — the Stage 3 test cases. Each Python test maps roughly 1-to-1 to a TS test you should write. Worth reading top to bottom.
- `wip/plan-validate-hook-rewrite.md` — full architecture and rationale doc. Section C.1 is the bash hook design; the Codex side is mentioned in "B-track" and at the bottom of section "Decisions taken."
- `CHANGELOG.md` v0.11.3 — the public framing of the change.

## Decisions already locked in

1. **Subprocess directly to `pipelex-agent`**, NOT recursively through `mthds-agent`. Same pattern as the existing `runPlxt` helper at line 159. Use `spawnSync` with `encoding: "utf8"` to capture stderr — do NOT `stdio: "inherit"` like the existing passthrough path does, because Stage 3 needs to *read* the markdown to decide.

2. **Port the bash markdown parsing to TS — same algorithm.** Empirically verified output shapes (from a real `pipelex-agent validate bundle` run on a broken `.mthds`):

   Input-domain error WITHOUT an `error_domain` field — happens when the raised error class doesn't set one and isn't in `AGENT_ERROR_DOMAINS` (e.g. `LibraryError` raised by a missing pipe reference):
   ```
   # Error: LibraryError

   Error validating pipe 'screen_all_candidates' dependency pipe 'build_scorecard' because of: Pipe 'build_scorecard' not found. Check for typos and make sure it is declared in MTHDS file in an imported package.

   ## Error source

   ```
   LibraryError @ /Users/.../pipelex/libraries/library.py:140 (in validate_pipe_library_with_libraries)
   PipeNotFoundError @ /Users/.../pipelex/libraries/pipe/pipe_library.py:115 (in get_required_pipe)
   ```
   ```

   Input-domain error WITH `error_domain` (`ValidateBundleError`, `LibraryLoadingError`, anything in `AGENT_ERROR_DOMAINS`):
   ```
   # Error: LibraryLoadingError

   Could not load MTHDS bundle from '...' because of: Validation error(s):

   Missing required fields: 'domain'

   ## Details

   - **error_domain:** input

   ## Error source

   ```...stack frames...```
   ```

   Algorithm (port from bash):
   - Strip everything from the line `## Error source` to EOF. **This is a stopgap** — pipelex 0.30.2 (just shipped to PyPI) already drops the section; once you bump the floor it becomes a no-op. Keep the strip as belt-and-suspenders so we don't break if a user lags on pipelex.
   - If the trimmed result is empty or whitespace-only → BLOCK with a generic `"Validation failed for <file> (pipelex-agent exited <code> with no stderr output)"`.
   - Otherwise, extract `error_domain`: regex-match `^- \*\*error_domain:\*\* *(\S+)` on the trimmed text (line-anchored, multiline). Take the first match.
   - If `error_domain` is `config` or `runtime` → emit additionalContext, no block.
   - Otherwise (input, missing, unknown) → BLOCK with the trimmed markdown verbatim as the reason. **Default to block for safety.**

3. **Codex `additionalContext` schema is the same shape as Claude's:**
   ```json
   {
     "hookSpecificOutput": {
       "hookEventName": "PostToolUse",
       "additionalContext": "<markdown — string, ≤ ~10k chars>"
     }
   }
   ```
   Truncate to 9500 chars with a `[truncated, <N> chars omitted]` marker — same safety margin used in the Claude bash hook. The Codex schema is at `openai/codex` repo path `codex-rs/hooks/schema/generated/post-tool-use.command.output.schema.json` if you need to double-check.

4. **Add a `buildAdditionalContextPayload(context: string): string` helper** next to the existing `buildBlockPayload(reason: string): string`. Don't overload one function. Both should be pure / exported / unit-tested.

5. **Aggregate behavior across multiple files** (the existing loop at line 213 already iterates touched `.mthds` files):
   - If any file produces a BLOCK reason → emit single `decision: block` with all block reasons joined (matches existing Stages 1/2 behavior).
   - If only additionalContext entries → emit one additionalContext, concatenating per-file warnings with file-path headers.
   - If a file blocks AND another file warns → both can coexist in one response per Claude's docs ("Block + additionalContext can both be set in the same response; both are honored"). Verify Codex honors the same. If unsure, prefer single block-only response (warnings can wait — block already forces the agent to retry).
   - Per-file pass / no-Stage-3-output → silent in the aggregate, same as today.

6. **Dependency injection.** Extend `CodexHookDeps` with a new field — e.g. `runPipelexValidate: (file: string, libraryDir: string) => { exitCode: number; stderr: string }` — and inject the real implementation from `agentCodexHook()`. This keeps the new logic unit-testable in the same style as the existing helpers, no real subprocess in tests.

## Don't change

- Stages 1 (`plxt lint`) and 2 (`plxt fmt`) — leave them alone. The plxt binaries are independent of pipelex output shape.
- The `parseMthdsFiles`, `commandOnPath`, `buildPathCandidates` helpers — already covered by tests and unchanged in scope.
- The PostToolUse stdout protocol described in the file header docstring (lines 11-13) — silent pass / block JSON / additionalContext JSON. Update the docstring to add the additionalContext line.

## Tests to add (mirror the Python integration tests)

In `tests/unit/agent/codex-hook.test.ts`, add a `describe("runCodexHook — Stage 3", ...)` block covering, at minimum:

- Input-domain markdown (`error_domain: input` in `## Details`) → BLOCK, reason contains the trimmed markdown including the `# Error:` header and the file path.
- Markdown with no `error_domain` line (e.g. `LibraryError`) → BLOCK (safety default).
- `error_domain: config` → exit 0, stdout is the additionalContext envelope, NOT a block envelope.
- `error_domain: runtime` → same as config.
- `## Error source` section present in stderr → stripped from BLOCK reason. Stack-frame lines (e.g. `library.py:140`) must NOT appear in the output.
- `## Error source` stripped from additionalContext too (config-domain case).
- Empty stderr with non-zero pipelex exit → BLOCK with the generic "no stderr output" reason.
- Markdown body > 9500 chars in config domain → additionalContext truncated with `[truncated,` marker, total length under 10000.
- pipelex exit 0 → no output added by Stage 3 (silent pass when Stages 1/2 also passed).
- Aggregate: file A blocks + file B passes → single block, only A's reason in it.
- Aggregate: file A warns (config) + file B blocks (input) → emit block (file B's reason); decide whether to also include file A's warning as additionalContext or to defer it. Match what you implemented in #5 above.

## What this work does NOT touch in the plugin repo

The plugin's Codex side is config-only:
- `mthds-codex/hooks/codex-hooks.json` just invokes `mthds-agent codex hook` — no logic change needed.
- `templates/hooks/codex-hooks.json.j2` — same.

Plugin-side changes happen AFTER this lands in mthds-js and publishes:
- Bump `targets/defaults.toml [vars].min_mthds_version` to the new mthds-js version.
- Update `mthds-plugins/CLAUDE.md` lines 110-115 — drop the "Stage 3 stays disabled until offline-mode validation lands" sentence; replace with a one-liner that Codex now has Stage 3 parity.
- Add a CHANGELOG line in `mthds-plugins` (either fold into v0.11.3 if not yet shipped, or roll into v0.11.4).

## Suggested first commands on resume

```bash
cd /Users/lchoquel/repos/Pipelex/mthds-js

# 1. Branch + tool state
git status -sb | head -5
node --version
npm view mthds version

# 2. Confirm pipelex-agent validate bundle is offline-safe
cd /tmp && rm -rf codex_verify && mkdir codex_verify && cd codex_verify
cp /Users/lchoquel/repos/Pipelex/mthds-plugins/wip/bad_bundle.mthds ./
# Unset any API key envs and run with offline-ish DNS if possible:
env -i HOME="$HOME" PATH="$PATH" pipelex-agent validate bundle bad_bundle.mthds -L ./ >stdout.txt 2>stderr.txt
echo "exit=$?"
head -25 stderr.txt
# Expected: exit 1, stderr is a clean `# Error:` markdown envelope.
# NOT expected: any RemoteConfigUnavailableError, GatewayUnknownModelError, or socket / DNS errors.

# 3. Read the source of truth
cat /Users/lchoquel/repos/Pipelex/mthds-plugins/templates/hooks/validate-mthds.sh.j2 | sed -n '87,156p'
cat /Users/lchoquel/repos/Pipelex/mthds-plugins/tests/integration/test_hook_validate_mthds.py | sed -n '220,400p'

# 4. Open the file to edit and its tests
cd /Users/lchoquel/repos/Pipelex/mthds-js
wc -l src/agent/commands/codex-hook.ts tests/unit/agent/codex-hook.test.ts
```

If step 2 fails (network attempt detected), STOP and report back — the premise of this work is wrong and pipelex needs another fix. If step 2 succeeds, proceed to design the Stage 3 helper + tests.

## References

- Claude Code PostToolUse hook output protocol (block + additionalContext): https://code.claude.com/docs/en/hooks (PostToolUse output, lines 484-590, also captured verbatim in `mthds-plugins/wip/plan-validate-hook-rewrite.md` "Decisions taken").
- Pipelex 0.30.2 changelog (just shipped): `/Users/lchoquel/repos/Pipelex/pipelex/CHANGELOG.md` — drops `## Error source` from markdown.
- Pipelex error envelope source: `/Users/lchoquel/repos/Pipelex/pipelex/pipelex/cli/agent_cli/commands/agent_output.py` lines 217-307 (payload assembly, markdown render, `AGENT_ERROR_DOMAINS` lookup at line 156).
- Companion bash hook (Claude side, just shipped in `mthds-plugins` v0.11.3): `/Users/lchoquel/repos/Pipelex/mthds-plugins/mthds/hooks/validate-mthds.sh`.
