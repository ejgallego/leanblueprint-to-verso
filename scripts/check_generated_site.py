#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ASSET_DIRS = {"-verso-data", "-verso-search"}
ASSET_REF_RE = re.compile(
    r"(?P<ref>(?:(?:\./|\.\./)*)-(?:verso-data|verso-search)/[A-Za-z0-9._~!$&()*+,;=:@/%-]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate generated Verso Blueprint site artifacts."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=Path("_out/site/html-multi"),
        help="Generated html-multi site directory, relative to project root by default.",
    )
    return parser.parse_args()


def project_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def site_relative_asset_ref(raw_ref: str) -> Path | None:
    ref = raw_ref.split("#", 1)[0].split("?", 1)[0].rstrip(".,;:")
    parts = PurePosixPath(ref).parts
    for index, part in enumerate(parts):
        if part in ASSET_DIRS:
            tail = parts[index:]
            if ".." in tail or len(tail) < 2:
                return None
            return Path(*tail)
    return None


def referenced_assets(site_dir: Path) -> dict[Path, set[Path]]:
    refs: dict[Path, set[Path]] = {}
    for html_path in sorted(site_dir.rglob("*.html")):
        try:
            text = html_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = html_path.read_text(encoding="utf-8", errors="replace")
        for match in ASSET_REF_RE.finditer(text):
            ref = site_relative_asset_ref(match.group("ref"))
            if ref is not None:
                refs.setdefault(ref, set()).add(html_path)
    return refs


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def preview_entries(data: Any) -> list[Any] | None:
    if isinstance(data, dict) and isinstance(data.get("previews"), list):
        return data["previews"]
    return None


def html_cache_entries(data: Any) -> list[Any] | None:
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    return None


def has_rendered_preview_entries(entries: list[Any] | None, *, empty_ok: bool = False) -> bool:
    if entries is None:
        return False
    if empty_ok and not entries:
        return True
    return any(isinstance(entry, dict) and isinstance(entry.get("html"), str) for entry in entries)


def preview_data_roles(data_dir: Path) -> tuple[Path | None, Path | None, list[Path]]:
    semantic_manifest: Path | None = None
    rendered_cache: Path | None = None
    unreadable: list[Path] = []
    for json_path in sorted(data_dir.glob("*.json")):
        data = load_json(json_path)
        if data is None:
            unreadable.append(json_path)
            continue
        previews = preview_entries(data)
        entries = html_cache_entries(data)
        if previews is not None and semantic_manifest is None:
            semantic_manifest = json_path
        if has_rendered_preview_entries(entries, empty_ok=True) and rendered_cache is None:
            rendered_cache = json_path
        if has_rendered_preview_entries(previews, empty_ok=True) and rendered_cache is None:
            rendered_cache = json_path
    return semantic_manifest, rendered_cache, unreadable


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    site_dir = project_path(project_root, args.site_dir).resolve()
    errors: list[str] = []

    if not site_dir.is_dir():
        errors.append(f"generated site directory is missing: {display_path(site_dir, project_root)}")
    else:
        index_path = site_dir / "index.html"
        if not index_path.is_file():
            errors.append(f"generated site index is missing: {display_path(index_path, project_root)}")

        refs = referenced_assets(site_dir)
        for ref, pages in sorted(refs.items(), key=lambda item: str(item[0])):
            target = site_dir / ref
            if not target.is_file():
                page_list = ", ".join(
                    display_path(page, project_root) for page in sorted(pages)[:3]
                )
                extra = "" if len(pages) <= 3 else f" and {len(pages) - 3} more"
                errors.append(
                    "generated site references missing asset "
                    f"{display_path(target, project_root)} from {page_list}{extra}"
                )

        data_dir = site_dir / "-verso-data"
        if not data_dir.is_dir():
            errors.append(f"generated site data directory is missing: {display_path(data_dir, project_root)}")
        else:
            semantic_manifest, rendered_cache, unreadable = preview_data_roles(data_dir)
            for path in unreadable:
                errors.append(f"generated site JSON is unreadable: {display_path(path, project_root)}")
            if semantic_manifest is None:
                errors.append(
                    "generated site is missing semantic preview data "
                    "(expected a JSON file in -verso-data with a top-level previews array)"
                )
            if rendered_cache is None:
                errors.append(
                    "generated site is missing rendered preview data "
                    "(expected preview entries with rendered HTML, either in a cache entries array "
                    "or in a legacy previews array)"
                )

    if errors:
        for error in errors:
            print(f"[generated-site] {error}", file=sys.stderr)
        return 1

    print(f"[generated-site] ok: {display_path(site_dir, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
