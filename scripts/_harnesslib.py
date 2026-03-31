#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_PATTERN = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\s+where", re.M)


def resolve_project_root(raw: Path | None) -> Path:
    return (raw or Path.cwd()).resolve()


def find_package_name(project_root: Path) -> str | None:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None
    match = PACKAGE_PATTERN.search(lakefile.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def require_package_name(project_root: Path, package_name: str | None) -> str:
    inferred = package_name or find_package_name(project_root)
    if inferred is None:
        raise SystemExit(
            "could not infer the blueprint package name from lakefile.lean; "
            "pass --package-name explicitly"
        )
    return inferred


def resolve_input_paths(project_root: Path, raw_paths: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for raw_path in raw_paths:
        if raw_path.is_absolute():
            paths.append(raw_path.resolve())
        else:
            paths.append((project_root / raw_path).resolve())
    return paths


def default_chapter_paths(project_root: Path, package_name: str | None) -> list[Path]:
    package = require_package_name(project_root, package_name)
    chapter_dir = project_root / package / "Chapters"
    if not chapter_dir.exists():
        return []
    return sorted(path.resolve() for path in chapter_dir.glob("*.lean"))


def filter_paths(
    project_root: Path,
    paths: list[Path],
    exclude_patterns: list[str],
) -> list[Path]:
    if not exclude_patterns:
        return paths

    filtered: list[Path] = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(project_root)
        except ValueError:
            relative = None

        excluded = False
        for pattern in exclude_patterns:
            if relative is not None and relative.match(pattern):
                excluded = True
                break
            if path.name == pattern:
                excluded = True
                break

        if not excluded:
            filtered.append(path)

    return filtered


def resolve_chapter_paths(
    project_root: Path,
    raw_paths: list[Path],
    package_name: str | None,
    exclude_patterns: list[str],
) -> list[Path]:
    paths = (
        resolve_input_paths(project_root, raw_paths)
        if raw_paths
        else default_chapter_paths(project_root, package_name)
    )
    return filter_paths(project_root, paths, exclude_patterns)


def lean_file_to_module(project_root: Path, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(project_root)
    except ValueError:
        return None

    if relative.suffix != ".lean":
        return None

    return ".".join(relative.with_suffix("").parts)
