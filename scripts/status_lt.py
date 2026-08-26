#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from _source_metadata import source_lean_label_aliases  # noqa: E402
from check_lt_similarity import paired_blocks, score_pair  # noqa: E402


def summarize(
    path: Path,
    warn_below: float,
    source_aliases: dict[str, set[str]],
    lean_target_aliases: dict[str, str],
    unresolved_lean_targets: set[str],
) -> str:
    pairs, errors = paired_blocks(path)
    if errors:
        return f"{path.name}: source-pair-errors={len(errors)}"

    scores = [
        score_pair(
            block,
            tex,
            source_aliases=source_aliases,
            lean_target_aliases=lean_target_aliases,
            unresolved_lean_targets=unresolved_lean_targets,
        )
        for block, tex in pairs
    ]
    if not scores:
        return f"{path.name}: no-pairs"

    primary_values = [score.primary_ratio for score in scores]
    low = sum(score.primary_ratio < warn_below for score in scores)
    metadata = sum(score.metadata_diff_count > 0 for score in scores)
    ref_review = sum(score.ref_hint_count > 0 for score in scores)
    strong_refs = sum(len(score.strong_ref_candidates) for score in scores)
    env_refs = sum(len(score.env_ref_hints) for score in scores)
    soft_refs = sum(len(score.soft_ref_hints) for score in scores)
    source_unresolved_lean = sum(len(score.unresolved_tex_lean) for score in scores)
    return (
        f"{path.name}: pairs={len(scores)} "
        f"avg={statistics.mean(primary_values):.3f} "
        f"median={statistics.median(primary_values):.3f} "
        f"low={low} metadata={metadata} "
        f"ref_review={ref_review} "
        f"strong_refs={strong_refs} env_ref_hints={env_refs} "
        f"soft_ref_hints={soft_refs} source_unresolved_lean={source_unresolved_lean}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compact LT status dashboard for one or more chapter files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific Lean chapter files. Defaults to the configured lt.default_chapters.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--warn-below",
        type=float,
        default=0.70,
        help="Similarity warning threshold.",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    paths = resolve_chapter_paths(project_root, args.paths)
    config = load_config(project_root)
    source_aliases = source_lean_label_aliases(project_root, config.tex_source_glob)
    lean_target_aliases = dict(config.lt_lean_target_aliases)
    unresolved_lean_targets = set(config.lt_unresolved_lean_targets)

    if not paths:
        print("no chapter files selected for LT status report", file=sys.stderr)
        return 2

    for path in paths:
        print(
            summarize(
                path,
                args.warn_below,
                source_aliases,
                lean_target_aliases,
                unresolved_lean_targets,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
