#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_similarity import paired_blocks, score_pair  # noqa: E402


def summarize(path: Path, warn_below: float) -> str:
    pairs, errors = paired_blocks(path)
    if errors:
        return f"{path.name}: source-pair-errors={len(errors)}"

    scores = [score_pair(block, tex) for block, tex in pairs]
    if not scores:
        return f"{path.name}: no-pairs"

    primary_values = [score.primary_ratio for score in scores]
    low = sum(score.primary_ratio < warn_below for score in scores)
    metadata = sum(score.metadata_diff_count > 0 for score in scores)
    strong_refs = sum(len(score.strong_ref_candidates) for score in scores)
    env_refs = sum(len(score.env_ref_hints) for score in scores)
    return (
        f"{path.name}: pairs={len(scores)} "
        f"avg={statistics.mean(primary_values):.3f} "
        f"median={statistics.median(primary_values):.3f} "
        f"low={low} metadata={metadata} "
        f"strong_refs={strong_refs} env_ref_hints={env_refs}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compact LT status dashboard for one or more chapter files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help=(
            "Specific Lean chapter files. "
            "Defaults to all files under <package>/Chapters."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--package-name",
        default=None,
        help="Blueprint package name. Inferred from lakefile.lean by default.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help=(
            "Exclude chapter paths when using default discovery. "
            "Matches repo-relative glob patterns or exact file names."
        ),
    )
    parser.add_argument(
        "--warn-below",
        type=float,
        default=0.70,
        help="Similarity warning threshold.",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    paths = resolve_chapter_paths(project_root, args.paths, args.package_name, args.exclude)

    if not paths:
        print("no chapter files selected for LT status report", file=sys.stderr)
        return 2

    for path in paths:
        print(summarize(path, args.warn_below))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
