#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path


PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")
PACKAGE_PATTERN = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\s+where", re.M)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that a host repo has the expected Verso harness files."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    return parser.parse_args()


def find_package_name(lakefile: Path) -> str | None:
    match = PACKAGE_PATTERN.search(lakefile.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def unresolved_placeholders(project_root: Path, paths: list[Path]) -> list[Path]:
    bad: list[Path] = []
    for relative in paths:
        path = project_root / relative
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER_PATTERN.search(text):
            bad.append(relative)
    return bad


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()

    missing: list[Path] = []
    required = [
        Path("lakefile.lean"),
        Path("lean-toolchain"),
        Path("BlueprintMain.lean"),
        Path("scripts/ci-pages.sh"),
        Path(".github/workflows/blueprint.yml"),
    ]

    for relative in required:
        if not (project_root / relative).exists():
            missing.append(relative)

    package_name = None
    chapter_paths: list[Path] = []
    lakefile = project_root / "lakefile.lean"
    if lakefile.exists():
        package_name = find_package_name(lakefile)
        if package_name is None:
            missing.append(Path("<package declaration in lakefile.lean>"))
        else:
            for relative in [Path(f"{package_name}.lean"), Path(package_name) / "TeXPrelude.lean"]:
                if not (project_root / relative).exists():
                    missing.append(relative)
            chapter_dir = project_root / package_name / "Chapters"
            if chapter_dir.exists():
                chapter_paths = sorted(
                    path.relative_to(project_root) for path in chapter_dir.glob("*.lean")
                )
            if not chapter_paths:
                missing.append(Path(package_name) / "Chapters" / "<at least one .lean file>")

    placeholder_targets = required.copy()
    if package_name is not None:
        placeholder_targets.extend(
            [Path(f"{package_name}.lean"), Path(package_name) / "TeXPrelude.lean"]
        )
    placeholder_targets.extend(chapter_paths)
    placeholder_paths = unresolved_placeholders(project_root, placeholder_targets)

    script_path = project_root / "scripts" / "ci-pages.sh"
    script_executable = (
        script_path.exists() and bool(script_path.stat().st_mode & stat.S_IXUSR)
    )

    if missing or placeholder_paths or not script_executable:
        if missing:
            print("missing:")
            for path in missing:
                print(f"  {path}")
        if placeholder_paths:
            print("unresolved placeholders:")
            for path in placeholder_paths:
                print(f"  {path}")
        if script_path.exists() and not script_executable:
            print("ci-pages.sh is not executable")
        return 1

    print(f"project root: {project_root}")
    print(f"package: {package_name}")
    print("status: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
