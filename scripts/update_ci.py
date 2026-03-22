#!/usr/bin/env python3

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path


TRACKED_FILES = [
    Path("scripts/ci-pages.sh"),
    Path(".github/workflows/blueprint.yml"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh helper-owned CI files in a host repo."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files.",
    )
    return parser.parse_args()


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    args = parse_args()
    helper_root = Path(__file__).resolve().parents[1]
    template_root = helper_root / "templates" / "repo-root"
    project_root = args.project_root.resolve()

    changed = 0
    unchanged = 0

    for relative in TRACKED_FILES:
        source = template_root / relative
        target = project_root / relative
        source_text = source.read_text(encoding="utf-8")
        target_text = target.read_text(encoding="utf-8") if target.exists() else None

        if target_text == source_text:
            unchanged += 1
            print(f"unchanged {relative}")
            continue

        changed += 1
        print(f"update    {relative}")
        if args.dry_run:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_text, encoding="utf-8")
        if target.name == "ci-pages.sh":
            ensure_executable(target)

    print(f"changed: {changed}")
    print(f"unchanged: {unchanged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
