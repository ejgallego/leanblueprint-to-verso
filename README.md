# Leanblueprint To Verso Harness

This repository helps you turn an existing `leanblueprint` or TeX blueprint
project into a Verso-based blueprint site.

Use it when:
- you are starting a new blueprint port from scratch
- you already have an older port and want to bring it up to the current shared setup

The normal operating model is:
- a human sets up the repo with this harness
- the human uses Codex CLI to issue prompts and carry out the porting work
- Codex reads `verso-harness.toml`, `AGENTS.md`, and the harness docs
- Codex should use the harness-provided checking tools for fidelity, grounding, graph shape, and port status

## Start Here

Add the shared harness to your repo:

```bash
git submodule add git@github.com:ejgallego/leanblueprint-to-verso.git tools/verso-harness
```

If you are starting a brand-new port from an empty directory, the first command
you should run is:

```bash
python3 tools/verso-harness/scripts/start_new_port.py \
  --project-root . \
  --package-name <BlueprintPackage> \
  --title "<Project Title>" \
  --formalization-name <FormalizationName> \
  --formalization-remote <upstream-formalization-git-url> \
  --formalization-path <FormalizationName> \
  --tex-source-glob "<relative-tex-source-path-or-glob>"
```

After that:
1. review `verso-harness.toml`
2. add your first real chapter file under `chapter_root`
3. set `lt.default_chapters`
4. review `harness.native_warnings` and `harness.strict_external_code`
5. run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`
6. copy `tools/verso-harness/snippets/AGENTS.host.md` into `AGENTS.md`
7. choose the first direct-port chapter from `lt.default_chapters`
8. open Codex CLI and issue the first porting prompt for one coherent section of that chapter

The startup flow intentionally does not generate synthetic chapter prose.
`lt.default_chapters` is only for real source-backed direct-port chapters.

## The Three Main Rules

- The upstream math project decides the Lean toolchain.
- Every managed repo must have a root `verso-harness.toml` file.
- New ports use one standard layout; do not invent a new one.

## If Your Repo Already Exists

If you already have an older port, use the retrofit path instead of the
empty-directory start path:

- [`references/retrofit.md`](references/retrofit.md)
- [`references/maintenance.md`](references/maintenance.md)

## Common Commands

Start any maintenance pass with the repo-level status check:

```bash
python3 tools/verso-harness/scripts/status_harness.py --project-root .
```

Then check that the repo still matches the expected shared setup:

```bash
python3 tools/verso-harness/scripts/check_harness.py --project-root .
```

Run the main direct-port chapter audit commands:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_blueprint_node_kinds.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_source_label_grounding.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_verso_math_delimiters.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . --native-warnings path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . --native-warnings --native-warnings-scope all path/to/Chapter.lean
```

## More Detailed Docs

Start a new port from an empty directory:
- [`references/start-new-port.md`](references/start-new-port.md)

Short adoption checklist:
- [`references/new-consumer-checklist.md`](references/new-consumer-checklist.md)

Detailed porting workflow:
- [`references/porting.md`](references/porting.md)
- [`references/lt-method.md`](references/lt-method.md)
- [`AGENTS.md`](AGENTS.md)

## Notes

- The shared setup may change over time because it is used by more than one
  project. If `tools/verso-harness` changes unexpectedly, inspect the helper
  diff and rerun `check_harness.py`.
- Generated `.github/workflows/blueprint.yml` files are thin callers into the
  reusable Pages workflow shipped by `verso-blueprint` and pinned to the same
  `VersoBlueprint` ref used in `lakefile.lean`.
- The helper chooses the matching `VersoBlueprint` branch from the Lean
  toolchain used by the upstream math project.
- Generated consumers keep the version-appropriate Verso math-lint option
  enabled and disable the noisy `VersoManual` inline-code line-length warning
  via `verso.code.warnLineLength := 0`.
- Generated consumers also set
  the version-appropriate strict-resolve option from the default harness
  warning policy, and `check_harness.py` verifies that `lakefile.lean` stays
  aligned with the declared `verso-harness.toml` settings.
- Verso inline math opens with `$`` and closes with the final backtick alone.
  The malformed TeX-like pattern `$`...`$` must not be introduced while porting.
- Generated `README.md` files are starting points only; after bootstrap they are
  project-owned.
