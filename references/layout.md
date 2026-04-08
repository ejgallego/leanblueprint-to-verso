# Layout

The canonical layout for a new Leanblueprint-to-Verso project is a dedicated
integration repository whose root is the Verso harness and whose upstream
formalization is vendored as a submodule.

## Canonical Layout

```text
host-repo/
├── tools/verso-harness/        # helper submodule
├── Formalization/              # upstream formalization submodule
├── MyProjectBlueprint.lean
├── MyProjectBlueprint/
│   ├── TeXPrelude.lean
│   └── Chapters/
├── BlueprintMain.lean
├── verso-harness.toml
├── lakefile.lean
├── lean-toolchain
├── scripts/ci-pages.sh
└── .github/workflows/blueprint.yml
```

This is the only startup layout for a new port.

## Why This Layout

- it cleanly separates the integration harness from the upstream formalization
- it makes `verso-harness.toml` the single source of truth for package layout
- it keeps shared helper logic in `tools/verso-harness`
- it matches the working `verso-flt` consumer shape

## Existing Repos

If an existing repository cannot adopt this layout directly, treat that as a
retrofit workflow, not as an alternative startup shape. Use:

- `references/retrofit.md`
- `references/maintenance.md`

## Helper Path

Prefer `tools/verso-harness` as the submodule path. It is short, local to the
repo, and easy to reference from `AGENTS.md`.
