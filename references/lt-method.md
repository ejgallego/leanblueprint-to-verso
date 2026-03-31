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
- Do not promote plain prose into new theorem, definition, or proof nodes
  unless the source already has a corresponding formal environment or proof
  step that should remain graph-visible.
- Preserve TeX `\uses{...}` edges when they carry real dependency meaning, but
  do not invent new dependency edges just to improve graph shape.
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
```

Use `lt_audit.py` when you also want the focused chapter build and optional
pages smoke test.
