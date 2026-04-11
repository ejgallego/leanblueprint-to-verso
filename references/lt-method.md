# LT Method

This helper uses an LT-first workflow for direct TeX-to-Verso chapter work.
`LT` is the canonical term. `LF` (`LaTeX Fidelity`) and `TF` (`Translation
Faithfulness`) are accepted aliases for the same workflow.

## Core Rules

- Do not trust older LT-pass labels by themselves. Under the current method, a
  chapter is not treated as LT-audited until each translated informal block has
  a local adjacent `tex` witness.
- Preserve paragraph boundaries, sentence order, section order, labeled theorem
  order, and local claim order unless a concrete Verso or build constraint
  forces a change.
- Translate TeX layout into Verso with the smallest possible editorial
  footprint. Do not smooth or summarize the prose just because it reads better.
- If the source uses mathematical notation, keep it as mathematics where
  practical rather than demoting it into code spans.
- Valid Verso inline math opens with `$`` and closes with the final backtick
  alone. Because this overlaps with Markdown-style backticks, be conservative:
  do not transform already-valid `$`...`` into the malformed form `$`...`$`.
- Keep prose as prose unless the source already has a corresponding theorem,
  definition, lemma, corollary, proof, or similar graph-visible source object.
- Preserve theorem-like environment kind faithfully. Do not translate a TeX
  lemma, corollary, definition, or proof into a generic `:::theorem` wrapper.
- Do not use `:::theorem` as a generic wrapper for theorem-like source blocks.
- Preserve TeX `\uses{...}` edges when they carry real dependency meaning, but
  do not invent new dependency edges just to improve graph shape.
- When a standalone line would otherwise consist only of consecutive
  `{uses "..."}[]` references, rewrite it deterministically as a sentence that
  starts with `Uses`.
- Use exactly `Uses {uses "..."}[].` for one edge, `Uses {uses "..."}[] and
  {uses "..."}[].` for two edges, and `Uses {uses "..."}[], {uses "..."}[],
  and {uses "..."}[].` for three or more edges.
- Do not paraphrase, reorder, or integrate those standalone `Uses ...` lines
  into surrounding prose; this is a presentation-only normalization that
  applies equally to statements and proofs.
- Treat metadata cleanup as a second phase of LT rather than as a substitute
  for LT. First pair the text with a source witness, then tighten
  `(lean := "...")` and `{uses "..."}[]`.
- When non-literal material is unavoidable, keep it visibly separate and label
  it as an editorial or harness note.

## Witness Discipline

- Each translated informal block should sit immediately next to a labeled
  `tex` block carrying the corresponding TeX source.
- Prefer one translated block per witness block when practical.
- If the translation is not ready yet, keep the source locally in a `tex`
  witness rather than filling the gap with placeholder prose.
- If a block has low LT similarity, first ask whether the witness is oversized
  or misaligned before rewriting faithful prose.

## Triage Order For Low-Similarity Blocks

1. shrink or split the witness to the exact source span
2. remove invented summary structure
3. restore missing source-grounded intermediate nodes
4. only then rewrite the translated prose
5. if none of that yields a trustworthy LT block, fall back to raw `tex`

## Validation Loop

After a coherent direct-port batch, run:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_blueprint_node_kinds.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_verso_math_delimiters.py --project-root . path/to/Chapter.lean
```

Use `lt_audit.py --node-kinds --math-sanity` when you also want the focused
chapter build, optional pages smoke test, the graph-visible node-kind check,
and the conservative math-delimiter check.

Use `lt_audit.py --native-warnings` when you want the focused chapter build to
fail on Lean, Verso, or VersoBlueprint warnings. Generated consumers disable
the noisy `VersoManual` inline-code line-length warning by default, so this is
intended for math lint and other structural warning surfaces rather than prose
formatting noise.
By default this warning-fail mode only fails on consumer-owned warnings. The
audit still prints separate summaries for vendored-formalization warnings and
`.lake/packages` dependency warnings without failing the run for them.
Use `--native-warnings-scope all` when you want full transitive warning failure.

The default `lt_audit.py` native warning mode follows
`harness.native_warnings` in `verso-harness.toml`, and generated consumers keep
the version-appropriate `strictResolve` lean option aligned with
`harness.strict_external_code`.
