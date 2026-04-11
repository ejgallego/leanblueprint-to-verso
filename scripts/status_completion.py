#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import (  # noqa: E402
    lean_file_to_module,
    load_config,
    resolve_project_root,
)
from check_blueprint_node_kinds import audit_file as audit_node_kinds  # noqa: E402
from check_lt_similarity import paired_blocks, score_pair  # noqa: E402
from check_verso_math_delimiters import suspicious_math_syntax  # noqa: E402
from lt_audit import (  # noqa: E402
    chapter_build_command,
    collect_native_warning_records,
    effective_native_warnings,
    native_warning_check_ok,
    run_step,
)


STATE_SORT_KEY = {
    "untracked": 0,
    "unpaired": 1,
    "paired": 2,
    "lt-audited": 3,
    "metadata-clean": 4,
    "done": 5,
    "non-port": 6,
}
STATE_LABELS = (
    "done",
    "metadata-clean",
    "lt-audited",
    "paired",
    "unpaired",
    "non-port",
    "untracked",
)


@dataclass(frozen=True)
class CompletionStatus:
    relative_path: Path
    scope: str
    state: str
    pair_count: int
    low_similarity: int
    metadata_dirty: int
    label_issues: int
    node_kind_issues: int
    math_issues: int
    build_checked: bool
    build_ok: bool | None
    reasons: tuple[str, ...]


def chapter_root_paths(project_root: Path, chapter_root: str) -> list[Path]:
    root = project_root / chapter_root
    if not root.exists():
        return []
    return sorted(path.relative_to(project_root) for path in root.rglob("*.lean"))


def selected_paths(
    project_root: Path,
    *,
    chapter_root: str,
    lt_default_chapters: tuple[str, ...],
    non_port_chapters: tuple[str, ...],
    raw_paths: list[Path],
) -> list[Path]:
    if raw_paths:
        selected: list[Path] = []
        for raw_path in raw_paths:
            if raw_path.is_absolute():
                selected.append(raw_path.resolve().relative_to(project_root))
            else:
                selected.append(raw_path)
        return sorted(dict.fromkeys(selected))

    combined = (
        chapter_root_paths(project_root, chapter_root)
        + [Path(path) for path in lt_default_chapters]
        + [Path(path) for path in non_port_chapters]
    )
    return sorted(dict.fromkeys(combined))


def metadata_dirty_count(scores: list[object]) -> int:
    return sum(
        bool(
            score.exact_drift_count
            or score.ref_hint_count
            or score.placeholder_lean_attachments
        )
        for score in scores
    )


def label_issue_count(scores: list[object]) -> int:
    return sum(bool(score.label_regrounding_candidates) for score in scores)


def build_status(
    project_root: Path,
    path: Path,
    *,
    formalization_path: str,
    native_warnings: bool,
    native_warnings_scope: str,
) -> tuple[bool | None, tuple[str, ...]]:
    module = lean_file_to_module(project_root, path)
    if module is None:
        return None, ("could not infer a Lake module name for build checking",)

    result = run_step(
        project_root,
        "chapter build",
        chapter_build_command(module),
    )
    if not native_warnings:
        if result.ok:
            return True, ()
        detail = result.stderr or result.stdout or "lake build failed"
        return False, (detail.splitlines()[0],)

    warning_records = collect_native_warning_records(project_root, formalization_path, result)
    if native_warning_check_ok(result, warning_records, native_warnings_scope):
        return True, ()

    if not result.ok:
        detail = result.stderr or result.stdout or "lake build failed"
        return False, (detail.splitlines()[0],)

    failing_count = sum(
        native_warnings_scope == "all" or record.owner == "consumer"
        for record in warning_records
    )
    return False, (
        f"{failing_count} native warning(s) fail under {native_warnings_scope} scope",
    )


