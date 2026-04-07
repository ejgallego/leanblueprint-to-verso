# New Consumer Checklist

Use this checklist when adopting the helper in a fresh or newly-retrofitted
consumer repository.

## 1. Add The Helper

```bash
git submodule add <helper-repo-url> tools/verso-harness
```

## 2. Create The Root Harness Config

Every helper-managed repo must carry a checked-in `verso-harness.toml` at repo
root.

Minimum required fields:

```toml
package_name = "MyProjectBlueprint"
blueprint_main = "BlueprintMain"
chapter_root = "MyProjectBlueprint/Chapters"
tex_source_glob = "./blueprint/src/chapter/*.tex"

[lt]
default_chapters = [
  "MyProjectBlueprint/Chapters/Introduction.lean",
]

[harness]
non_port_chapters = [
  "MyProjectBlueprint/Chapters/PortingStatus.lean",
]
```

Use explicit chapter paths. Do not rely on helper-side discovery heuristics.

## 3. Bootstrap Or Retrofit

For a new outer harness:

```bash
python3 tools/verso-harness/scripts/bootstrap.py \
  --project-root . \
  --package-name MyProjectBlueprint \
  --title "My Project Blueprint" \
  --formalization-name MyProject \
  --formalization-path "./MyProject"
```

For an existing harness, keep the root project-owned files and read:

- `references/retrofit.md`
- `references/maintenance.md`
- `snippets/AGENTS.host.md`

## 4. Validate The Harness Shape

Run:

```bash
python3 tools/verso-harness/scripts/check_harness.py --project-root .
```

Do not proceed with LT audit or chapter work until this passes.

## 5. Install The Host Instructions

Pull the guidance from `tools/verso-harness/snippets/AGENTS.host.md` into the
consumer repo's `AGENTS.md`.

## 6. Port And Audit Direct-Port Chapters

For each touched direct-port chapter, run:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_source_label_grounding.py --project-root . path/to/Chapter.lean
```

Use the one-shot combined command when useful:

```bash
python3 tools/verso-harness/scripts/lt_audit.py --project-root . path/to/Chapter.lean
```

## 7. Run The Site Smoke Test

```bash
bash ./scripts/ci-pages.sh
```

## 8. Keep Ownership Clear

Helper-owned and safe to refresh mechanically:

- `scripts/ci-pages.sh`
- `.github/workflows/blueprint.yml`

Host-owned and review-driven:

- `verso-harness.toml`
- `lakefile.lean`
- `lean-toolchain`
- `BlueprintMain.lean` or the configured `blueprint_main`
- root blueprint modules and chapter prose
- declaration attachments and dependency metadata
