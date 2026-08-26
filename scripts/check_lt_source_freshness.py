#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sys
import tomllib


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_similarity import (  # noqa: E402
    block_body,
    normalize_tex,
    paired_blocks,
    score_pair,
    strip_tex_comments,
)


DEVIATIONS_FILENAME = "lt-source-deviations.toml"
SOURCE_ENV_RE = re.compile(
    r"\\begin\{(?P<kind>theorem|lemma|corollary|definition|proposition)\*?\}"
    r"(?P<body>.*?)"
    r"\\end\{(?P=kind)\*?\}",
    re.DOTALL,
)
SOURCE_LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
PLASTEX_CONDITIONAL_RE = re.compile(
    r"\\ifplastex(?P<plastex>.*?)\\else(?P<latex>.*?)\\fi",
    re.DOTALL,
)


@dataclass(frozen=True)
class SourceNode:
    label: str
    normalized_text: str
    canonical_text: str


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    relative_path: Path
    normalized_text: str
    canonical_text: str
    normalized_variants: tuple[str, ...]
    canonical_variants: tuple[str, ...]
    node_labels: frozenset[str]
    nodes: tuple[SourceNode, ...]


@dataclass(frozen=True)
class WitnessDeviation:
    chapter: Path
    fingerprint: str
    reason: str


@dataclass(frozen=True)
class SourceLabelDeviation:
    source: Path
    label: str
    reason: str


@dataclass(frozen=True)
class SourceDeviations:
    witnesses: tuple[WitnessDeviation, ...] = ()
    source_labels: tuple[SourceLabelDeviation, ...] = ()


@dataclass(frozen=True)
class WitnessFreshness:
    chapter: Path
    line: int
    fingerprint: str
    labels: frozenset[str]
    status: str
    source_paths: tuple[Path, ...]
    reason: str | None = None

    @property
    def needs_review(self) -> bool:
        return self.status in {"metadata-changed", "content-changed", "unmatched"}


@dataclass(frozen=True)
class SourceLabelFreshness:
    chapter: Path
    source: Path
    label: str
    status: str
    reason: str | None = None

    @property
    def needs_review(self) -> bool:
        return self.status == "missing"


@dataclass(frozen=True)
class ChapterFreshness:
    chapter: Path
    witnesses: tuple[WitnessFreshness, ...]
    source_labels: tuple[SourceLabelFreshness, ...]

    @property
    def stale_witness_count(self) -> int:
        return sum(item.needs_review for item in self.witnesses)

    @property
    def missing_source_label_count(self) -> int:
        return sum(item.needs_review for item in self.source_labels)

    @property
    def deviation_count(self) -> int:
        return sum(item.status == "allowed" for item in self.witnesses) + sum(
            item.status == "allowed" for item in self.source_labels
        )

    @property
    def current(self) -> bool:
        return self.stale_witness_count == 0 and self.missing_source_label_count == 0


@dataclass(frozen=True)
class ProjectFreshness:
    chapters: tuple[ChapterFreshness, ...]
    errors: tuple[str, ...]

    def by_chapter(self) -> dict[Path, ChapterFreshness]:
        return {chapter.chapter: chapter for chapter in self.chapters}

    @property
    def needs_review(self) -> bool:
        return bool(self.errors) or any(not chapter.current for chapter in self.chapters)


