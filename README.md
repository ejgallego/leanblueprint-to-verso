# Leanblueprint To Verso Harness

Use this repository as a local submodule inside a Lean project that is porting,
maintaining, or retrofitting a `leanblueprint` or TeX blueprint to a `verso-blueprint` harness.

The helper assumes the current LT-first workflow: preserve theorem order,
section order, paragraph boundaries, and dependency edges from the legacy
blueprint unless there is a clear harness reason not to.

It tracks the current `verso-flt` harness pattern where Lean 4.28 and the
`VersoBlueprint` compatibility branch drive the stack, including support for
labeled local `tex` blocks when raw TeX needs to remain visible in the port.

Every helper-managed repo must carry a root `verso-harness.toml`. The helper
reads package layout, chapter scope, and LT defaults from that file and does
not guess repo structure.

Canonical repository name: `leanblueprint-to-verso`.

## Add The Helper

```bash
git submodule add git@github.com:ejgallego/leanblueprint-to-verso.git tools/verso-harness
```

Recommended host-side `AGENTS.md` wiring lives in
[snippets/AGENTS.host.md](snippets/AGENTS.host.md).

A short adoption path for other repos lives in
[references/new-consumer-checklist.md](references/new-consumer-checklist.md).

The canonical empty-directory startup path lives in
[references/start-new-port.md](references/start-new-port.md).

## Main Usage Modes

### 1. Start A New Port From An Empty Directory

This is the canonical startup flow. Do not ask the agent to choose a layout.
Use the dedicated integration-repo layout from
[references/start-new-port.md](references/start-new-port.md).

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
python3 tools/verso-harness/scripts/check_source_label_grounding.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
```

`update_ci.py` only refreshes the helper-owned CI files. It does not overwrite
project-owned blueprint modules or chapter prose.

### 3. Underlying Bootstrap Command

The canonical startup script delegates to `scripts/bootstrap.py` after the
formalization submodule is in place. `bootstrap.py` remains available as the
low-level scaffolding command, but new ports should prefer
`scripts/start_new_port.py`.

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
