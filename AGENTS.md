# Leanblueprint To Verso Harness

This repository is a reusable helper intended to be added as a submodule inside
a host Lean project that is porting a `leanblueprint` or TeX blueprint source to
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
  `scripts/check_verso_math_delimiters.py`, `scripts/status_lt.py`, and
  `scripts/lt_audit.py`.
- For older ports that predate the source-paired LT method, read
  `references/retrofit.md` before editing chapters.
- Read the relevant file in `references/` before changing script or template
  behavior.

## LT Standard

- Treat the legacy TeX or `leanblueprint` source as the content source of truth
  for prose structure.
- Identify the actual TeX chapter source locator in the host repo early. A
  common layout is `./blueprint/src/chapter/*.tex`, but some projects use a
  single file such as `./blueprint/src/chapter/main.tex`; do not assume either
  layout without checking.
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
- The upstream formalization determines the Lean toolchain. Keep the root
  `lean-toolchain` equal to the upstream value, and choose the matching
  `VersoBlueprint` branch `lean-<release>` unless explicit compatibility work
  says otherwise.
- Validate edited blueprint modules incrementally.
- After a coherent batch, run `bash ./scripts/ci-pages.sh`.
- Keep the root build green. If a faithful Lean link would pull in imports that
  are not harness-clean on the current toolchain, leave the chapter informal
  and note the dependency in prose instead of breaking the build.
- If using `lean-beam`, prefer one-module-at-a-time `sync` calls unless the
  target repo is known to tolerate concurrent sync traffic.
- Keep template changes, docs, and snippets aligned.

## Sub-Agent Coordination

- Prefer one agent per chapter, or one agent per clearly disjoint file set.
- Do not split one chapter across multiple agents unless one side is read-only.
- Keep every agent on the same `verso-harness.toml` contract for package layout, chapter scope, and TeX source location.
- Good parallel lanes are independent direct-port chapters or one chapter edit plus one audit-only lane on a different chapter.
- Avoid concurrent edits to shared root files such as `lakefile.lean`, `lean-toolchain`, `verso-harness.toml`, `BlueprintMain.lean`, or shared chapter index files unless one agent owns that whole write scope.
- Serialize repository-level validation. In particular, do not run multiple whole-site builds or multiple `lean-beam sync` requests against the same project root at the same time.
- Merge the chapter-level edits first, then run the final shared validation steps once.

## Validation

- After changing scripts, run at least the `--help` surface.
- When changing LT similarity or grounding tooling, run:
  - `python3 scripts/test_harness_config.py`
  - `python3 scripts/test_check_lt_similarity.py`
  - `python3 scripts/test_check_source_label_grounding.py`
- After changing templates, run `python3 scripts/test_bootstrap.py`.
- When changing the canonical startup flow, run `python3 scripts/test_start_new_port.py`.
