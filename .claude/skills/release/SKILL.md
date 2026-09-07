---
name: release
description: >
  Cut a release of mthds-plugins, the MTHDS plugin marketplace served to Claude
  Code and Codex from GitHub: the release/vX.Y.Z worktree, the matched-version
  bump across every build target and the Claude marketplace, the regenerated
  plugin manifests, the changelog entry, the quality gates, one commit, and a
  pull request to main. Use when the user says "release", "cut a release", "bump
  version", "prepare a release", "make a release", "ship it", "create release
  branch", "promote dev to main", "release the plugin", or any variation of
  shipping a new version of the MTHDS plugins. Changelog content passed inline
  ("/release Added a sandbox target") becomes the entry. The merge is landed by
  /ledger-land, never by this skill.
---

# Releasing mthds-plugins

The procedure is the workspace release play, [`docs/releasing.md`](../../../../docs/releasing.md) at the workspace root — `../docs/releasing.md` from this repo's own root, which resolves the same from the main checkout and from any worktree. Read it first, then run it with what follows. The repo key is `mthds-plugins`, the base is `dev`, and the pull request targets `main`: `guard-branches.yml` refuses any head branch but `release/vX.Y.Z` into `main`, so there is no other way in. The release worktree is `_mthds-plugins--release`, made with `wt add mthds-plugins release --branch release/vX.Y.Z`. The repo declares neither `.worktree.toml` nor `.worktreeinclude`, so `wt` resolves the base from `origin/dev` and provisions with the Makefile's `install` target, which is what creates the `.venv` every gate below runs out of.

## What ships

**Nothing is uploaded anywhere, and the merge itself is the publish.** No workflow in `.github/workflows/` fires on a push to `main` — `checks.yml` and `tests.yml` fire on `pull_request`, `guard-branches.yml` on `pull_request_target` — because both marketplaces are installed straight from the GitHub repository `mthds-ai/mthds-plugins` in the bare `owner/repo` form the README gives, which carries no `@ref` and so leaves them on the repository's default branch, `main`. What lands there is what the next `/plugin marketplace add` or `codex plugin marketplace add` hands a user.

- **The Claude Code marketplace** reads `.claude-plugin/marketplace.json` and serves the built output directories it lists: `mthds/` (the prod plugin), `mthds-dev/` and `mthds-sandbox/`. `mthds-dev/` renders container install paths and is consumed by the `internal-tools` Docker integration tests rather than installed on a host.
- **The Codex marketplace** reads `.agents/plugins/marketplace.json`, the generated discovery copy of the canonical `packaging/codex-marketplace.json`, and serves `mthds-codex/`.

The landing therefore has no publish run to inspect and no registry to query, and **this repo carries no tags** — none exist locally or on origin, and no workflow creates one, so `git describe` and a `git tag --list vX.Y.Z` check have nothing to find. What it verifies instead is that the merge happened and that `main` now carries the new version:

```bash
gh pr view <number> --json state,mergedAt,mergeCommit                              # merged
git -C <main> fetch --prune origin
git -C <main> show origin/main:targets/prod.toml | grep '^version'                 # X.Y.Z
git -C <main> show origin/main:.claude-plugin/marketplace.json | grep '"version"'  # X.Y.Z
```

## Version files and the lock

- **`[plugin].version` in every `targets/*.toml`**, all set to the same string — the matched-version lockstep. Enumerate the files with `ls targets/*.toml` rather than trusting any list written down here, so a target added since is never silently missed. `targets/defaults.toml` is not a build target: it holds shared `[vars]` and no `[plugin]` table, and `scripts/check.py` skips it by name for that reason.
- **`.claude-plugin/marketplace.json`** — `metadata.version`, the Claude marketplace's own number. Set it to the same string as the targets.
- **No lock step.** `uv.lock` locks this repo's internal tooling package, `mthds-plugins-tools`, whose `version` in `pyproject.toml` is deliberately not the plugin version — the comment above it says so, and `guard-branches.yml` repeats the point. A release touches neither file.
- **Also stamped: each target's generated `plugin.json`**, written by `make build` (`scripts/gen_skill_docs.py --target all`) from the target's TOML and the `plugin-base.json` of its platform — `.claude-plugin/plugin-base.json` for the Claude targets and `.codex-plugin/plugin-base.json` for the Codex one, two files whose shared fields differ — and never hand-edited: `mthds/.claude-plugin/plugin.json`, `mthds-dev/.claude-plugin/plugin.json`, `mthds-sandbox/.claude-plugin/plugin.json`, and the Codex-shaped `mthds-codex/.codex-plugin/plugin.json`. The same build also syncs `.agents/plugins/marketplace.json` from `packaging/codex-marketplace.json`.

## Gates

Run in the worktree, in this order:

