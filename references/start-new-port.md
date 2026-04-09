# Start A New Port

This is the canonical startup path for a new Leanblueprint-to-Verso project.
Use it from an empty directory. Do not ask the agent to choose a layout.

## Canonical Shape

Always create a dedicated integration repository whose root is the Verso
harness, and vendor the upstream formalization as a submodule.

```text
<project>-verso/
├── tools/verso-harness/
├── <Formalization>/
├── <BlueprintPackage>.lean
├── <BlueprintPackage>/
│   ├── TeXPrelude.lean
│   └── Chapters/
├── <BlueprintMain>.lean
├── verso-harness.toml
├── lakefile.lean
├── lean-toolchain
├── scripts/ci-pages.sh
└── .github/workflows/blueprint.yml
```

There is no startup choice between “outer harness” and “in-place harness” for
new ports. New ports use this layout. Existing repos that cannot adopt it fall
under retrofit work instead.

## Canonical Commands

```bash
mkdir <project>-verso
cd <project>-verso
git init
git submodule add git@github.com:ejgallego/leanblueprint-to-verso.git tools/verso-harness
python3 tools/verso-harness/scripts/start_new_port.py \
  --project-root . \
  --package-name <BlueprintPackage> \
  --title "<Project Title>" \
  --formalization-name <FormalizationName> \
  --formalization-remote <upstream-formalization-git-url> \
  --formalization-path <FormalizationName> \
  --tex-source-glob "<relative-tex-source-path-or-glob>"
```

After the script finishes:

1. confirm that `lean-toolchain` at repo root matches the upstream formalization
2. confirm that `lakefile.lean` points to the matching `VersoBlueprint` branch `lean-<release>`
3. review `verso-harness.toml` and verify that `formalization_path` matches the
   upstream submodule path
4. review `verso-harness.toml` and verify that `tex_source_glob` points at the
   real TeX source locator; some projects use a multi-file pattern such as
   `./blueprint/src/chapter/*.tex`, while others use a single file such as
   `./blueprint/src/chapter/main.tex`
5. set `lt.default_chapters` explicitly
6. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
7. copy `tools/verso-harness/snippets/AGENTS.host.md` into `AGENTS.md`
8. start the first LT chapter pass

## Start-Port Prompt

Use this prompt for the first porting session in a freshly created consumer:

```text
Use tools/verso-harness and the repo root verso-harness.toml.
Treat the legacy TeX / leanblueprint source as read-only source of truth.
Start a faithful LT pass on the first unchecked chapter in lt.default_chapters.
Do not rewrite the prose for style.
Add adjacent tex witnesses for every translated informal block.
Do not invent new dependency edges or placeholder Lean declarations.
After the edit, run check_lt_source_pairs.py, check_lt_similarity.py, and check_source_label_grounding.py on the touched chapter.
Record any deliberate non-literal deviations.
```
