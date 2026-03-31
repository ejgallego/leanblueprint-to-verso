# Retrofit

Use this workflow when a host project already has a Verso or `leanblueprint`
port, but that port needs to be brought up to the current helper-owned harness
and LT method.

## 1. Install The Helper

Add or update the helper at the conventional path:

```bash
git submodule add <helper-repo-url> tools/verso-harness
```

If the helper already exists, bump it deliberately and read the helper diff
before touching the host repo.

## 2. Refresh The Helper-Owned Files

Run:

```bash
python3 tools/verso-harness/scripts/update_ci.py --project-root .
python3 tools/verso-harness/scripts/check_harness.py --project-root .
```

These commands only refresh the helper-owned CI files and check the expected
harness shape. They do not overwrite project-owned blueprint modules.

## 3. Align The Host-Owned Harness Files

Review the helper templates and port the relevant changes manually into:

- `lakefile.lean`
- `lean-toolchain`
- `BlueprintMain.lean`
- the root blueprint module
- `TeXPrelude.lean`
- chapter imports and include lists

For older projects, the main alignment points are usually:

- the current `VersoBlueprint` dependency source and ref
- the current Lean toolchain baseline
- one shared `TeXPrelude.lean`
- one coherent root blueprint package at the host root

## 4. Update Host Instructions

Pull the host guidance from `snippets/AGENTS.host.md` into the host
repository's `AGENTS.md` so future work follows the helper-owned workflow.

## 5. Re-Audit Direct-Port Chapters

Treat earlier LT labels as provisional only. For each direct-port chapter that
is touched during the retrofit:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
```

If the host repo has harness-native chapters, exclude them when using default
chapter discovery:

```bash
python3 tools/verso-harness/scripts/status_lt.py --project-root . --exclude 'MyBlueprint/Chapters/Historical*.lean'
```

## 6. Keep Ownership Clear

- Helper-owned: `scripts/ci-pages.sh`, `.github/workflows/blueprint.yml`
- Host-owned: chapter prose, root blueprint modules, `lakefile.lean`,
  `lean-toolchain`, declaration links, and chapter structure

Do not expect `update_ci.py` to modernize project-owned files automatically.
That part of the retrofit is review-driven on purpose.

## 7. Finish With A Coherent Validation Pass

After a coherent retrofit batch:

1. rerun the LT audit stack on touched direct-port chapters
2. run `bash ./scripts/ci-pages.sh`
3. record any deliberate non-literal deviations in the work summary
