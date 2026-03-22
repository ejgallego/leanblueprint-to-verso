# Leanblueprint Verso Helper

This repository is a reusable helper intended to be added as a submodule inside
a host Lean project that is porting a `leanblueprint` or TeX blueprint to
`verso-blueprint`.

## Scope

- Keep only reusable docs, snippets, scripts, and templates here.
- Do not store host-project mathematics, declarations, or chapter prose here.
- The host repository owns the files materialized into its root.

## Primary Workflows

- For first-time setup of an outer harness, use `scripts/bootstrap.py`.
- For maintenance of helper-owned CI files, use `scripts/update_ci.py`.
- For audits, use `scripts/check_harness.py`.
- Read the relevant file in `references/` before changing script or template
  behavior.

## Porting Rules

- Treat the legacy TeX or `leanblueprint` source as the content source of truth
  for prose structure.
- Prefer faithful TeX-to-Verso translation over editorial rewriting.
- Preserve section order, labeled theorem order, and dependency structure unless
  there is a clear build or project-structure reason not to.
- Treat the host formalization as the source of truth.
- Prefer `(lean := "...")` links to existing declarations instead of copying
  Lean code into blueprint pages.
- Preserve TeX `\uses{...}` edges as Verso `{uses "..."}[]` references inside
  the relevant theorem, definition, or proof nodes rather than leaving them in
  free prose.
- If a chapter is only partially ported, continue with the next coherent
  section block instead of scattering edits across unrelated files.
- Keep shared macros in one `TeXPrelude` module.
- Validate edited blueprint modules incrementally.
- After a coherent batch, run `bash ./scripts/ci-pages.sh`.
- Keep the root build green. If a faithful Lean link would pull in imports that
  are not harness-clean on the current toolchain, leave the chapter informal
  and note the dependency in prose instead of breaking the build.
- If using `lean-beam`, prefer one-module-at-a-time `sync` calls unless the
  target repo is known to tolerate concurrent sync traffic.
- Keep template changes, docs, and snippets aligned.

## Validation

- After changing scripts, run at least the `--help` surface.
- After changing templates, bootstrap into a scratch directory and run
  `scripts/check_harness.py` against that generated tree.
