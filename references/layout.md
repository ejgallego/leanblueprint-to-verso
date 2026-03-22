# Layout

The helper supports two host-repository shapes.

## Preferred: Outer Harness At Host Root

This is the supported bootstrap path. The host repo root acts as the Verso
blueprint harness and depends on the formalization through a local Lake
dependency.

Recommended layout:

```text
host-repo/
├── tools/verso-harness/        # this helper submodule
├── Formalization/             # upstream checkout or submodule
├── MyProjectBlueprint.lean
├── MyProjectBlueprint/
│   ├── TeXPrelude.lean
│   └── Chapters/
├── BlueprintMain.lean
├── lakefile.lean
├── lean-toolchain
├── scripts/ci-pages.sh
└── .github/workflows/blueprint.yml
```

This matches the separation that worked well in `verso-flt`: blueprint and CI
code at the outer root, mathematical source-of-truth code in a distinct
dependency checkout.

## Alternative: Existing Package In Place

If the host repo already has a non-trivial root `lakefile.lean`, keep the
existing package and patch it manually:

- add `verso` and `VersoBlueprint` dependencies
- add a `blueprint-gen` executable
- add a root blueprint module and chapter tree
- add `scripts/ci-pages.sh`
- add the Pages workflow

Do not force the helper bootstrap script onto a heavily customized root package.
Use the bootstrap templates as examples and adapt them manually.

## Helper Path

Prefer `tools/verso-harness` as the submodule path. It is short, local to the
repo, and easy to reference from `AGENTS.md`.

## Ignore Patterns

Most host repos should ignore at least:

```text
.lake/
_out/
.beam/
```
