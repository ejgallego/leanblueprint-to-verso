# Maintenance

Use this workflow after the initial port exists.

## Routine Tasks

Common maintenance work includes:

- adding or splitting chapters
- fixing `(lean := "...")` targets after declaration moves
- extending `TeXPrelude.lean`
- updating the source-backed porting status page or task board
- refreshing CI or Pages wiring
- updating the Lean toolchain or Verso dependencies

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

## After Updating The Helper Submodule

When the host repo bumps `tools/verso-harness`:

1. read the helper diff
2. run `python3 tools/verso-harness/scripts/update_ci.py --project-root .`
3. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
4. run the normal site smoke test

If the helper changed template expectations rather than CI, port those changes
manually into the project-owned files.

## Adding New Blueprint Content

- Extend the root blueprint module imports and `{include ...}` entries.
- Add shared macros only in `TeXPrelude.lean`.
- Prefer linking existing declarations to re-stating them.
- If the port is still source-backed, keep open TeX excerpts locally in labeled
  `tex` blocks instead of turning them into vague placeholders.
- Validate edited modules incrementally before building the whole site.

## Updating The Toolchain Or Dependencies

Treat toolchain bumps carefully:

- first update `lean-toolchain`
- then update dependency refs in `lakefile.lean`
- then refresh caches or rebuild as needed
- then repair any import or syntax fallout in the blueprint modules

Do not bundle unrelated blueprint prose edits into a dependency-upgrade change.

The current `verso-flt` pattern is to let `VersoBlueprint` drive the `verso`
dependency. Prefer that unless the host repo has a concrete reason not to.
