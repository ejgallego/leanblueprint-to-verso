# Ownership

This helper is designed to be pinned as a submodule while the host project owns
the actual blueprint code at its root.

## Helper Responsibilities

The helper provides:

- reusable workflow guidance
- bootstrap templates
- host `AGENTS.md` snippets
- reusable LT audit scripts that run against the host repo
- refresh logic for helper-owned CI files

## Host Responsibilities

The host repository owns:

- its mathematical source of truth
- the chosen package layout
- declaration names used in `(lean := "...")`
- all blueprint prose and chapter structure
- any project-specific chapter include/exclude choices for LT audit runs
- edits to `lakefile.lean` and the root blueprint modules after bootstrap

## Safe Automatic Refresh

Only these files are treated as helper-owned and safe to refresh
mechanically:

- `scripts/ci-pages.sh`
- `.github/workflows/blueprint.yml`

Everything else should be reviewed and updated deliberately by Codex or a human
after reading the helper diff.
