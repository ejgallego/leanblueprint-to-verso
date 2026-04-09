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

- `README.md`
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

The generated README is a starting point for the consumer repo and remains
project-owned after bootstrap. The helper should not rewrite it automatically
on later updates.

The LT audit scripts live in the helper submodule and run against the host repo
in place. They are not copied into the host root.

## After Updating The Helper Submodule

When the host repo bumps `tools/verso-harness`:

1. read the helper diff
2. run `python3 tools/verso-harness/scripts/update_ci.py --project-root .`
3. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
4. rerun the LT audit stack on any direct-port chapters touched by the update
5. run the normal site smoke test

The shared harness may also move independently of local chapter work because it is maintained
across many ports. Agents should treat unexpected `tools/verso-harness` changes as normal
shared-infrastructure updates: inspect the helper diff first, then rerun `check_harness.py`,
then decide whether only helper-owned files changed or whether project-owned files need review.

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
  - `check_blueprint_node_kinds.py`
  - `lt_audit.py`

## Updating The Toolchain Or Dependencies

The upstream formalization determines the Lean toolchain. In a consumer repo:

- first update the upstream formalization to the desired revision
- then copy or confirm the same value in the root `lean-toolchain`
- then update the `VersoBlueprint` ref in `lakefile.lean` to the matching branch `lean-<release>`
- then refresh caches or rebuild as needed
- then repair any import or syntax fallout in the blueprint modules

Do not bundle unrelated blueprint prose edits into a dependency-upgrade change,
and do not bump the consumer toolchain independently of upstream.

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