1. **`make agent-check`** — `fix-unused-imports`, `format` and `lint`, then `make check`. **It rewrites files** (`ruff check --fix`, `ruff format`), so whatever it touches joins the release commit. `make check` is the substance, and it runs scope by scope: `check-shared` verifies the shared references, the matched-version lockstep, template freshness (`gen_skill_docs.py --target all --check`, which is what catches a generated file the build has not been run over, an orphaned `SKILL.md`, a leaked `.j2`, and a `.agents/plugins/marketplace.json` that no longer matches `packaging/codex-marketplace.json` byte for byte), ruff format and lint, pyright and mypy; `check-claude` verifies the Claude marketplace packaging; `check-codex` verifies the canonical `packaging/codex-marketplace.json` against the target configs and that no Claude-specific artifact leaked into `mthds-codex/`. Red blocks the release: fix the cause, never loosen the target.
2. **`make agent-test`** — the pytest suite under `tests/`, quiet unless it fails. The pull request runs the same tests, so a red one here is a red pull request there.
3. **After the bump, `make build` and then `make check` again.** This is the gate the play marks *after the bump*, and it is not optional here: the version is written in `targets/*.toml`, but each target's `plugin.json` is generated from it, and `check.py` compares the two. Skip the rebuild and `make check` fails with `[<target>] plugin.json has A.B.C, targets/<target>.toml has X.Y.Z`. Never hand-edit a `plugin.json` to make that quiet — the next `make build` overwrites it.

## The release commit

Every `targets/<name>.toml` you bumped, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, and each target's regenerated `plugin.json` — staged by name. That is the whole of a version-only release, and it is exactly what the `Release v0.15.1` commit carries. When the branch also moved `min_mthds_version` in `targets/defaults.toml` or a template under `templates/`, `make build` rewrites the derived `SKILL.md` and shared Markdown files across every output directory as well, and those belong in the commit too — so stage what the build actually changed rather than the list above.

## CI on the release pull request

- **`guard-branches.yml`** (`gate-main`) — on a pull request whose base is `main`, the head branch must match `^release\/v[0-9]+\.[0-9]+\.[0-9]+$`, so the release branch name is the only way in. It fires on `pull_request_target` with `types: [opened, edited, reopened]`, and therefore does not re-run when the branch is pushed to again.
- **`checks.yml`** (`Validate skills`) — on every pull request, `make check` then `make test`, on Python 3.13.
- **`tests.yml`** (`Unit tests`) — on every pull request, `make gha-tests` (`pytest --exitfirst --quiet`), on Python 3.12.

**Nothing in CI checks the release as a release.** There is no `version-check.yml` and no `changelog-check.yml`: no job compares the version in `targets/*.toml` against the version in the branch name, and no job reads `CHANGELOG.md` at all. `make check` catches an *internally inconsistent* bump — a target left behind, a stale `plugin.json`, a marketplace number lagging the targets — but a consistent bump to the wrong number, or a release with no changelog entry, merges green. Getting the number and the entry right is this skill's job, not CI's.

## Particulars

- **Matched-version lockstep.** Every build target ends the release on the same version string, whatever it carried before; `check_matched_target_versions` in `scripts/check.py` refuses any drift with `Target versions must be in lockstep`. Compute the bump from `targets/prod.toml`'s current version and write it to all of them.
- **The marketplace version is a floor, not an equality.** `check.py` fails only when `.claude-plugin/marketplace.json`'s `metadata.version` is *lower* than the highest Claude target version — `metadata.version 'A.B.C' lags behind Claude target version 'X.Y.Z'` — so a marketplace number that runs ahead passes the check. Write the same string anyway.
- **`pyproject.toml` is not a release file.** Its `version` belongs to `mthds-plugins-tools`, the unpublished internal tooling package; it moves when the tooling changes, in an ordinary pull request to `dev`, and never as part of a plugin release.
- **No pre-release form.** `gate-main`'s regex ends at the patch number, so `release/v0.16.0-rc.1` is refused into `main` outright rather than skipped the way a looser gate would skip it. Ship a plain `X.Y.Z`.
- **The changelog headings carry the `v`** — `## [vX.Y.Z] - YYYY-MM-DD` — and no `[Unreleased]` heading is left behind; the next change re-creates one. The `v` prefix appears in the branch name, the changelog heading and the pull request title, and never in a version file.
- **The back-merge is usually a fast-forward, and is not guaranteed to be one.** The release branch is cut from `dev`, so when `dev` has not moved while the release was in flight it fast-forwards onto `main` and needs no merge commit. When `dev` has moved, a real merge is required: commit `54bc94f`, `Merge branch 'release/v0.13.0' into dev`, is a two-parent merge whose first parent is not an ancestor of the release commit, so no fast-forward was possible there. `/ledger-land` makes whichever the state at the time calls for.
