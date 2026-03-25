# Verso Harness Notes

- This repo uses the local helper at `tools/verso-harness`.
- Before porting or maintaining blueprint files, read:
  - `tools/verso-harness/references/layout.md`
  - `tools/verso-harness/references/porting.md`
  - `tools/verso-harness/references/maintenance.md`
  - `tools/verso-harness/references/beam-validation.md`
- Use `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
  to audit the local harness.
- Treat the legacy TeX or `leanblueprint` source as the prose source of truth.
- Record the real TeX chapter source path for this repo. The common legacy
  layout is `./blueprint/src/chapter/*.tex`, but verify it before wiring status
  pages or source-backed notes.
- Preserve section order, labeled theorem order, and important dependency edges
  when translating to Verso.
- Treat the host formalization as the source of truth.
- Prefer `(lean := "...")` links to real declarations rather than duplicating
  Lean code in blueprint modules.
- Preserve TeX `\uses{...}` edges as Verso `{uses "..."}[]` references inside
  the relevant node or proof, not just in free prose.
- When the source block still needs to stay visible, prefer a labeled local
  `tex` block over rewriting it into placeholder prose.
- Port coherent chapter blocks rather than scattering small edits across
  unrelated chapters.
- Keep shared TeX macros in one `TeXPrelude.lean` module.
- Prefer the harness pattern where `VersoBlueprint` drives the `verso`
  dependency unless this repo has a concrete reason to pin `verso` directly.
- After a coherent batch, run `bash ./scripts/ci-pages.sh`.
- Keep the root build green. If a Lean link would pull in imports that are not
  harness-clean on the current toolchain, leave the node informal and note the
  dependency in prose instead.
- If using `lean-beam`, avoid parallel `sync` calls against the same project
  root unless the target repo is known to tolerate it.
