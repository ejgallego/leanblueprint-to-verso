#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


CONFIG_FILENAME = "verso-harness.toml"
PACKAGE_PATTERN = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\s+where", re.M)


@dataclass(frozen=True)
class HarnessConfig:
    package_name: str
    chapter_root: str
    tex_source_glob: str
    lt_default_chapters: tuple[str, ...]
    non_port_chapters: tuple[str, ...]


def resolve_project_root(raw: Path | None) -> Path:
    return (raw or Path.cwd()).resolve()


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILENAME


def find_package_name(project_root: Path) -> str | None:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None
    match = PACKAGE_PATTERN.search(lakefile.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def require_relative_path(value: str, field_name: str) -> str:
    if Path(value).is_absolute():
        raise SystemExit(f"{CONFIG_FILENAME}: {field_name} must be a relative path, got: {value!r}")
    return value


def require_string(table: dict[str, object], key: str, field_name: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
    return value


def require_string_list(
    table: dict[str, object],
    key: str,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
    items = tuple(item for item in value)
    if not allow_empty and not items:
        raise SystemExit(f"{CONFIG_FILENAME}: {field_name} must not be empty")
    return items


def load_config(project_root: Path) -> HarnessConfig:
    path = config_path(project_root)
    if not path.exists():
        raise SystemExit(
            f"missing required {CONFIG_FILENAME} at {path}; helper-managed repos must declare "
            "their harness layout explicitly"
        )

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{CONFIG_FILENAME}: invalid TOML: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: expected a top-level table")

    package_name = require_string(data, "package_name", "package_name")
    chapter_root = require_relative_path(
        require_string(data, "chapter_root", "chapter_root"),
        "chapter_root",
    )
    tex_source_glob = require_relative_path(
        require_string(data, "tex_source_glob", "tex_source_glob"),
        "tex_source_glob",
    )

    lt_section = data.get("lt")
    if not isinstance(lt_section, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: missing required [lt] table")
    lt_default_chapters = require_string_list(
        lt_section,
        "default_chapters",
        "lt.default_chapters",
        allow_empty=False,
    )
    for chapter in lt_default_chapters:
        require_relative_path(chapter, "lt.default_chapters")

    harness_section = data.get("harness", {})
    if not isinstance(harness_section, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: invalid [harness] table")
    non_port_chapters = (
        require_string_list(
            harness_section,
            "non_port_chapters",
            "harness.non_port_chapters",
            allow_empty=True,
        )
        if "non_port_chapters" in harness_section
        else ()
    )
    for chapter in non_port_chapters:
        require_relative_path(chapter, "harness.non_port_chapters")

    chapter_root_path = Path(chapter_root)
    for chapter in (*lt_default_chapters, *non_port_chapters):
        chapter_path = Path(chapter)
        if chapter_root_path != Path(".") and chapter_root_path not in chapter_path.parents:
            raise SystemExit(
                f"{CONFIG_FILENAME}: chapter {chapter!r} is not under chapter_root {chapter_root!r}"
            )

    return HarnessConfig(
        package_name=package_name,
        chapter_root=chapter_root,
        tex_source_glob=tex_source_glob,
        lt_default_chapters=lt_default_chapters,
        non_port_chapters=non_port_chapters,
    )


def resolve_input_paths(project_root: Path, raw_paths: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for raw_path in raw_paths:
        if raw_path.is_absolute():
            paths.append(raw_path.resolve())
        else:
            paths.append((project_root / raw_path).resolve())
    return paths


def default_chapter_paths(project_root: Path) -> list[Path]:
    config = load_config(project_root)
    return resolve_input_paths(project_root, [Path(path) for path in config.lt_default_chapters])


def resolve_chapter_paths(project_root: Path, raw_paths: list[Path]) -> list[Path]:
    load_config(project_root)
    return resolve_input_paths(project_root, raw_paths) if raw_paths else default_chapter_paths(project_root)


def lean_file_to_module(project_root: Path, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(project_root)
    except ValueError:
        return None

    if relative.suffix != ".lean":
        return None

    return ".".join(relative.with_suffix("").parts)
