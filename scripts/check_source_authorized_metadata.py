#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from _source_metadata import source_lean_label_aliases  # noqa: E402
from check_lt_similarity import paired_blocks, score_pair  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when local manual Verso `{uses ...}`, `{bpref ...}`, or "
            "`(lean := ...)` metadata is not authorized by the adjacent TeX witness. "
            "Automatic dependency edges are treated as generated metadata and ignored."
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
    config = load_config(project_root)
    aliases = source_lean_label_aliases(project_root, config.tex_source_glob)
    lean_target_aliases = dict(config.lt_lean_target_aliases)
    unresolved_lean_targets = set(config.lt_unresolved_lean_targets)

    found = False
    for path in paths:
        pairs, errors = paired_blocks(path)
        if errors:
            for error in errors:
                print(f"{path}: cannot check source-authorized metadata because {error}")
            found = True
            continue
        for block, tex in pairs:
            score = score_pair(
                block,
                tex,
                source_aliases=aliases,
                lean_target_aliases=lean_target_aliases,
                unresolved_lean_targets=unresolved_lean_targets,
            )
            if not score.extra_uses and not score.extra_lean and not score.extra_bprefs:
                continue
            found = True
            kind = "prose" if block.kind == "prose" else "node"
            extras: list[str] = []
            if score.extra_uses:
                extras.append(f"extra uses {sorted(score.extra_uses)!r}")
            if score.extra_bprefs:
                extras.append(f"extra bprefs {sorted(score.extra_bprefs)!r}")
            if score.extra_lean:
                extras.append(f"extra lean {sorted(score.extra_lean)!r}")
            print(
                f"{path}:{block.start_line}: local {kind} metadata is not source-authorized "
                f"by the adjacent TeX witness ({'; '.join(extras)})"
            )

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
