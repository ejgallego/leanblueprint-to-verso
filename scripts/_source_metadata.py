from __future__ import annotations

from pathlib import Path
import re


SOURCE_NODE_RE = re.compile(
    r"\\begin\{(?P<kind>theorem|lemma|corollary|definition|proposition)\*?\}"
    r".*?"
    r"\\end\{(?P=kind)\*?\}",
    re.DOTALL,
)
TEX_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
TEX_LABEL_RE = re.compile(r"\\label\{([^{}]*)\}")
TEX_LEAN_RE = re.compile(r"\\lean\{([^{}]*)\}")


def strip_tex_comments(text: str) -> str:
    return "\n".join(TEX_COMMENT_RE.sub("", line) for line in text.splitlines())


def split_csv_items(text: str) -> set[str]:
    return {item.strip() for item in text.split(",") if item.strip()}


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
            labels = {
                label.strip()
                for label_match in TEX_LABEL_RE.finditer(node)
                if (label := label_match.group(1).strip())
            }
            declarations: set[str] = set()
            for lean_match in TEX_LEAN_RE.finditer(node):
                declarations.update(split_csv_items(lean_match.group(1)))
            for declaration in declarations:
                aliases.setdefault(declaration, set()).update(labels)
    return aliases


def resolve_source_targets(
    source_targets: set[str],
    local_targets: set[str],
    aliases: dict[str, set[str]],
) -> set[str]:
    """Resolve source declaration references to their authoritative Blueprint labels."""
    resolved: set[str] = set()
    for target in source_targets:
        target_aliases = aliases.get(target, set())
        matching_aliases = target_aliases & local_targets
        if matching_aliases:
            resolved.update(matching_aliases)
        elif len(target_aliases) == 1:
            resolved.update(target_aliases)
        else:
            resolved.add(target)
    return resolved
