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
  do not invent new dependency edges just to improve graph shape. Prefer node
  metadata such as `(uses := "foo, bar")`; use inline `{uses "foo"}[]` only
  when the source reference is naturally part of the translated prose.
- TeX sources sometimes name a dependency by its `\lean{...}` declaration even
  when the target node has a different `\label{...}`. Verso dependencies and
  references must use the Blueprint label. The source-aware metadata,
  similarity, and status checks accept that label when the maintained TeX
  source establishes the declaration-to-label mapping; keep the adjacent raw
  witness unchanged.
- Translate TeX `\ref{...}` references to blueprint nodes as inline
  `{bpref "..."}[]` links when the prose is only pointing at the node and
  should not add a dependency edge.
- Do not introduce standalone prose lines that exist only to display
  dependency edges; put those edges in `(uses := ...)` on the node instead.
- Treat metadata cleanup as a second phase of LT rather than as a substitute
  for LT. First pair the text with a source witness, then tighten
  `(lean := "...")`, `(uses := ...)`, inline `{uses "..."}[]` where it is
  natural in prose, and `{bpref "..."}[]`.
- Treat dependency metadata such as `uses_origin`, `uses_intent`, inline
  `origin` / `intent`, and `autoDeps` as curation or generated-dependency
  metadata, not as part of the first LT port. Source TeX `\uses{...}` edges
  should remain manual regular edges unless a later review deliberately marks
  a generated/formalization-owned relationship as automatic.
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

Adjacent witnesses are only a local audit trail. They must also remain grounded
in the maintained upstream TeX:

- set `tex_source_glob` to the current source tree, never to a copied snapshot
- when a glob contains legacy or inactive files, declare exact ownership in
  `[lt.source_files]`, mapping every `lt.default_chapters` entry to one or more
  source files
- run `check_lt_source_freshness.py --require-current` after upstream updates;
  it checks witness text and metadata against those sources and reports newly
  added labeled source nodes that are absent locally
- record a necessary non-literal repair in root `lt-source-deviations.toml`;
  witness exceptions use a SHA-256 fingerprint and therefore expire as soon as
  the reviewed witness changes

Example source ownership:

```toml
[lt.source_files]
"MyBlueprint/Chapters/Main.lean" = ["Formalization/blueprint/src/main.tex"]
```

If current upstream TeX names a declaration that was renamed in Lean, preserve
the raw witness and map the source name to the declaration that actually exists:

```toml
[lt.lean_target_aliases]
"Formalization.oldName" = "Formalization.currentName"
```

If upstream TeX names a declaration that has no implementation, keep the local
Blueprint node unattached and record that source debt explicitly in `[lt]`:

```toml
[lt]
unresolved_lean_targets = ["Formalization.notImplemented"]
```

These settings only reconcile source metadata during LT comparison. They do
not create declarations or weaken Verso's external-code resolution. Verify every
alias target with the normal site build or remote Pages CI, and remove aliases
or unresolved entries as soon as upstream metadata and Lean agree again.
`check_harness.py` fails if a configured source-side target no longer occurs in
the maintained TeX source, so these exceptions expire instead of accumulating.

Example reviewed deviation:

```toml
version = 1

[[witness]]
chapter = "MyBlueprint/Chapters/Main.lean"
fingerprint = "<64 lowercase hex characters from the freshness report>"
reason = "Upstream metadata names a removed node; omit the dangling local edge."
```

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
python3 tools/verso-harness/scripts/check_lt_source_freshness.py --project-root . --require-current path/to/Chapter.lean
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
