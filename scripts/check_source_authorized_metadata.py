#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from _source_metadata import source_lean_label_aliases  # noqa: E402
from check_lt_similarity import block_body, extract_tex_refs, paired_blocks, score_pair  # noqa: E402
from check_lt_source_freshness import (  # noqa: E402
    canonicalize_tex_source, load_deviations, load_source_documents, witness_fingerprint,
)


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
    lean_target_aliases = dict(config.lt_lean_target_aliases)
    unresolved_lean_targets = set(config.lt_unresolved_lean_targets)
    selected_chapters = {path.relative_to(project_root) for path in paths}
    all_corrections = load_deviations(project_root).references
    for correction in all_corrections:
        if not (project_root / correction.chapter).is_file():
            raise SystemExit(f"reference correction chapter does not exist: {correction.chapter}")
    corrections = tuple(
        correction for correction in all_corrections
        if correction.chapter in selected_chapters
    )
    active_paths = {
        Path(source) for _, sources in config.lt_source_files for source in sources
    }
    active_sources = tuple(
        source
        for source in load_source_documents(project_root, config.tex_source_glob)
        if not active_paths or source.relative_path in active_paths
    ) if corrections else ()
    active_labels = {
        label
        for source in active_sources
        for label in source.node_labels
    }
    source_map = dict(config.lt_source_files)
    used_corrections = set()

    found = False
    for path in paths:
        pairs, errors = paired_blocks(path)
        if errors:
            for error in errors:
                print(f"{path}: cannot check source-authorized metadata because {error}")
            found = True
            continue
        for block, tex in pairs:
            score = score_pair(
                block,
                tex,
                source_aliases=aliases,
                lean_target_aliases=lean_target_aliases,
                unresolved_lean_targets=unresolved_lean_targets,
            )
            extra_bprefs = score.extra_bprefs
            for correction in corrections:
                owned_sources = source_map.get(str(correction.chapter))
                if (correction.chapter == path.relative_to(project_root)
                        and correction.fingerprint == witness_fingerprint(block_body(tex))
                        and correction.source_label in extract_tex_refs(block_body(tex))
                        and correction.source_label not in active_labels
                        and correction.target_label in active_labels
                        and correction.target_label in extra_bprefs
                        and any(
                            canonicalize_tex_source(block_body(tex)) in variant
                            for source in active_sources
                            if owned_sources is None or str(source.relative_path) in owned_sources
                            for variant in source.canonical_variants
                        )):
                    extra_bprefs = extra_bprefs - {correction.target_label}
                    used_corrections.add(correction)
            if not score.extra_uses and not score.extra_lean and not extra_bprefs:
                continue
            found = True
            kind = "prose" if block.kind == "prose" else "node"
            extras: list[str] = []
            if score.extra_uses:
                extras.append(f"extra uses {sorted(score.extra_uses)!r}")
            if extra_bprefs:
                extras.append(f"extra bprefs {sorted(extra_bprefs)!r}")
            if score.extra_lean:
                extras.append(f"extra lean {sorted(score.extra_lean)!r}")
            print(
                f"{path}:{block.start_line}: local {kind} metadata is not source-authorized "
                f"by the adjacent TeX witness ({'; '.join(extras)})"
            )

    for correction in corrections:
        if correction not in used_corrections:
            found = True
            print(
                "unused reference correction "
                f"{correction.chapter} sha256={correction.fingerprint[:12]} "
                f"{correction.source_label} -> {correction.target_label}; "
                "requires the exact current source witness, a stale source label, an active target node, "
                "and the corrected bpref"
            )

    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
