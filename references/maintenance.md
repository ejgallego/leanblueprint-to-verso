# Maintenance

Use this workflow after the initial port exists.

## Routine Tasks

Common maintenance work includes:

- adding or splitting chapters
- fixing `(lean := "...")` targets after declaration moves
- extending `TeXPrelude.lean`
- refreshing CI or Pages wiring
- updating the Lean toolchain or Verso dependencies
- re-auditing direct-port chapters under the current LT method

## Ownership Split

The helper intentionally separates files into two groups.

Project-owned after bootstrap:

- `lakefile.lean`
- `lean-toolchain`
- `BlueprintMain.lean`
- the root blueprint module
- `TeXPrelude.lean`
- chapter files

Helper-owned for automated refresh:

- `scripts/ci-pages.sh`
- `.github/workflows/blueprint.yml`

Use `scripts/update_ci.py` only for the helper-owned files.

The LT audit scripts live in the helper submodule and run against the host repo
in place. They are not copied into the host root.

## After Updating The Helper Submodule

When the host repo bumps `tools/verso-harness`:

1. read the helper diff
2. run `python3 tools/verso-harness/scripts/update_ci.py --project-root .`
3. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
4. rerun the LT audit stack on any direct-port chapters touched by the update
5. run the normal site smoke test

If the helper changed template expectations rather than CI, port those changes
manually into the project-owned files.

## Adding New Blueprint Content

- Extend the root blueprint module imports and `{include ...}` entries.
- Add shared macros only in `TeXPrelude.lean`.
- Prefer linking existing declarations to re-stating them.
- Validate edited modules incrementally before building the whole site.
- For direct-port chapters, use the LT audit stack after each coherent batch:
  - `check_lt_source_pairs.py`
  - `check_lt_similarity.py`
  - `lt_audit.py`

## Updating The Toolchain Or Dependencies

Treat toolchain bumps carefully:

- first update `lean-toolchain`
- then update dependency refs in `lakefile.lean`
- then refresh caches or rebuild as needed
- then repair any import or syntax fallout in the blueprint modules

Do not bundle unrelated blueprint prose edits into a dependency-upgrade change.

## Bringing An Older Harness Up To Date

If a project already has an older port that predates the source-paired LT
method:

1. refresh the helper-owned CI files
2. align the host `lakefile.lean`, `lean-toolchain`, and blueprint package
   layout with the current helper templates by manual review
3. record the real TeX source path and expose it in the local harness-native
   status surface when useful
4. add the host `AGENTS.md` guidance from `snippets/AGENTS.host.md`
5. treat prior LT labels as provisional only
6. re-audit touched direct-port chapters with adjacent `tex` witnesses,
   similarity checks, and a short deviation report
