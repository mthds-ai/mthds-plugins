---
name: release
description: >
  Automates the release workflow for this plugin: runs `make check`, bumps the
  version in plugin.json and marketplace.json, finalizes CHANGELOG.md, creates a
  release/vX.Y.Z branch, commits, pushes, and opens a PR to main. Use this skill
  when the user says "release", "cut a release", "bump version", "prepare a
  release", "make a release", "create release branch", or any variation of
  shipping a new version. The user can optionally provide changelog content
  inline when invoking the skill (e.g. "/release Added version sync check"),
  which will be used as the changelog entry for this version.
---

# Release Workflow

Guides the user through preparing a new plugin release. Every step requires
explicit user confirmation before proceeding.

This plugin keeps its version in two files:

- `.claude-plugin/plugin.json` -- the `"version"` field
- `.claude-plugin/marketplace.json` -- the `"metadata"."version"` field

Both must always be in sync.

## 1. Pre-flight checks

- Read the current version from `plugin.json`.
- Read `CHANGELOG.md` to understand the current state (if it exists).
- Run `git status` and `git log origin/main..HEAD` to assess the working tree:
  - If there are **uncommitted changes** (staged or unstaged), warn the user and
    ask whether to commit them as part of the release, stash them, or abort.
  - If there are **unpushed commits** on the current branch, list them so the
    user is aware -- these will be included in the release branch.

## 2. Determine the bump type

Ask the user which kind of version bump they want -- **patch**, **minor**, or
**major** -- unless they already specified it. Show the current version and what
the new version would be for each option so the choice is concrete.

If the current branch already looks like `release/vA.B.C` and the version in
`plugin.json` was already bumped, offer a **"Keep current (A.B.C)"** option.

Store the chosen version as `TARGET_VERSION` (no `v` prefix, e.g. `0.6.2`).

## 3. Run quality checks

Run `make check`. This is the gate -- if it fails, stop and report the errors so
they can be fixed before retrying. Do not proceed past this step on failure.

## 4. Ensure we're on the right branch

The release branch must be named `release/v{TARGET_VERSION}` where the version
is the **new** version. All file modifications (changelog, version bump) must
happen on this branch.

- If already on `release/v{TARGET_VERSION}` matching the new version, stay on it.
- If on `main` or any other branch, create and switch to
  `release/v{TARGET_VERSION}` from the current HEAD.
- If on a `release/` branch for a **different** version, warn the user and ask
  how to proceed.

## 5. Bump the version

Edit both files to the new version string:

1. **`.claude-plugin/plugin.json`** -- change the `"version"` value.
2. **`.claude-plugin/marketplace.json`** -- change the `"metadata"."version"`
   value.

Only change the version fields -- don't touch anything else in either file.

- If both versions already match `TARGET_VERSION`: inform the user and skip.
- Otherwise: use the Edit tool to make the changes, then show the diff.

Verify both files now contain the same new version.

## 6. Finalize the changelog

Add a new version entry at the top of the changelog for the release. If
`CHANGELOG.md` does not exist yet, create it with a `# Changelog` heading.

1. If there is an `## [Unreleased]` section, **remove it** (including any blank
   lines that follow it) and replace it with the new version heading. Any
   content that was under `[Unreleased]` becomes the content of the new version.
2. If there is no `[Unreleased]` section, insert the new version heading
   directly after the `# Changelog` title.
3. **Never add an `[Unreleased]` heading.** The changelog should only contain
   concrete version entries.
4. If the user provided changelog content when invoking the skill (e.g.
   `/release Added version sync check`), **merge** that content with any
   existing `[Unreleased]` content (do not discard either source). Format the
   combined content properly under the appropriate headings (e.g. `### Added`,
   `### Changed`, `### Fixed`), inferring headings from the content when
   possible.
5. If the release has no changelog content yet (neither from an `[Unreleased]`
   section nor from inline user input), run `git log main..HEAD --oneline` (or
   `git log --oneline -20` if on `main`) to review recent commits. Draft a
   changelog entry from those commits and propose it to the user for approval.
6. The result should look like:

```markdown
# Changelog

## [vX.Y.Z] - YYYY-MM-DD

### Added

- Item one

### Changed

- Item two

### Fixed

- Item three

## [vPREVIOUS] - PREVIOUS-DATE

...
```

Use the appropriate subsections (Added, Changed, Fixed, Removed, Breaking
Changes) based on the content. Only include subsections that have entries. The
user may accept, edit, or rewrite the proposed entry.

## 7. Commit, push & PR

Stage all release-related changes: `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and `CHANGELOG.md`, plus any other files the
user chose to include in step 1 (e.g. previously uncommitted work that belongs
in this release). Never use `git add .` or `git add -A`.

Commit with the message:

```
Release v{TARGET_VERSION}
```

Push the branch to origin with `-u` to set up tracking.

Create a pull request targeting `main` with:

- **Title:** `Release v{TARGET_VERSION}`
- **Body:**

```markdown
## Release v{TARGET_VERSION}

Bumps version from `{OLD_VERSION}` to `{TARGET_VERSION}`.

### Changelog

<paste the changelog entries for this version here>
```

Report the PR URL back to the user.

## Rules

- The version follows semver: `MAJOR.MINOR.PATCH`.
- Both `plugin.json` and `marketplace.json` must always have the same version.
- Always confirm the bump type with the user before making changes.
- If `make check` fails, the release is blocked -- help the user fix the issues
  rather than skipping the checks.
- Never use `git add .` or `git add -A` -- only stage the specific release files.
- The `v` prefix appears in branch names, changelog headers, and PR titles, but
  **not** in `plugin.json` or `marketplace.json`.
- Always use today's date for new changelog entries (format: `YYYY-MM-DD`).
- If any step fails or the user wants to abort, stop immediately -- do not
  continue the workflow.
- PR always targets `main`.