def witness_fingerprint(text: str) -> str:
    canonical = canonicalize_tex_source(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonicalize_tex_source(text: str) -> str:
    """Normalize layout while retaining TeX structure and Blueprint metadata."""
    return " ".join(strip_tex_comments(text).split())


def tex_source_variants(text: str) -> tuple[str, ...]:
    """Expand simple plasTeX/LaTeX presentation branches for source matching."""
    variants = {text}
    for branch in ("plastex", "latex"):
        candidate = text
        while (match := PLASTEX_CONDITIONAL_RE.search(candidate)) is not None:
            candidate = (
                candidate[: match.start()]
                + match.group(branch)
                + candidate[match.end() :]
            )
        variants.add(candidate)
    return tuple(sorted(variants))


def require_nonempty_string(table: dict[str, object], key: str, context: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{DEVIATIONS_FILENAME}: {context}.{key} must be a non-empty string")
    return value.strip()


def load_deviations(project_root: Path) -> SourceDeviations:
    path = project_root / DEVIATIONS_FILENAME
    if not path.exists():
        return SourceDeviations()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{DEVIATIONS_FILENAME}: invalid TOML: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise SystemExit(f"{DEVIATIONS_FILENAME}: version must be 1")

    raw_witnesses = data.get("witness", [])
    raw_source_labels = data.get("source_label", [])
    if not isinstance(raw_witnesses, list) or not all(
        isinstance(item, dict) for item in raw_witnesses
    ):
        raise SystemExit(f"{DEVIATIONS_FILENAME}: witness must be an array of tables")
    if not isinstance(raw_source_labels, list) or not all(
        isinstance(item, dict) for item in raw_source_labels
    ):
        raise SystemExit(f"{DEVIATIONS_FILENAME}: source_label must be an array of tables")

    witnesses: list[WitnessDeviation] = []
    for index, item in enumerate(raw_witnesses, start=1):
        chapter = Path(require_nonempty_string(item, "chapter", f"witness[{index}]"))
        fingerprint = require_nonempty_string(item, "fingerprint", f"witness[{index}]")
        reason = require_nonempty_string(item, "reason", f"witness[{index}]")
        if chapter.is_absolute():
            raise SystemExit(
                f"{DEVIATIONS_FILENAME}: witness[{index}].chapter must be relative"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise SystemExit(
                f"{DEVIATIONS_FILENAME}: witness[{index}].fingerprint must be a SHA-256 hex digest"
            )
        witnesses.append(WitnessDeviation(chapter, fingerprint, reason))

    source_labels: list[SourceLabelDeviation] = []
    for index, item in enumerate(raw_source_labels, start=1):
        source = Path(require_nonempty_string(item, "source", f"source_label[{index}]"))
        label = require_nonempty_string(item, "label", f"source_label[{index}]")
        reason = require_nonempty_string(item, "reason", f"source_label[{index}]")
        if source.is_absolute():
            raise SystemExit(
                f"{DEVIATIONS_FILENAME}: source_label[{index}].source must be relative"
            )
        source_labels.append(SourceLabelDeviation(source, label, reason))

    return SourceDeviations(tuple(witnesses), tuple(source_labels))


def source_nodes(text: str) -> tuple[SourceNode, ...]:
    nodes: list[SourceNode] = []
    for match in SOURCE_ENV_RE.finditer(strip_tex_comments(text)):
        # Only the environment's first label names the Blueprint node. Later
        # labels can name equations or other anchors nested in the node body.
        label_match = SOURCE_LABEL_RE.search(match.group("body"))
        if label_match is not None:
            nodes.append(
                SourceNode(
                    label=label_match.group(1).strip(),
                    normalized_text=normalize_tex(match.group(0)),
                    canonical_text=canonicalize_tex_source(match.group(0)),
                )
            )
    return tuple(nodes)


def load_source_documents(project_root: Path, source_glob: str) -> tuple[SourceDocument, ...]:
    paths = sorted(path for path in project_root.glob(source_glob) if path.is_file())
    documents: list[SourceDocument] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        nodes = source_nodes(text)
        variants = tex_source_variants(text)
        documents.append(
            SourceDocument(
                path=path,
                relative_path=path.relative_to(project_root),
                normalized_text=normalize_tex(text),
                canonical_text=canonicalize_tex_source(text),
                normalized_variants=tuple(normalize_tex(variant) for variant in variants),
                canonical_variants=tuple(
                    canonicalize_tex_source(variant) for variant in variants
                ),
                node_labels=frozenset(node.label for node in nodes),
                nodes=nodes,
            )
        )
    return tuple(documents)


def audit_project(
    project_root: Path,
    chapter_paths: list[Path] | tuple[Path, ...],
    *,
    source_glob: str,
    source_map: tuple[tuple[str, tuple[str, ...]], ...] = (),
    deviations: SourceDeviations | None = None,
) -> ProjectFreshness:
    deviations = deviations if deviations is not None else load_deviations(project_root)
    sources = load_source_documents(project_root, source_glob)
    errors: list[str] = []
    if not sources:
        errors.append(f"tex_source_glob matched no files: {source_glob}")
    sources_by_path = {source.relative_path: source for source in sources}
    has_explicit_source_map = bool(source_map)
    configured_source_map = {
        Path(chapter): tuple(Path(source) for source in source_paths)
        for chapter, source_paths in source_map
    }
    selected_chapters: set[Path] = set()
    for chapter_path in chapter_paths:
        absolute_chapter = (
            chapter_path if chapter_path.is_absolute() else project_root / chapter_path
        ).resolve()
        try:
            selected_chapters.add(absolute_chapter.relative_to(project_root))
        except ValueError:
            pass
    configured_source_map = {
        chapter: source_paths
        for chapter, source_paths in configured_source_map.items()
        if chapter in selected_chapters
    }
    for chapter, source_paths in configured_source_map.items():
        for source_path in source_paths:
            if source_path not in sources_by_path:
                errors.append(
                    f"lt.source_files maps {chapter} to a file not matched by "
                    f"tex_source_glob: {source_path}"
                )

    witness_deviation_map = {
        (item.chapter, item.fingerprint): item for item in deviations.witnesses
    }
    source_label_deviation_map = {
        (item.source, item.label): item for item in deviations.source_labels
    }
    used_witness_deviations: set[tuple[Path, str]] = set()
    used_source_label_deviations: set[tuple[Path, str]] = set()

    witnesses_by_chapter: dict[Path, list[WitnessFreshness]] = defaultdict(list)
    local_labels_by_chapter: dict[Path, set[str]] = defaultdict(set)
    covered_source_labels_by_chapter: dict[Path, set[str]] = defaultdict(set)
    source_chapter_hits: dict[Path, Counter[Path]] = defaultdict(Counter)

    for chapter_path in chapter_paths:
        absolute_chapter = (
            chapter_path if chapter_path.is_absolute() else project_root / chapter_path
        ).resolve()
        try:
            chapter = absolute_chapter.relative_to(project_root)
        except ValueError:
            errors.append(f"chapter is outside project root: {chapter_path}")
            continue
        if not absolute_chapter.exists():
            errors.append(f"missing chapter: {chapter}")
            continue
        pairs, pair_errors = paired_blocks(absolute_chapter)
        errors.extend(pair_errors)
        candidate_sources = tuple(
            sources_by_path[source]
            for source in configured_source_map.get(chapter, ())
            if source in sources_by_path
        )
        if not configured_source_map:
            candidate_sources = sources
        for block, tex in pairs:
            body = block_body(tex)
            normalized = normalize_tex(body)
            canonical = canonicalize_tex_source(body)
            fingerprint = witness_fingerprint(body)
            pair_score = score_pair(block, tex)
            labels = set(pair_score.tex_labels)
            if pair_score.verso_header_id is not None:
                labels.add(pair_score.verso_header_id)
            labels = frozenset(labels)
            local_labels_by_chapter[chapter].update(labels)

            semantic_sources = tuple(
                source.relative_path
                for source in candidate_sources
                if normalized
                and any(normalized in variant for variant in source.normalized_variants)
            )
            exact_sources = tuple(
                source.relative_path
                for source in candidate_sources
                if (
                    any(canonical in variant for variant in source.canonical_variants)
                    if labels and canonical
                    else source.relative_path in semantic_sources
                )
            )
            label_sources = tuple(
                source.relative_path
                for source in candidate_sources
                if labels & source.node_labels
            )
            if pair_score.tex_env_kind in {
                "theorem",
                "lemma",
                "corollary",
                "definition",
                "proposition",
            }:
                for source in candidate_sources:
                    for node in source.nodes:
                        if normalized and normalized in node.normalized_text:
                            covered_source_labels_by_chapter[chapter].add(node.label)
            for source in semantic_sources:
                source_chapter_hits[source][chapter] += 1
            # A matching node label is stronger ownership evidence than prose,
            # which can be duplicated across legacy and active source files.
            for source in label_sources:
                source_chapter_hits[source][chapter] += 100

            if exact_sources:
                status = "exact"
                reason = None
                source_paths = exact_sources
            else:
                if semantic_sources:
                    raw_status = "metadata-changed"
                    raw_source_paths = semantic_sources
                elif label_sources:
                    raw_status = "content-changed"
                    raw_source_paths = label_sources
                else:
                    raw_status = "unmatched"
                    raw_source_paths = ()
                deviation_key = (chapter, fingerprint)
                deviation = witness_deviation_map.get(deviation_key)
                if deviation is not None:
                    status = "allowed"
                    reason = deviation.reason
                    used_witness_deviations.add(deviation_key)
                else:
                    status = raw_status
                    reason = None
                source_paths = raw_source_paths

            witnesses_by_chapter[chapter].append(
                WitnessFreshness(
                    chapter=chapter,
                    line=tex.start_line,
                    fingerprint=fingerprint,
                    labels=labels,
                    status=status,
                    source_paths=source_paths,
                    reason=reason,
                )
            )

    source_labels_by_chapter: dict[Path, list[SourceLabelFreshness]] = defaultdict(list)

    def add_missing_source_labels(chapter: Path, source: SourceDocument) -> None:
        covered_labels = (
            local_labels_by_chapter[chapter] | covered_source_labels_by_chapter[chapter]
        )
        for label in sorted(source.node_labels - covered_labels):
            deviation_key = (source.relative_path, label)
            deviation = source_label_deviation_map.get(deviation_key)
            if deviation is None:
                status = "missing"
                reason = None
            else:
                status = "allowed"
                reason = deviation.reason
                used_source_label_deviations.add(deviation_key)
            source_labels_by_chapter[chapter].append(
                SourceLabelFreshness(
                    chapter=chapter,
                    source=source.relative_path,
                    label=label,
                    status=status,
                    reason=reason,
                )
            )

    audited_source_paths: set[Path] = (
        set() if has_explicit_source_map else set(sources_by_path)
    )
    if configured_source_map:
        for chapter, source_paths in configured_source_map.items():
            for source_path in source_paths:
                source = sources_by_path.get(source_path)
                if source is not None:
                    audited_source_paths.add(source_path)
                    add_missing_source_labels(chapter, source)
    else:
        all_local_labels = (
            set().union(*local_labels_by_chapter.values()) if local_labels_by_chapter else set()
        )
        for source in sources:
            chapter_hits = source_chapter_hits.get(source.relative_path)
            if not chapter_hits or max(chapter_hits.values()) < 2:
                continue
            owner = sorted(
                chapter_hits,
                key=lambda chapter: (-chapter_hits[chapter], str(chapter)),
            )[0]
            audited_source_paths.add(source.relative_path)
            # In inference mode, retain the historical project-wide label
            # comparison because a source file may feed multiple chapters.
            local_labels_by_chapter[owner] |= all_local_labels
            add_missing_source_labels(owner, source)

    for deviation in deviations.witnesses:
        key = (deviation.chapter, deviation.fingerprint)
        if deviation.chapter in selected_chapters and key not in used_witness_deviations:
            errors.append(
                "unused witness deviation "
                f"{deviation.chapter} sha256={deviation.fingerprint[:12]}"
            )
    for deviation in deviations.source_labels:
        key = (deviation.source, deviation.label)
        if (
            deviation.source in audited_source_paths
            and key not in used_source_label_deviations
        ):
            errors.append(f"unused source-label deviation {deviation.source} label={deviation.label}")

    chapters: list[ChapterFreshness] = []
    for chapter_path in chapter_paths:
        absolute_chapter = (
            chapter_path if chapter_path.is_absolute() else project_root / chapter_path
        ).resolve()
        try:
            chapter = absolute_chapter.relative_to(project_root)
        except ValueError:
            continue
        chapters.append(
            ChapterFreshness(
                chapter=chapter,
                witnesses=tuple(witnesses_by_chapter[chapter]),
                source_labels=tuple(source_labels_by_chapter[chapter]),
            )
        )
    return ProjectFreshness(tuple(chapters), tuple(errors))


def print_report(report: ProjectFreshness, *, verbose: bool) -> None:
    totals = Counter(item.status for chapter in report.chapters for item in chapter.witnesses)
    label_totals = Counter(item.status for chapter in report.chapters for item in chapter.source_labels)
    print("summary:")
    print(f"  chapters: {len(report.chapters)}")
    print(f"  witnesses: {sum(totals.values())}")
    for status in ("exact", "metadata-changed", "content-changed", "unmatched", "allowed"):
        print(f"  witness_{status.replace('-', '_')}: {totals[status]}")
    print(f"  source_labels_missing: {label_totals['missing']}")
    print(f"  source_labels_allowed: {label_totals['allowed']}")
    print(f"  errors: {len(report.errors)}")
    print(f"  current: {'no' if report.needs_review else 'yes'}")

    print("chapters:")
    for chapter in report.chapters:
        counts = Counter(item.status for item in chapter.witnesses)
        print(
            f"  {chapter.chapter}: witnesses={len(chapter.witnesses)} "
            f"exact={counts['exact']} metadata_changed={counts['metadata-changed']} "
            f"content_changed={counts['content-changed']} "
            f"unmatched={counts['unmatched']} allowed={counts['allowed']} "
            f"source_labels_missing={chapter.missing_source_label_count} "
            f"source_labels_allowed={sum(item.status == 'allowed' for item in chapter.source_labels)}"
        )
        if verbose:
            for item in chapter.witnesses:
                if item.status == "exact":
                    continue
                labels = ",".join(sorted(item.labels)) or "-"
                sources = ",".join(str(path) for path in item.source_paths) or "-"
                reason = f" reason={item.reason}" if item.reason else ""
                print(
                    f"    line {item.line}: {item.status} labels={labels} "
                    f"sources={sources} sha256={item.fingerprint}{reason}"
                )
            for item in chapter.source_labels:
                reason = f" reason={item.reason}" if item.reason else ""
                print(
                    f"    source-label: {item.status} source={item.source} "
                    f"label={item.label}{reason}"
                )
    for error in report.errors:
        print(f"error: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that adjacent LT TeX witnesses are still grounded in the configured "
            "current upstream TeX source."
        )
    )
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--require-current",
        action="store_true",
        help="Return exit code 1 for stale witnesses, missing source labels, or stale deviations.",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    config = load_config(project_root)
    chapter_paths = resolve_chapter_paths(project_root, args.paths)
    report = audit_project(
        project_root,
        chapter_paths,
        source_glob=config.tex_source_glob,
        source_map=config.lt_source_files,
    )
    print(f"project root: {project_root}")
    print(f"tex_source_glob: {config.tex_source_glob}")
    print_report(report, verbose=args.verbose)
    if args.require_current and report.needs_review:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
