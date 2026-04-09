# Leanblueprint To Verso Harness Notes

- This repo uses the local helper at `tools/verso-harness`.
- Keep a root `verso-harness.toml` checked in and treat it as the source of
  truth for package layout, LT chapter scope, and the TeX source path.
- Before porting or maintaining blueprint files, read:
  - `tools/verso-harness/references/layout.md`
  - `tools/verso-harness/references/lt-method.md`
  - `tools/verso-harness/references/porting.md`
  - `tools/verso-harness/references/maintenance.md`
  - `tools/verso-harness/references/retrofit.md`
  - `tools/verso-harness/references/beam-validation.md`
- Use `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
  to audit the local harness.
- Treat the legacy TeX or `leanblueprint` source as the prose source of truth.
- Record the real TeX chapter source locator for this repo. The common legacy
  layout is `./blueprint/src/chapter/*.tex`, but some projects use a single
  file such as `./blueprint/src/chapter/main.tex`; verify it before wiring
  status pages or source-backed notes.
- The default deliverable for direct-port chapters is an LT pass. Do not trust
  older LT labels by themselves; every translated informal block now needs an
  adjacent local `tex` witness.
- Preserve section order, paragraph boundaries, labeled theorem order, and
  important dependency edges when translating to Verso.
- Treat the host formalization as the source of truth.
- Prefer `(lean := "...")` links to real declarations rather than duplicating
  Lean code in blueprint modules.
- Preserve TeX `\uses{...}` edges as Verso `{uses "..."}[]` references inside
  the relevant node or proof, not just in free prose.
- Keep prose as prose unless the source really gives a graph-visible theorem,
  definition, lemma, corollary, or proof-style object.
- Preserve TeX environment kind faithfully. Use `:::lemma_` for TeX
  `\begin{lemma}`, `:::corollary` for `\begin{corollary}`, `:::definition` for
  `\begin{definition}`, `:::proof` for `\begin{proof}`, and reserve
  `:::theorem` for `\begin{theorem}`.
- Do not use `:::theorem` as a generic wrapper for source material that should
  remain prose or another node kind.
- When the source block still needs to stay visible, prefer a labeled local
  `tex` block over rewriting it into placeholder prose.
- Treat metadata cleanup as a second phase of LT rather than as a substitute
  for LT.
- Port coherent chapter blocks rather than scattering small edits across
  unrelated chapters.
- Keep shared TeX macros in one `TeXPrelude.lean` module.
- Prefer the harness pattern where `VersoBlueprint` drives the `verso`
  dependency unless this repo has a concrete reason to pin `verso` directly.
- After editing direct-port chapters, run:
  - `python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . <chapter.lean>`
  - `python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . <chapter.lean>`
- Use `python3 tools/verso-harness/scripts/check_blueprint_node_kinds.py --project-root . <chapter.lean>`
- Use `python3 tools/verso-harness/scripts/check_source_label_grounding.py --project-root . <chapter.lean>`
- Use `python3 tools/verso-harness/scripts/lt_audit.py --project-root . <chapter.lean>`
  when you want the source-pair check, similarity report, focused build, and
  optional extra checks such as `--node-kinds`, `--math-sanity`, or pages
  smoke test in one command.
- After a coherent batch, run `bash ./scripts/ci-pages.sh`.
- Keep the root build green. If a Lean link would pull in imports that are not
  harness-clean on the current toolchain, leave the node informal and note the
  dependency in prose instead.
- If using `lean-beam`, avoid parallel `sync` calls against the same project
  root unless the target repo is known to tolerate it.
- If using sub-agents, prefer one agent per chapter or per clearly disjoint file set.
- Do not split one chapter across multiple agents unless one side is read-only.
- Merge chapter edits before running shared validation steps.
