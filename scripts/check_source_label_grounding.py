#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_similarity import paired_blocks, score_pair  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report source-grounded Verso nodes whose ids do not match the adjacent "
            "TeX/source label (or fallback TeX lean target when no label exists)."
        )
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
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    paths = resolve_chapter_paths(project_root, args.paths)

    found = False
    for path in paths:
        pairs, errors = paired_blocks(path)
        if errors:
            for error in errors:
                print(f"{path}: cannot check label grounding because {error}")
            found = True
            continue
        for block, tex in pairs:
            score = score_pair(block, tex)
            candidates = sorted(score.label_regrounding_candidates)
            if not candidates:
                continue
            found = True
            print(
                f"{path}:{block.start_line}: verso id {score.verso_header_id!r} "
                f"does not match source label(s) {candidates!r}"
            )

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
