# Beam Validation

Prefer incremental validation over full rebuild loops when that is enough to
check the latest change.

## Beam-First Loop

If `lean-beam` is available:

```bash
lean-beam ensure .
lean-beam sync "MyProjectBlueprint/Chapters/Introduction.lean"
```

Useful follow-up probes include:

```bash
lean-beam hover "MyProjectBlueprint/Chapters/Introduction.lean" 20 10
lean-beam run-at "MyProjectBlueprint/Chapters/Introduction.lean" 20 10
```

## Concurrency Caution

In `verso-flt`, running multiple `lean-beam sync` requests in parallel against
the same project root sometimes caused worker exits and incomplete barriers.
Treat one-module-at-a-time sync as the conservative default unless the target
repo is known to behave well under concurrent sync traffic.

## When To Escalate

Escalate from Beam to a normal build when:

- the imported dependency chain changed
- the file needs code generation side effects
- Beam looks stale or unhealthy
- the error seems to come from the package graph rather than one module

Focused build:

```bash
nice lake build blueprint-gen
```

LT audit stack for one or more touched chapters:

```bash
python3 tools/verso-harness/scripts/check_lt_source_pairs.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/check_blueprint_node_kinds.py --project-root . path/to/Chapter.lean
python3 tools/verso-harness/scripts/lt_audit.py --project-root . --node-kinds path/to/Chapter.lean
```

Site smoke test:

```bash
bash ./scripts/ci-pages.sh
```

For longer rebuild loops, fetch the mathlib cache first if the host project uses
it.
