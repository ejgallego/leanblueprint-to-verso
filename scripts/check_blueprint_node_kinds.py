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
from check_lt_source_pairs import Block, parse_blocks  # noqa: E402


VERSO_KIND_RE = re.compile(r"^:::([A-Za-z_][A-Za-z0-9_]*)\b")


def block_body(block: Block) -> str:
    if block.kind in {"verso", "tex"}:
        return "\n".join(block.lines[1:-1])
    return "\n".join(block.lines)


def extract_verso_kind(header: str) -> str | None:
    match = VERSO_KIND_RE.match(header.strip())
    return match.group(1) if match else None


def extract_tex_env_kinds(text: str, tex_to_verso: dict[str, str]) -> list[str]:
    if not tex_to_verso:
        return []
    env_pattern = "|".join(re.escape(kind) for kind in tex_to_verso)
    tex_env_re = re.compile(r"\\begin\{(" + env_pattern + r")\}")
    return tex_env_re.findall(text)


def audit_file(path: Path, *, tex_to_verso: dict[str, str]) -> list[str]:
    blocks = parse_blocks(path)
    errors: list[str] = []
    configured_verso_kinds = set(tex_to_verso.values())

    for index, block in enumerate(blocks):
        if block.kind != "verso":
            continue
        if block.header.startswith(":::group "):
            continue

        verso_kind = extract_verso_kind(block.header)
        if verso_kind is None or verso_kind not in configured_verso_kinds:
            continue

        following = blocks[index + 1] if index + 1 < len(blocks) else None
        if following is None or following.kind != "tex":
            continue

        tex_env_kinds = extract_tex_env_kinds(block_body(following), tex_to_verso)
        if not tex_env_kinds:
            errors.append(
                f"{path}:{block.start_line}: Verso node kind '{verso_kind}' has an adjacent "
                "TeX witness with no configured graph-visible environment; keep prose as prose "
                f"unless the source really gives a theorem/definition/proof-style object: {block.preview()}"
            )
            continue

        tex_kind = tex_env_kinds[0]
        expected_verso_kind = tex_to_verso[tex_kind]
        if verso_kind != expected_verso_kind:
            errors.append(
                f"{path}:{block.start_line}: Verso node kind '{verso_kind}' does not match "
                f"adjacent TeX environment '{tex_kind}'; use ':::{expected_verso_kind}' instead: "
                f"{block.preview()}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that graph-visible Verso node kinds match the adjacent TeX source "
            "environment kind, and that theorem-style wrappers are not used for plain prose."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific Lean chapter files to audit. Defaults to the configured lt.default_chapters.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    config = load_config(project_root)
    paths = resolve_chapter_paths(project_root, args.paths)

    if not paths:
        print("no chapter files selected for node-kind audit", file=sys.stderr)
        return 2

    missing = [path for path in paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing file: {path}", file=sys.stderr)
        return 2

    tex_to_verso = dict(config.lt_node_kind_pairs)
    failures: list[str] = []
    for path in paths:
        failures.extend(audit_file(path, tex_to_verso=tex_to_verso))

    if failures:
        print("Blueprint node kind audit failed:")
        for failure in failures:
            print(f"- {failure}")
        print(f"\n{len(failures)} node kind issue(s) found.")
        return 1

    print(f"Blueprint node kind audit passed for {len(paths)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
