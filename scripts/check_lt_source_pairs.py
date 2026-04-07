#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import resolve_chapter_paths, resolve_project_root  # noqa: E402


@dataclass
class Block:
    kind: str
    start_line: int
    end_line: int
    header: str
    lines: list[str]

    def preview(self) -> str:
        for line in self.lines:
            stripped = line.strip()
            if stripped:
                return stripped
        return self.header.strip()


def parse_blocks(path: Path) -> list[Block]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[Block] = []

    in_doc = False
    fence_start = -1
    fence_info = ""
    fence_lines: list[str] = []
    node_start = -1
    node_header = ""
    node_lines: list[str] = []
    prose_start = -1
    prose_lines: list[str] = []

    def flush_prose(end_line: int) -> None:
        nonlocal prose_start, prose_lines
        if prose_start == -1:
            return
        blocks.append(
            Block(
                kind="prose",
                start_line=prose_start,
                end_line=end_line,
                header=prose_lines[0],
                lines=prose_lines.copy(),
            )
        )
        prose_start = -1
        prose_lines = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not in_doc:
            if line.lstrip().startswith("#doc") and "=>" in line:
                in_doc = True
            continue

        if fence_start != -1:
            fence_lines.append(line)
            if stripped.startswith("```"):
                kind = "tex" if fence_info.startswith("tex") else "code"
                blocks.append(
                    Block(
                        kind=kind,
                        start_line=fence_start,
                        end_line=idx,
                        header=fence_info,
                        lines=fence_lines.copy(),
                    )
                )
                fence_start = -1
                fence_info = ""
                fence_lines = []
            continue

        if node_start != -1:
            node_lines.append(line)
            if stripped == ":::":
                blocks.append(
                    Block(
                        kind="verso",
                        start_line=node_start,
                        end_line=idx,
                        header=node_header,
                        lines=node_lines.copy(),
                    )
                )
                node_start = -1
                node_header = ""
                node_lines = []
            continue

        if stripped.startswith("```"):
            flush_prose(idx - 1)
            fence_start = idx
            fence_info = stripped[3:].strip()
            fence_lines = [line]
            continue

        if stripped.startswith(":::") and stripped != ":::":
            flush_prose(idx - 1)
            node_start = idx
            node_header = stripped
            node_lines = [line]
            continue

        if stripped.startswith("#"):
            flush_prose(idx - 1)
            blocks.append(Block("heading", idx, idx, stripped, [line]))
            continue

        if not stripped or stripped.startswith("--"):
            flush_prose(idx - 1)
            continue

        if prose_start == -1:
            prose_start = idx
            prose_lines = [line]
        else:
            prose_lines.append(line)

    flush_prose(len(lines))
    return blocks


def block_neighbors(blocks: list[Block], index: int) -> tuple[Block | None, Block | None]:
    previous = blocks[index - 1] if index > 0 else None
    following = blocks[index + 1] if index + 1 < len(blocks) else None
    return previous, following


def audit_file(path: Path) -> list[str]:
    blocks = parse_blocks(path)
    errors: list[str] = []

    for index, block in enumerate(blocks):
        if block.kind not in {"prose", "verso"}:
            continue
        if block.kind == "verso" and block.header.startswith(":::group "):
            continue
        _, following = block_neighbors(blocks, index)
        if following and following.kind == "tex":
            continue

        block_kind = "prose block" if block.kind == "prose" else "informal node"
        errors.append(
            f"{path}:{block.start_line}: {block_kind} is missing an adjacent ```tex block: "
            f"{block.preview()}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that every translated informal block has an adjacent tex source block. "
            "LT is the canonical repository term; LF and TF are accepted aliases."
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
    paths = resolve_chapter_paths(project_root, args.paths)

    if not paths:
        print("no chapter files selected for LT source-pair audit", file=sys.stderr)
        return 2

    missing = [path for path in paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing file: {path}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for path in paths:
        failures.extend(audit_file(path))

    if failures:
        print("LT source-pair audit failed:")
        for failure in failures:
            print(f"- {failure}")
        print(f"\n{len(failures)} block(s) need adjacent tex source blocks.")
        return 1

    print(f"LT source-pair audit passed for {len(paths)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
