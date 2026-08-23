#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_similarity import (  # noqa: E402
    extract_tex_labels,
    extract_tex_lean,
    paired_blocks,
    score_pair,
    strip_tex_comments,
)


SOURCE_NODE_RE = re.compile(
    r"\\begin\{(?P<kind>theorem|lemma|corollary|definition|proposition)\*?\}"
    r".*?"
    r"\\end\{(?P=kind)\*?\}",
    re.DOTALL,
)


def source_lean_label_aliases(project_root: Path, source_glob: str) -> dict[str, set[str]]:
    """Map source Lean declaration names to Blueprint labels from the same node."""
    aliases: dict[str, set[str]] = {}
    paths = sorted(
        candidate for candidate in project_root.glob(source_glob) if candidate.is_file()
    )
    for path in paths:
        source = strip_tex_comments(path.read_text(encoding="utf-8"))
        for match in SOURCE_NODE_RE.finditer(source):
            node = match.group(0)
            labels = extract_tex_labels(node)
            for declaration in extract_tex_lean(node):
                aliases.setdefault(declaration, set()).update(labels)
    return aliases


def authorized_aliases(items: set[str], aliases: dict[str, set[str]]) -> set[str]:
    return set().union(*(aliases.get(item, set()) for item in items)) if items else set()


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

    found = False
    for path in paths:
        pairs, errors = paired_blocks(path)
        if errors:
            for error in errors:
                print(f"{path}: cannot check source-authorized metadata because {error}")
            found = True
            continue
        for block, tex in pairs:
            score = score_pair(block, tex)
            extra_uses = score.extra_uses - authorized_aliases(score.tex_uses, aliases)
            extra_bprefs = score.extra_bprefs - authorized_aliases(score.tex_refs, aliases)
            if not extra_uses and not score.extra_lean and not extra_bprefs:
                continue
            found = True
            kind = "prose" if block.kind == "prose" else "node"
            extras: list[str] = []
            if extra_uses:
                extras.append(f"extra uses {sorted(extra_uses)!r}")
            if extra_bprefs:
                extras.append(f"extra bprefs {sorted(extra_bprefs)!r}")
            if score.extra_lean:
                extras.append(f"extra lean {sorted(score.extra_lean)!r}")
            print(
                f"{path}:{block.start_line}: local {kind} metadata is not source-authorized "
                f"by the adjacent TeX witness ({'; '.join(extras)})"
            )

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
