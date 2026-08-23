# Maintenance

Use this workflow after the initial port exists.

The first command in a maintenance pass should be:

```bash
python3 tools/verso-harness/scripts/status_harness.py --project-root .
```

Use that status view to see whether the helper checkout, the vendored
formalization, or the resolved `VersoBlueprint` package have moved before you
start updating files.
For repo-level chapter completion status, use:

```bash
python3 tools/verso-harness/scripts/status_completion.py --project-root .
python3 tools/verso-harness/scripts/status_completion.py --project-root . --build
```

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

The generated `blueprint.yml` is intentionally thin. It calls the reusable
Pages workflow in `verso-blueprint` and is pinned to the same
`VersoBlueprint` ref declared in the consumer `lakefile.lean`.
The generated `scripts/ci-pages.sh` invokes
`lake exe vbp build --output _out/site`; it must not prebuild the Blueprint
entry point with `lake build` or invoke the legacy `lake lean` generator path.

The generated README is a starting point for the consumer repo and remains
project-owned after bootstrap. The helper should not rewrite it automatically
on later updates.

The LT audit scripts live in the helper submodule and run against the host repo
in place. They are not copied into the host root.

## After Updating The Helper Submodule

When the host repo bumps `tools/verso-harness`:

1. run `python3 tools/verso-harness/scripts/status_harness.py --project-root .`
2. read the helper diff
3. run `python3 tools/verso-harness/scripts/update_ci.py --project-root .`
4. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
5. rerun the LT audit stack on any direct-port chapters touched by the update
6. run the normal site smoke test

The shared harness may also move independently of local chapter work because it is maintained
across many ports. Agents should treat unexpected `tools/verso-harness` changes as normal
shared-infrastructure updates: inspect the helper diff first, then rerun `check_harness.py`,
then decide whether only helper-owned files changed or whether project-owned files need review.

If the helper changed template expectations rather than CI, port those changes
manually into the project-owned files.
In particular, keep `lakefile.lean` aligned with the warning policy declared in
`verso-harness.toml`; `check_harness.py` verifies the generated
version-appropriate math-lint and strict-resolve lean options together with the
version-appropriate warn-line-length setting.

## Adding New Blueprint Content

- Extend the root blueprint module imports and `{include ...}` entries.
- Add shared macros only in `TeXPrelude.lean`.
- Prefer linking existing declarations to re-stating them.
- Preserve source-backed reference metadata: TeX `\uses{...}` becomes
  `(uses := ...)` on the relevant node by default, with inline `{uses "..."}[]`
  only when the reference is naturally part of the prose. Link-only TeX
  `\ref{...}` references to blueprint nodes become inline `{bpref "..."}[]`.
- Validate edited modules incrementally before building the whole site.
- For direct-port chapters, use the LT audit stack after each coherent batch:
  - `check_lt_source_pairs.py`
  - `check_lt_source_freshness.py --require-current`
  - `check_lt_similarity.py`
  - `check_blueprint_node_kinds.py`
  - `check_source_label_grounding.py`
  - `check_verso_math_delimiters.py`
  - `lt_audit.py`
  - `lt_audit.py --native-warnings` when the repo wants warnings to fail the focused build

## Updating The Toolchain Or Dependencies

The upstream formalization determines the Lean toolchain. In a consumer repo:

- first update the upstream formalization to the desired revision
- then copy or confirm the same value in the root `lean-toolchain`, including
  prerelease suffixes such as `v4.30.0-rc2`
- then update the `VersoBlueprint` ref in `lakefile.lean` to the base release
  ref for that Lean series, such as `v4.30.0` for `v4.30.0-rc2`
- keep the resolved `.lake/packages/VersoBlueprint` checkout clean; prerelease
  toolchain selection is a property of the root/formalization build, not a
  mutation of the dependency package checkout
- then refresh caches as needed through the harness scripts
- then repair any import or syntax fallout in the blueprint modules
- treat every `(lean := "...")` target as part of the compatibility surface:
  `check_harness.py` validates configuration only, so run the normal
  `scripts/ci-pages.sh` site build or equivalent remote Pages CI to catch
  declarations renamed, replaced, or removed by the formalization update

Do not bundle unrelated blueprint prose edits into a dependency-upgrade change,
do not bump the consumer toolchain independently of upstream, and do not run raw
Lake build/update commands when this local toolchain selection has not been
checked.

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
