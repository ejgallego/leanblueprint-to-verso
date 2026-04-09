# New Consumer Checklist

Canonical helper repository: `leanblueprint-to-verso`.

Use this checklist when adopting the helper in a fresh or newly-retrofitted
consumer repository.

## 1. If This Is A New Port, Use The Canonical Start Flow

For a new project from an empty directory, do not improvise a layout. Use:

- `references/start-new-port.md`
- `scripts/start_new_port.py`

## 2. Add The Helper

```bash
git submodule add git@github.com:ejgallego/leanblueprint-to-verso.git tools/verso-harness
```

## 3. Create The Root Harness Config

Every helper-managed repo must carry a checked-in `verso-harness.toml` at repo
root. The repo root `lean-toolchain` must match the upstream formalization's
`lean-toolchain`.

Minimum required fields:

```toml
package_name = "MyProjectBlueprint"
blueprint_main = "BlueprintMain"
formalization_path = "MyProject"
chapter_root = "MyProjectBlueprint/Chapters"
tex_source_glob = "./blueprint/src/chapter/main.tex"

[lt]
default_chapters = [
  "MyProjectBlueprint/Chapters/Introduction.lean",
]

[harness]
non_port_chapters = [
  "MyProjectBlueprint/Chapters/PortingStatus.lean",
]
```

Use the actual relative TeX source locator here. Some projects use a single
file such as `./blueprint/src/chapter/main.tex`; others use a multi-file
pattern such as `./blueprint/src/chapter/*.tex`.

Use explicit chapter paths. Do not rely on helper-side discovery heuristics.
For new ports, do not choose the Lean toolchain independently: the upstream
formalization is authoritative, and the helper should choose the matching
`VersoBlueprint` branch `lean-<release>`.

## 4. Validate The Harness Shape

Run:

```bash
python3 tools/verso-harness/scripts/check_harness.py --project-root .
```

Do not proceed with LT audit or chapter work until this passes.

## 5. Install The Host Instructions

Pull the guidance from `tools/verso-harness/snippets/AGENTS.host.md` into the
consumer repo's `AGENTS.md`.

## 6. Start The Port With A Concrete Prompt

Use the shared checking tools from `tools/verso-harness/scripts/...` for
fidelity, grounding, math sanity, and port status.


For a regular blueprint repository, start the port with a concrete request like:

```text
Use tools/verso-harness and the repo root verso-harness.toml.
Treat the legacy TeX / leanblueprint source as read-only source of truth.
Start a faithful LT pass on the first unchecked chapter in lt.default_chapters.
Do not rewrite the prose for style.
Add adjacent tex witnesses for every translated informal block.
After the edit, run check_lt_source_pairs.py, check_lt_similarity.py, check_source_label_grounding.py, and check_verso_math_delimiters.py on the touched chapter.
Record any deliberate non-literal deviations.
```

Use a chapter-specific variant once the first pass is underway:

```text
Use tools/verso-harness and verso-harness.toml.
Continue the LT pass on <chapter>.lean only.
Preserve source order and local claim order.
Do not invent new dependency edges or placeholder Lean declarations.
Run the helper LT audit stack on that chapter before stopping.
```

## 7. Port And Audit Direct-Port Chapters

For each touched direct-port chapter, run:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_source_label_grounding.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_verso_math_delimiters.py --project-root . path/to/Chapter.lean
```

Use the one-shot combined command when useful:

```bash
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
```

## 8. Run The Site Smoke Test

```bash
bash ./scripts/ci-pages.sh
```

## 9. Keep Ownership Clear

Helper-owned and safe to refresh mechanically:

- `scripts/ci-pages.sh`
- `.github/workflows/blueprint.yml`

Host-owned and review-driven:

- `README.md`
- `verso-harness.toml`
- `lakefile.lean`
- `lean-toolchain`
- `BlueprintMain.lean` or the configured `blueprint_main`
- root blueprint modules and chapter prose
- declaration attachments and dependency metadata
