# Porting

Use this workflow when migrating an existing `leanblueprint` or TeX blueprint to
Verso.

## 1. Establish The Source Of Truth

- Treat the legacy TeX or `leanblueprint` source as authoritative for the prose
  structure and dependency story.
- Record the actual TeX source location in the host repo. The common legacy
  layout is `./blueprint/src/chapter/*.tex`, but some projects use a single
  file such as `./blueprint/src/chapter/main.tex`; verify the real source
  locator before using it in the local harness.
- Preserve section order, paragraph boundaries, labeled theorem order, and
  mathematical claims unless there is a clear harness or tooling reason not to.
- Prefer faithful TeX-to-Verso translation over editorial rewriting.
- Identify where the real Lean declarations live.
- Treat those modules as authoritative.
- Prefer `(lean := "...")` links in blueprint nodes instead of duplicating
  formalized statements in prose modules.

Read [lt-method.md](lt-method.md) before editing chapters. The current LT
baseline is stricter than earlier harness passes: each translated informal
block now needs an adjacent local `tex` witness.

If the target declaration chain does not compile on the chosen toolchain, treat
that as a deliberate formalization compatibility task rather than papering over
the problem in the blueprint.

## 2. Choose The Harness Shape

- Use the bootstrap path when the host repo can use a dedicated outer harness at
  its root.
- Use the manual path when the host already has a complex root package that must
  be preserved.

See `[layout.md](layout.md)` before choosing.

## 3. Seed The Harness

For the outer-harness path, run `scripts/bootstrap.py`.

For the in-place path, copy the template ideas manually:

- one root blueprint module
- one `BlueprintMain.lean`
- one shared `TeXPrelude.lean`
- one or more real source-backed chapter files
- one site-generation smoke test
- one Pages workflow

Do not add synthetic starter chapters. Treat `lt.default_chapters` as the
direct-port LT scope and populate it only with real source-backed chapter files.

## 4. Port Chapter Content Incrementally

- Start with a small chapter or one stable slice of the old blueprint.
- Work chapter-by-chapter and continue with the next coherent section block if
  a chapter is only partially ported.
- Pair each translated informal block with an adjacent labeled `tex` block from
  the source. This is part of the LT pass itself, not an optional cleanup step.
- Keep shared TeX macros in `TeXPrelude.lean`.
- Reuse the old macro vocabulary where it helps, but keep the prelude small.
- Inline math opens with `$`` and closes with a backtick.
- Display math uses `$$`` ... ``.
- When the TeX source has a labeled theorem, definition, lemma, corollary, or
  proof step that still matters to the dependency story, prefer creating a
  corresponding Verso node rather than burying it in prose.
- Keep prose as prose unless the source really gives a graph-visible theorem,
  definition, lemma, corollary, or proof-style object.
- Preserve TeX environment kind faithfully instead of flattening different
  theorem-like environments into a generic `:::theorem` wrapper.
- Do not use `:::theorem` as a generic wrapper for graph noise control or
  chapter organization.
- When the TeX source has `\uses{...}`, preserve those edges as
  `{uses "..."}[]` references inside the relevant node or proof rather than in
  free prose.
- When a standalone line would otherwise consist only of consecutive
  `{uses "..."}[]` references, rewrite it deterministically as a sentence that
  starts with `Uses`.
- Use exactly `Uses {uses "..."}[].` for one edge, `Uses {uses "..."}[] and
  {uses "..."}[].` for two edges, and `Uses {uses "..."}[], {uses "..."}[],
  and {uses "..."}[].` for three or more edges.
- Do not paraphrase, reorder, or integrate those standalone `Uses ...` lines
  into surrounding prose; this is a presentation-only normalization that
  applies equally to statements and proofs.
- Do not treat metadata cleanup as LT completion. First localize the text with
  a source witness, then tighten `(lean := "...")` and `{uses "..."}[]`.

Do not port the whole blueprint in one pass. Edit one module, validate it, then
continue.

## 5. Attach Real Lean References

When a node corresponds to an existing theorem or definition, add the real
declaration name with `(lean := "...")`.

Before adding a link:

- confirm the declaration name
- confirm the import chain is acceptable for the harness
- prefer the narrowest import that keeps the chapter stable

## 6. Validate Often

Use the Beam-first workflow in `[beam-validation.md](beam-validation.md)`.

In practice:

- save the edited module
- run one `lean-beam sync` for that module if Beam is available
- only escalate to `lake build` or `bash ./scripts/ci-pages.sh` when needed
- after a coherent batch, use `bash ./scripts/ci-pages.sh` as the site smoke
  test

For direct-port chapters, the normal LT audit stack is:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_blueprint_node_kinds.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . --native-warnings path/to/Chapter.lean
```

The default `lt_audit.py` native warning behavior follows
`harness.native_warnings` in `verso-harness.toml`. Use `--native-warnings` or
`--no-native-warnings` to override it for one run.
When enabled, the default warning-fail scope is consumer-owned files only. The
audit still reports separate vendored-formalization and `.lake/packages`
warning summaries without failing for them. Use `--native-warnings-scope all`
for full transitive warning failure.

Treat low similarity scores as a triage signal, not as permission to rewrite
freely. First ask whether the witness is too large, whether metadata drift is
masking an otherwise faithful block, or whether the translation is genuinely
non-literal.

Keep the root build green. If a faithful Lean link would pull in imports that
are not harness-clean on the current toolchain, leave the chapter informal and
note the dependency in prose instead of breaking the build.

## 7. Keep Integration And Formalization Work Separate

- Blueprint/harness changes belong in the host root.
- Wider formalization compatibility fixes belong in the formalization codebase.
- If the formalization is vendored as a submodule, update that pointer
  deliberately after compatibility fixes land.
- Commit coherent validated batches in the host repo instead of mixing unrelated
  chapter edits together.

## 8. Record Deviations Explicitly

After each porting batch, record any deliberate non-literal changes in the work
summary:

- additions
- omissions
- reordered material
- invented nodes
- editorial notes
