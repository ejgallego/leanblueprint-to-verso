#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_source_pairs import Block, parse_blocks  # noqa: E402


SECTION_COMMAND_RE = re.compile(r"\\(section|subsection|subsubsection)\b")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
VERSO_CODE_RE = re.compile(r"`([^`]+)`")
VERSO_INLINE_MATH_RE = re.compile(r"\$`([^`]*)`")
TEX_TEXORPDF_RE = re.compile(r"\\texorpdfstring\{([^{}]*)\}\{([^{}]*)\}")
TEX_MATH_RE = re.compile(r"\$([^$]*)\$")
TEX_CMD_ARG_RE = re.compile(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}")
TEX_CMD_RE = re.compile(r"\\([A-Za-z]+)")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

SECTION_LEVELS = {
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
}

OPERATOR_REPLACEMENTS = {
    r"\geq": " geq ",
    r"\leq": " leq ",
    r"\to": " to ",
    r"\times": " times ",
    ">=": " geq ",
    "<=": " leq ",
    "→": " to ",
    "×": " times ",
}


@dataclass(frozen=True)
class HeadingCommand:
    kind: str
    title: str
    line: int

    @property
    def level(self) -> int:
        return SECTION_LEVELS[self.kind]


def block_body(block: Block) -> str:
    if block.kind == "tex":
        return "\n".join(block.lines[1:-1])
    return "\n".join(block.lines)


def extract_braced(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    out: list[str] = []
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            if depth > 0:
                out.append(char)
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return "".join(out), index + 1
            out.append(char)
            continue
        out.append(char)
    return None, start


def extract_tex_section_commands(block: Block) -> list[HeadingCommand]:
    commands: list[HeadingCommand] = []
    for offset, raw_line in enumerate(block.lines[1:-1], start=1):
        line = raw_line.strip()
        if not line:
            continue
        search_from = 0
        while True:
            match = SECTION_COMMAND_RE.search(line, search_from)
            if match is None:
                break
            position = match.end()
            if position < len(line) and line[position] == "[":
                _, position = extract_braced(line, position)  # harmless fallback if malformed
            while position < len(line) and line[position].isspace():
                position += 1
            title, end = extract_braced(line, position)
            if title is None:
                break
            commands.append(
                HeadingCommand(
                    kind=match.group(1),
                    title=title,
                    line=block.start_line + offset,
                )
            )
            search_from = end
    return commands


def heading_level(header: str) -> int:
    stripped = header.strip()
    return len(stripped) - len(stripped.lstrip("#"))


def heading_text(header: str) -> str:
    stripped = header.strip()
    return stripped.lstrip("#").strip()


def normalize_common(text: str) -> str:
    lowered = text.lower()
    for source, target in OPERATOR_REPLACEMENTS.items():
        lowered = lowered.replace(source, target)
    lowered = NON_ALNUM_RE.sub(" ", lowered)
    normalized = " ".join(lowered.split())
    if normalized.startswith("the "):
        return normalized[4:]
    return normalized


def normalize_verso_heading(text: str) -> str:
    text = MARKDOWN_LINK_RE.sub(r" \1 ", text)
    text = VERSO_INLINE_MATH_RE.sub(r" \1 ", text)
    text = VERSO_CODE_RE.sub(r" \1 ", text)
    return normalize_common(text)


def normalize_tex_heading(text: str) -> str:
    while True:
        updated = TEX_TEXORPDF_RE.sub(r" \2 ", text)
        if updated == text:
            break
        text = updated
    text = TEX_MATH_RE.sub(r" \1 ", text)
    text = TEX_CMD_ARG_RE.sub(r" \1 ", text)
    text = TEX_CMD_RE.sub(r" \1 ", text)
    return normalize_common(text)


def audit_file(path: Path) -> list[str]:
    blocks = parse_blocks(path)
    errors: list[str] = []
    heading_indexes = [index for index, block in enumerate(blocks) if block.kind == "heading"]

    for position, index in enumerate(heading_indexes):
        block = blocks[index]
        next_heading = heading_indexes[position + 1] if position + 1 < len(heading_indexes) else len(blocks)
        section_commands: list[HeadingCommand] = []
        for inner in blocks[index + 1:next_heading]:
            if inner.kind != "tex":
                continue
            section_commands.extend(extract_tex_section_commands(inner))

        if not section_commands:
            continue

        first = section_commands[0]
        actual_level = heading_level(block.header)
        actual_text = heading_text(block.header)
        if actual_level != first.level:
            expected_hashes = "#" * first.level
            errors.append(
                f"{path}:{block.start_line}: heading level {actual_level} does not match "
                f"adjacent TeX {first.kind}; use `{expected_hashes} {actual_text}`"
            )

        if normalize_verso_heading(actual_text) != normalize_tex_heading(first.title):
            errors.append(
                f"{path}:{block.start_line}: heading text `{actual_text}` does not match "
                f"adjacent TeX {first.kind} title `{first.title}`"
            )

        for extra in section_commands[1:]:
            expected_hashes = "#" * extra.level
            errors.append(
                f"{path}:{extra.line}: TeX {extra.kind} `{extra.title}` appears before the next Lean heading; "
                f"add a matching `{expected_hashes} ...` heading and localize the witness more tightly"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that Lean heading levels and titles match adjacent TeX "
            "section/subsection/subsubsection structure."
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
    load_config(project_root)
    paths = resolve_chapter_paths(project_root, args.paths)

    if not paths:
        print("no chapter files selected for heading-structure audit", file=sys.stderr)
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
        print("Blueprint heading structure audit failed:")
        for failure in failures:
            print(f"- {failure}")
        print(f"\n{len(failures)} heading issue(s) found.")
        return 1

    print(f"Blueprint heading structure audit passed for {len(paths)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