def classify_direct_port(
    project_root: Path,
    config,
    relative_path: Path,
    *,
    warn_below: float,
    build: bool,
    native_warnings: bool,
    native_warnings_scope: str,
) -> CompletionStatus:
    path = project_root / relative_path
    if not path.exists():
        return CompletionStatus(
            relative_path=relative_path,
            scope="direct-port",
            state="unpaired",
            pair_count=0,
            low_similarity=0,
            metadata_dirty=0,
            label_issues=0,
            node_kind_issues=0,
            math_issues=0,
            build_checked=False,
            build_ok=None,
            reasons=("missing file",),
        )

    pairs, pair_errors = paired_blocks(path)
    if pair_errors or not pairs:
        reasons = [f"source-pair errors={len(pair_errors)}"] if pair_errors else ["no paired blocks"]
        return CompletionStatus(
            relative_path=relative_path,
            scope="direct-port",
            state="unpaired",
            pair_count=len(pairs),
            low_similarity=0,
            metadata_dirty=0,
            label_issues=0,
            node_kind_issues=0,
            math_issues=0,
            build_checked=False,
            build_ok=None,
            reasons=tuple(reasons),
        )

    scores = [score_pair(block, tex) for block, tex in pairs]
    low_similarity = sum(score.primary_ratio < warn_below for score in scores)
    node_kind_issues = len(audit_node_kinds(path, tex_to_verso=dict(config.lt_node_kind_pairs)))
    math_issues = len(suspicious_math_syntax(path))
    metadata_dirty = metadata_dirty_count(scores)
    label_issues = label_issue_count(scores)

    paired_reasons: list[str] = []
    if low_similarity:
        paired_reasons.append(f"low-similarity blocks={low_similarity}")
    if node_kind_issues:
        paired_reasons.append(f"node-kind issues={node_kind_issues}")
    if math_issues:
        paired_reasons.append(f"math issues={math_issues}")
    if paired_reasons:
        return CompletionStatus(
            relative_path=relative_path,
            scope="direct-port",
            state="paired",
            pair_count=len(pairs),
            low_similarity=low_similarity,
            metadata_dirty=metadata_dirty,
            label_issues=label_issues,
            node_kind_issues=node_kind_issues,
            math_issues=math_issues,
            build_checked=False,
            build_ok=None,
            reasons=tuple(paired_reasons),
        )

    if metadata_dirty:
        reasons = [f"metadata-cleanup blocks={metadata_dirty}"]
        if label_issues:
            reasons.append(f"label-grounding blocks={label_issues}")
        return CompletionStatus(
            relative_path=relative_path,
            scope="direct-port",
            state="lt-audited",
            pair_count=len(pairs),
            low_similarity=low_similarity,
            metadata_dirty=metadata_dirty,
            label_issues=label_issues,
            node_kind_issues=node_kind_issues,
            math_issues=math_issues,
            build_checked=False,
            build_ok=None,
            reasons=tuple(reasons),
        )

    if not build:
        return CompletionStatus(
            relative_path=relative_path,
            scope="direct-port",
            state="metadata-clean",
            pair_count=len(pairs),
            low_similarity=0,
            metadata_dirty=0,
            label_issues=0,
            node_kind_issues=0,
            math_issues=0,
            build_checked=False,
            build_ok=None,
            reasons=("build not checked; rerun with --build for final completion",),
        )

    build_ok, build_reasons = build_status(
        project_root,
        path,
        formalization_path=config.formalization_path,
        native_warnings=native_warnings,
        native_warnings_scope=native_warnings_scope,
    )
    state = "done" if build_ok else "metadata-clean"
    return CompletionStatus(
        relative_path=relative_path,
        scope="direct-port",
        state=state,
        pair_count=len(pairs),
        low_similarity=0,
        metadata_dirty=0,
        label_issues=0,
        node_kind_issues=0,
        math_issues=0,
        build_checked=True,
        build_ok=build_ok,
        reasons=build_reasons,
    )


def classify_chapter(
    project_root: Path,
    config,
    relative_path: Path,
    *,
    warn_below: float,
    build: bool,
    native_warnings: bool,
    native_warnings_scope: str,
    direct_port_paths: set[Path],
    non_port_paths: set[Path],
) -> CompletionStatus:
    if relative_path in non_port_paths:
        return CompletionStatus(
            relative_path=relative_path,
            scope="non-port",
            state="non-port",
            pair_count=0,
            low_similarity=0,
            metadata_dirty=0,
            label_issues=0,
            node_kind_issues=0,
            math_issues=0,
            build_checked=False,
            build_ok=None,
            reasons=("excluded by harness.non_port_chapters",),
        )

    if relative_path not in direct_port_paths:
        return CompletionStatus(
            relative_path=relative_path,
            scope="untracked",
            state="untracked",
            pair_count=0,
            low_similarity=0,
            metadata_dirty=0,
            label_issues=0,
            node_kind_issues=0,
            math_issues=0,
            build_checked=False,
            build_ok=None,
            reasons=("present under chapter_root but not listed in lt.default_chapters or harness.non_port_chapters",),
        )

    return classify_direct_port(
        project_root,
        config,
        relative_path,
        warn_below=warn_below,
        build=build,
        native_warnings=native_warnings,
        native_warnings_scope=native_warnings_scope,
    )


