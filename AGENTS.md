# TeX Blueprint To Verso Harness

This repository is a reusable helper intended to be added as a submodule inside
a host Lean project that is porting a TeX blueprint or `leanblueprint` source to
`verso-blueprint`, or updating an older Verso harness to the current LT method.

## Scope

- Keep only reusable docs, snippets, scripts, and templates here.
- Do not store host-project mathematics, declarations, or chapter prose here.
- The host repository owns the files materialized into its root.
- Helper-managed repos must declare their layout explicitly in
  `verso-harness.toml`; this helper does not guess package or chapter layout.

## Primary Workflows

- For first-time setup of an outer harness, use `scripts/bootstrap.py`.
- For maintenance of helper-owned CI files, use `scripts/update_ci.py`.
- For audits, use `scripts/check_harness.py`.
- For direct-port LT audits, use `scripts/check_lt_source_pairs.py`,
  `scripts/check_lt_similarity.py`, `scripts/check_source_label_grounding.py`,
  `scripts/status_lt.py`, and
  `scripts/lt_audit.py`.
- For older ports that predate the source-paired LT method, read
  `references/retrofit.md` before editing chapters.
- Read the relevant file in `references/` before changing script or template
  behavior.

## LT Standard

- Treat the legacy TeX or `leanblueprint` source as the content source of truth
  for prose structure.
- Identify the actual TeX chapter source path in the host repo early. A common
  layout is `./blueprint/src/chapter/*.tex`, but do not assume that path
  without checking.
- Prefer faithful TeX-to-Verso translation over editorial rewriting.
- Do not trust older pass labels by themselves. A chapter is not LT-audited
  under the current method until each translated informal block has an adjacent
  local `tex` witness.
- Preserve section order, paragraph boundaries, labeled theorem order, and
  dependency structure unless there is a clear build or project-structure
  reason not to.
- Treat the host formalization as the source of truth.
- Prefer `(lean := "...")` links to existing declarations instead of copying
  Lean code into blueprint pages.
- Preserve TeX `\uses{...}` edges as Verso `{uses "..."}[]` references inside
  the relevant theorem, definition, or proof nodes rather than leaving them in
  free prose.
- When a source block still needs to be shown verbatim, prefer a local labeled
  `tex` block over rewriting it into placeholder prose.
- Treat metadata cleanup as a second phase of LT rather than as a substitute
  for LT. First localize the text with a `tex` witness, then tighten
  `(lean := "...")` and `{uses "..."}[]`.
- If a chapter is only partially ported, continue with the next coherent
  section block instead of scattering edits across unrelated files.
- Keep shared macros in one `TeXPrelude` module.
- Keep the harness dependency stack aligned with the current pattern where
  `VersoBlueprint` drives the `verso` dependency unless the host repo has a
  clear reason to pin `verso` directly.
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
- When changing LT similarity or grounding tooling, run:
  - `python3 scripts/test_harness_config.py`
  - `python3 scripts/test_check_lt_similarity.py`
  - `python3 scripts/test_check_source_label_grounding.py`
- After changing templates, run `python3 scripts/test_bootstrap.py`.

