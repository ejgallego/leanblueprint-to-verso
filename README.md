# TeX Blueprint To Verso Harness

Use this repository as a local submodule inside a Lean project that is porting,
maintaining, or retrofitting a TeX blueprint to a `verso-blueprint` harness.

The helper assumes the current LT-first workflow: preserve theorem order,
section order, paragraph boundaries, and dependency edges from the legacy
blueprint unless there is a clear harness reason not to.

It tracks the current `verso-flt` harness pattern where Lean 4.28 and the
`VersoBlueprint` compatibility branch drive the stack, including support for
labeled local `tex` blocks when raw TeX needs to remain visible in the port.

Every helper-managed repo must carry a root `verso-harness.toml`. The helper
reads package layout, chapter scope, and LT defaults from that file and does
not guess repo structure.

## Add The Helper

```bash
git submodule add <helper-repo-url> tools/verso-harness
```

Recommended host-side `AGENTS.md` wiring lives in
[snippets/AGENTS.host.md](snippets/AGENTS.host.md).

## Main Usage Modes

### 1. Bootstrap An Outer Harness

Use this when the host repo wants a dedicated root blueprint harness that
depends on an upstream formalization checkout or submodule.

```bash
python3 tools/verso-harness/scripts/bootstrap.py \
  --project-root . \
  --package-name MyProjectBlueprint \
  --title "My Project Blueprint" \
  --formalization-name MyProject \
  --formalization-path "./MyProject"
```

If the host repo stores TeX chapters somewhere other than the common
`./blueprint/src/chapter/*.tex` layout, also pass `--tex-source-glob`.

This seeds:

- `verso-harness.toml`
- `lakefile.lean`
- `lean-toolchain`
- `BlueprintMain.lean`
- a starter blueprint package with `TeXPrelude`, `Introduction`, and
  `PortingStatus` chapters
- `scripts/ci-pages.sh`
- `.github/workflows/blueprint.yml`

The seeded files are intentionally minimal. They are a starting point for
Codex, not a finished port.

### 2. Retrofit An Older Harness

Use this when a project already has an older Verso or `leanblueprint`-derived
port that needs to conform to the current source-paired LT method.

Read:

- [references/retrofit.md](references/retrofit.md)
- [references/lt-method.md](references/lt-method.md)
- [references/maintenance.md](references/maintenance.md)

The normal first steps are:

```bash
python3 tools/verso-harness/scripts/update_ci.py --project-root .
python3 tools/verso-harness/scripts/check_harness.py --project-root .
```

Then run the LT audit stack on the chapters being reworked:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
```

`update_ci.py` only refreshes the helper-owned CI files. It does not overwrite
project-owned blueprint modules or chapter prose.

### 3. Manual In-Place Integration

If the host repo already has a root `lakefile.lean` that cannot be replaced,
use the guidance in:

- [references/layout.md](references/layout.md)
- [references/porting.md](references/porting.md)
- [references/maintenance.md](references/maintenance.md)
- [references/retrofit.md](references/retrofit.md)

That path is intentionally doc-guided rather than fully scripted, because
patching an arbitrary existing `lakefile.lean` is project-specific.

## LT Audit Stack

The helper now carries the reusable LT tooling used in `verso-flt`:

- `scripts/check_lt_source_pairs.py`
- `scripts/check_lt_similarity.py`
- `scripts/check_source_label_grounding.py`
- `scripts/status_lt.py`
- `scripts/lt_audit.py`

These run from the helper submodule against the host repo via `--project-root`.
When no explicit chapter list is passed, they use `lt.default_chapters` from
`verso-harness.toml`.

For the detailed chapter-by-chapter workflow and validation rules, see
`references/lt-method.md`, `references/porting.md`, and `AGENTS.md`.