def print_status(status: CompletionStatus) -> None:
    print(f"[{status.state}] {status.relative_path}")
    print(f"  scope: {status.scope}")
    details = (
        f"pairs={status.pair_count} low={status.low_similarity} "
        f"metadata={status.metadata_dirty} labels={status.label_issues} "
        f"node_kinds={status.node_kind_issues} math={status.math_issues}"
    )
    print(f"  metrics: {details}")
    if status.build_checked:
        build_label = "ok" if status.build_ok else "needs-attention"
        print(f"  build: {build_label}")
    for reason in status.reasons:
        print(f"  reason: {reason}")


def report_complete(statuses: list[CompletionStatus]) -> bool:
    for status in statuses:
        if status.state in {"untracked", "unpaired", "paired", "lt-audited", "metadata-clean"}:
            return False
    return True


def sort_key(status: CompletionStatus) -> tuple[int, str]:
    return (STATE_SORT_KEY[status.state], str(status.relative_path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Repo-level completion dashboard for chapter scope and LT progress. "
            "This classifies configured direct-port chapters as unpaired, paired, "
            "lt-audited, metadata-clean, or done, and also reports non-port and "
            "untracked chapter files under chapter_root."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help=(
            "Optional specific chapter files. Defaults to every .lean file under chapter_root "
            "together with configured lt.default_chapters and harness.non_port_chapters."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--warn-below",
        type=float,
        default=0.70,
        help="Similarity warning threshold used to separate paired from LT-audited chapters.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Also run focused chapter builds and upgrade metadata-clean chapters to done when they pass.",
    )
    native_warning_group = parser.add_mutually_exclusive_group()
    native_warning_group.add_argument(
        "--native-warnings",
        dest="native_warnings",
        action="store_true",
        help="When combined with --build, apply the repo's native warning failure policy to chapter builds.",
    )
    native_warning_group.add_argument(
        "--no-native-warnings",
        dest="native_warnings",
        action="store_false",
        help="When combined with --build, suppress native warning failure even if enabled in verso-harness.toml.",
    )
    parser.add_argument(
        "--native-warnings-scope",
        choices=("consumer", "all"),
        default="consumer",
        help="When build checks use native warning failure, fail on consumer warnings only or on all warnings.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Return exit code 1 unless every selected direct-port chapter is done and no selected chapters are untracked.",
    )
    parser.set_defaults(native_warnings=None)
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    config = load_config(project_root)
    paths = selected_paths(
        project_root,
        chapter_root=config.chapter_root,
        lt_default_chapters=config.lt_default_chapters,
        non_port_chapters=config.non_port_chapters,
        raw_paths=args.paths,
    )
    native_warnings = effective_native_warnings(config.native_warnings, args.native_warnings)

    if not paths:
        print("no chapter files selected for completion report", file=sys.stderr)
        return 2

    direct_port_paths = {Path(path) for path in config.lt_default_chapters}
    non_port_paths = {Path(path) for path in config.non_port_chapters}
    statuses = [
        classify_chapter(
            project_root,
            config,
            relative_path,
            warn_below=args.warn_below,
            build=args.build,
            native_warnings=native_warnings,
            native_warnings_scope=args.native_warnings_scope,
            direct_port_paths=direct_port_paths,
            non_port_paths=non_port_paths,
        )
        for relative_path in paths
    ]

    counts = Counter(status.state for status in statuses)
    complete = report_complete(statuses)

    print(f"project root: {project_root}")
    print(f"chapter_root: {config.chapter_root}")
    print(f"build_checked: {'yes' if args.build else 'no'}")
    if args.build:
        print(
            "native_warnings: "
            f"{'on' if native_warnings else 'off'} (scope={args.native_warnings_scope})"
        )
    print("summary:")
    for state in STATE_LABELS:
        print(f"  {state}: {counts.get(state, 0)}")
    print(f"  complete: {'yes' if complete else 'no'}")

    print("chapters:")
    for status in sorted(statuses, key=sort_key):
        print_status(status)

    if args.require_complete and not complete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
