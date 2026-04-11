#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import difflib
import re
from pathlib import Path
import statistics
import sys
import unicodedata

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import resolve_chapter_paths, resolve_project_root  # noqa: E402
from check_lt_source_pairs import Block, parse_blocks  # noqa: E402

PLACEHOLDER_LEAN_TARGETS = {"???", "TODO", "TBD", "FIXME"}


def looks_like_placeholder_lean_target(target: str) -> bool:
    stripped = target.strip()
    return stripped in PLACEHOLDER_LEAN_TARGETS or stripped.endswith("_placeholder")


@dataclass
class PairScore:
    block: Block
    tex: Block
    sequence_ratio: float
    token_ratio: float
    length_ratio: float
    verso_text: str
    tex_text: str
    verso_uses: set[str]
    tex_uses: set[str]
    verso_lean: set[str]
    tex_lean: set[str]
    tex_labels: set[str]
    tex_refs: set[str]
    tex_env_kind: str | None
    tex_env_kinds: tuple[str, ...]
    verso_env_kind: str | None
    verso_header_id: str | None

    @property
    def primary_ratio(self) -> float:
        return self.token_ratio

    @property
    def missing_uses(self) -> set[str]:
        return self.tex_uses - self.verso_uses

    @property
    def extra_uses(self) -> set[str]:
        return self.verso_uses - self.tex_uses

    @property
    def missing_lean(self) -> set[str]:
        return self.tex_lean - self.verso_lean

    @property
    def extra_lean(self) -> set[str]:
        return self.verso_lean - self.tex_lean

    @property
    def placeholder_lean_attachments(self) -> set[str]:
        return {
            lean
            for lean in self.verso_lean
            if looks_like_placeholder_lean_target(lean) and lean not in self.tex_lean
        }

    @property
    def unresolved_ref_hints(self) -> set[str]:
        return self.tex_refs - self.tex_uses - self.tex_lean - self.verso_uses

    @property
    def pure_metadata_diff_count(self) -> int:
        return (
            len(self.missing_uses)
            + len(self.extra_uses)
            + len(self.missing_lean)
            + len(self.extra_lean)
        )

    @property
    def metadata_diff_count(self) -> int:
        return (
            self.pure_metadata_diff_count
            + (2 * len(self.strong_ref_candidates))
            + len(self.env_ref_hints)
        )

    @property
    def exact_drift_count(self) -> int:
        return (
            self.pure_metadata_diff_count
            + len(self.label_regrounding_candidates)
            + len(self.witness_mismatch_hints)
        )

    @property
    def label_regrounding_candidates(self) -> set[str]:
        if self.block.kind != "verso" or self.verso_header_id is None:
            return set()
        target_pool = self.tex_labels or self.tex_lean
        if not target_pool:
            return set()
        if self.verso_header_id in target_pool:
            return set()
        return target_pool

    @property
    def witness_mismatch_hints(self) -> tuple[str, ...]:
        if self.block.kind != "verso" or self.verso_env_kind is None:
            return ()
        hints: list[str] = []
        if len(self.tex_env_kinds) > 1:
            hints.append("multi_env_witness")
        if self.verso_env_kind == "proof" and "proof" not in self.tex_env_kinds:
            hints.append("proof_without_proof_env")
        return tuple(hints)

    @property
    def ref_hint_count(self) -> int:
        return (
            len(self.strong_ref_candidates)
            + len(self.env_ref_hints)
            + len(self.soft_ref_hints)
        )

    @property
    def strong_ref_candidates(self) -> set[str]:
        if self.tex_env_kind in {"theorem", "lemma", "corollary", "definition", "proof"} and self.tex_uses:
            return self.unresolved_ref_hints
        return set()

    @property
    def env_ref_hints(self) -> set[str]:
        if self.tex_env_kind in {"theorem", "lemma", "corollary", "definition", "proof"} and not self.tex_uses:
            return self.unresolved_ref_hints
        return set()

    @property
    def soft_ref_hints(self) -> set[str]:
        if self.tex_env_kind in {"theorem", "lemma", "corollary", "definition", "proof"}:
            return set()
        return self.unresolved_ref_hints


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
USES_RE = re.compile(r'\{uses "[^"]+"\}\[\]')
USES_CAPTURE_RE = re.compile(r'\{uses "([^"]+)"\}\[\]')
USES_LINE_RE = re.compile(
    r'(?m)^[ \t]*Uses (?:'
    r'\{uses "[^"]+"\}\[\]'
    r'|'
    r'\{uses "[^"]+"\}\[\] and \{uses "[^"]+"\}\[\]'
    r'|'
    r'\{uses "[^"]+"\}\[\](?:, \{uses "[^"]+"\}\[\])+, and \{uses "[^"]+"\}\[\]'
    r')\.[ \t]*$'
)
CITE_RE = re.compile(r"\{[^{}]*cite[^{}]*\}\[\]")
INLINE_TAG_RE = re.compile(r"\{[^{}]+\}\[\]")
TEX_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
TEX_META_RE = re.compile(r"\\(label|lean|uses|discussion|proves)\{[^{}]*\}")
TEX_REF_RE = re.compile(r"\\ref\{[^{}]*\}")
TEX_FLAGS_RE = re.compile(r"\\(leanok|mathlibok|notready)\b")
TEX_BEGIN_END_RE = re.compile(r"\\(begin|end)\{[^{}]*\}(?:\[[^\]]*\])?")
TEX_ITEM_RE = re.compile(r"\\item\b")
TEX_HREF_RE = re.compile(r"\\href\{[^{}]*\}\{([^{}]*)\}")
TEX_TEXORPDF_RE = re.compile(r"\\texorpdfstring\{([^{}]*)\}\{([^{}]*)\}")
TEX_SIMPLE_CMD_ARG_RE = re.compile(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}")
TEX_SIMPLE_CMD_RE = re.compile(r"\\([A-Za-z]+)")
TEX_USES_CAPTURE_RE = re.compile(r"\\uses\{([^{}]*)\}")
TEX_LEAN_CAPTURE_RE = re.compile(r"\\lean\{([^{}]*)\}")
TEX_REF_CAPTURE_RE = re.compile(r"\\ref\{([^{}]*)\}")
TEX_LABEL_CAPTURE_RE = re.compile(r"\\label\{([^{}]*)\}")
TEX_ENV_CAPTURE_RE = re.compile(r"\\begin\{(theorem|lemma|corollary|definition|proof|remark)\}")
VERSO_LEAN_CAPTURE_RE = re.compile(r'lean := "([^"]+)"')
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def paired_blocks(path: Path) -> tuple[list[tuple[Block, Block]], list[str]]:
    blocks = parse_blocks(path)
    pairs: list[tuple[Block, Block]] = []
    errors: list[str] = []

    for index, block in enumerate(blocks):
        if block.kind not in {"prose", "verso"}:
            continue
        if block.kind == "verso" and block.header.startswith(":::group "):
            continue
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        if following is None or following.kind != "tex":
            kind = "prose block" if block.kind == "prose" else "informal node"
            errors.append(
                f"{path}:{block.start_line}: {kind} is missing an adjacent ```tex block"
            )
            continue
        pairs.append((block, following))

    return pairs, errors


def block_body(block: Block) -> str:
    if block.kind == "verso":
        return "\n".join(block.lines[1:-1])
    if block.kind == "tex":
        return "\n".join(block.lines[1:-1])
    return "\n".join(block.lines)


def normalize_verso(text: str) -> str:
    text = USES_LINE_RE.sub(" ", text)
    text = MARKDOWN_LINK_RE.sub(r" \1 ", text)
    text = USES_RE.sub(" ", text)
    text = CITE_RE.sub(" ", text)
    text = INLINE_TAG_RE.sub(" ", text)
    return normalize_common(text)


def normalize_tex(text: str) -> str:
    stripped_lines = [TEX_COMMENT_RE.sub("", line) for line in text.splitlines()]
    text = "\n".join(stripped_lines)
    text = TEX_HREF_RE.sub(r" \1 ", text)
    text = TEX_TEXORPDF_RE.sub(r" \1 ", text)
    text = TEX_REF_RE.sub(" ", text)
    text = TEX_META_RE.sub(" ", text)
    text = TEX_FLAGS_RE.sub(" ", text)
    text = TEX_BEGIN_END_RE.sub(" ", text)
    text = TEX_ITEM_RE.sub(" ", text)

    previous = None
    while previous != text:
        previous = text
        text = TEX_SIMPLE_CMD_ARG_RE.sub(r" \1 ", text)

    return normalize_common(text)


def normalize_common(text: str) -> str:
    text = text.replace(":::"," ")
    text = text.replace("```", " ")
    text = text.replace("~", " ")
    text = text.replace("`", " ")
    text = text.replace("$", " ")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("‘", "'")
    text = text.replace("’", "'")
    text = text.replace("``", '"')
    text = text.replace("''", '"')
    text = text.replace("\\", " \\")
    text = TEX_SIMPLE_CMD_RE.sub(r" \1 ", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def token_ratio(left: str, right: str) -> float:
    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    common = sum((Counter(left_tokens) & Counter(right_tokens)).values())
    return (2 * common) / (len(left_tokens) + len(right_tokens))


def length_ratio(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return min(len(left), len(right)) / max(len(left), len(right))


def split_csv_items(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def strip_tex_comments(text: str) -> str:
    return "\n".join(TEX_COMMENT_RE.sub("", line) for line in text.splitlines())


def extract_verso_uses(text: str) -> set[str]:
    return {match.group(1).strip() for match in USES_CAPTURE_RE.finditer(text)}


def extract_verso_lean(header: str) -> set[str]:
    items: set[str] = set()
    for match in VERSO_LEAN_CAPTURE_RE.finditer(header):
        items |= split_csv_items(match.group(1))
    return items


def extract_tex_uses(text: str) -> set[str]:
    stripped = strip_tex_comments(text)
    items: set[str] = set()
    for match in TEX_USES_CAPTURE_RE.finditer(stripped):
        items |= split_csv_items(match.group(1))
    return items


def extract_tex_lean(text: str) -> set[str]:
    stripped = strip_tex_comments(text)
    items: set[str] = set()
    for match in TEX_LEAN_CAPTURE_RE.finditer(stripped):
        items |= split_csv_items(match.group(1))
    return items


def extract_tex_refs(text: str) -> set[str]:
    stripped = strip_tex_comments(text)
    return {match.group(1).strip() for match in TEX_REF_CAPTURE_RE.finditer(stripped)}


def extract_tex_labels(text: str) -> set[str]:
    stripped = strip_tex_comments(text)
    return {match.group(1).strip() for match in TEX_LABEL_CAPTURE_RE.finditer(stripped)}


def extract_tex_env_kind(text: str) -> str | None:
    stripped = strip_tex_comments(text)
    match = TEX_ENV_CAPTURE_RE.search(stripped)
    return match.group(1) if match else None


def extract_tex_env_kinds(text: str) -> tuple[str, ...]:
    stripped = strip_tex_comments(text)
    return tuple(match.group(1) for match in TEX_ENV_CAPTURE_RE.finditer(stripped))


def extract_verso_env_kind(header: str, kind: str) -> str | None:
    if kind != "verso":
        return None
    stripped = header.strip()
    if stripped.startswith(":::theorem "):
        return "theorem"
    if stripped.startswith(":::definition "):
        return "definition"
    if stripped.startswith(":::proof "):
        return "proof"
    return None


def extract_verso_header_id(header: str, kind: str) -> str | None:
    if kind != "verso":
        return None
    match = re.match(r'^:::(?:theorem|definition|proof) "([^"]+)"', header.strip())
    return match.group(1) if match else None


def score_pair(block: Block, tex: Block) -> PairScore:
    verso_body = block_body(block)
    tex_body = block_body(tex)
    verso_text = normalize_verso(verso_body)
    tex_text = normalize_tex(tex_body)
    return PairScore(
        block=block,
        tex=tex,
        sequence_ratio=difflib.SequenceMatcher(a=verso_text, b=tex_text).ratio(),
        token_ratio=token_ratio(verso_text, tex_text),
        length_ratio=length_ratio(verso_text, tex_text),
        verso_text=verso_text,
        tex_text=tex_text,
        verso_uses=extract_verso_uses(verso_body),
        tex_uses=extract_tex_uses(tex_body),
        verso_lean=extract_verso_lean(block.header),
        tex_lean=extract_tex_lean(tex_body),
        tex_labels=extract_tex_labels(tex_body),
        tex_refs=extract_tex_refs(tex_body),
        tex_env_kind=extract_tex_env_kind(tex_body),
        tex_env_kinds=extract_tex_env_kinds(tex_body),
        verso_env_kind=extract_verso_env_kind(block.header, block.kind),
        verso_header_id=extract_verso_header_id(block.header, block.kind),
    )


def summarize_file(
    path: Path,
    scores: list[PairScore],
    warn_below: float,
    top: int,
    verbose: bool,
) -> list[str]:
    primary_values = [score.primary_ratio for score in scores]
    low = [score for score in scores if score.primary_ratio < warn_below]
    low.sort(key=lambda score: (score.primary_ratio, score.sequence_ratio, score.block.start_line))
    exact_drift_pairs = [score for score in scores if score.exact_drift_count > 0]
    exact_drift_pairs.sort(
        key=lambda score: (
            -len(score.placeholder_lean_attachments),
            -score.exact_drift_count,
            score.block.start_line,
        )
    )
    pure_metadata_pairs = [score for score in scores if score.pure_metadata_diff_count > 0]
    placeholder_pairs = [score for score in scores if score.placeholder_lean_attachments]
    reground_pairs = [score for score in scores if score.label_regrounding_candidates]
    witness_pairs = [score for score in scores if score.witness_mismatch_hints]
    ref_review_pairs = [score for score in scores if score.ref_hint_count > 0]
    placeholder_count = sum(len(score.placeholder_lean_attachments) for score in scores)

    lines = [
        f"{path}: pairs={len(scores)} avg={statistics.mean(primary_values):.3f} "
        f"median={statistics.median(primary_values):.3f} min={min(primary_values):.3f} "
        f"warn_below={warn_below:.2f} low={len(low)} drift={len(exact_drift_pairs)} "
        f"pure_metadata={len(pure_metadata_pairs)} placeholder_lean={placeholder_count} "
        f"reground={len(reground_pairs)} witness={len(witness_pairs)} "
        f"ref_review={len(ref_review_pairs)}"
    ]

    if not verbose:
        if placeholder_pairs:
            lines.append("- LT-priority-1:")
            for score in placeholder_pairs[: min(3, top)]:
                kind = "prose" if score.block.kind == "prose" else "node"
                lines.append(
                    f"  line {score.block.start_line} {kind}: "
                    f"placeholder_lean={len(score.placeholder_lean_attachments)} "
                    f"text={score.block.preview()}"
                )
        if low:
            lines.append("- LT-focus:")
            for score in low[: min(3, top)]:
                kind = "prose" if score.block.kind == "prose" else "node"
                lines.append(
                    f"  line {score.block.start_line} {kind}: tok={score.token_ratio:.3f} "
                    f"text={score.block.preview()}"
                )
        if exact_drift_pairs:
            lines.append("- metadata-focus:")
            for score in exact_drift_pairs[: min(3, top)]:
                kind = "prose" if score.block.kind == "prose" else "node"
                lines.append(
                    f"  line {score.block.start_line} {kind}: "
                    f"drift={score.exact_drift_count} "
                    f"pure={score.pure_metadata_diff_count} "
                    f"placeholder_lean={len(score.placeholder_lean_attachments)} "
                    f"reground={len(score.label_regrounding_candidates)} "
                    f"witness={len(score.witness_mismatch_hints)} "
                    f"missing_uses={len(score.missing_uses)} "
                    f"missing_lean={len(score.missing_lean)} "
                    f"text={score.block.preview()}"
                )
        if ref_review_pairs:
            lines.append("- ref-review:")
            for score in ref_review_pairs[: min(3, top)]:
                kind = "prose" if score.block.kind == "prose" else "node"
                lines.append(
                    f"  line {score.block.start_line} {kind}: "
                    f"strong_refs={len(score.strong_ref_candidates)} "
                    f"env_ref_hints={len(score.env_ref_hints)} "
                    f"soft_ref_hints={len(score.soft_ref_hints)} "
                    f"text={score.block.preview()}"
                )
        return lines

    for score in low[:top]:
        kind = "prose" if score.block.kind == "prose" else "node"
        metadata_bits: list[str] = []
        if score.missing_uses:
            metadata_bits.append(f"missing_uses={sorted(score.missing_uses)}")
        if score.extra_uses:
            metadata_bits.append(f"extra_uses={sorted(score.extra_uses)}")
        if score.missing_lean:
            metadata_bits.append(f"missing_lean={sorted(score.missing_lean)}")
        if score.extra_lean:
            metadata_bits.append(f"extra_lean={sorted(score.extra_lean)}")
        if score.placeholder_lean_attachments:
            metadata_bits.append(
                f"placeholder_lean={sorted(score.placeholder_lean_attachments)}"
            )
        if score.label_regrounding_candidates:
            metadata_bits.append(f"label_reground={sorted(score.label_regrounding_candidates)}")
        if score.witness_mismatch_hints:
            metadata_bits.append(f"witness_hints={list(score.witness_mismatch_hints)}")
        if score.strong_ref_candidates:
            metadata_bits.append(f"strong_refs={sorted(score.strong_ref_candidates)}")
        if score.env_ref_hints:
            metadata_bits.append(f"env_ref_hints={sorted(score.env_ref_hints)}")
        if score.soft_ref_hints:
            metadata_bits.append(f"soft_ref_hints={sorted(score.soft_ref_hints)}")
        metadata_suffix = f" {'; '.join(metadata_bits)}" if metadata_bits else ""
        lines.append(
            f"- line {score.block.start_line} {kind}: seq={score.sequence_ratio:.3f} "
            f"tok={score.token_ratio:.3f} len={score.length_ratio:.3f} "
            f"text={score.block.preview()}{metadata_suffix}"
        )

    if exact_drift_pairs:
        lines.append("- metadata-focus:")
        for score in exact_drift_pairs[: min(5, top)]:
            kind = "prose" if score.block.kind == "prose" else "node"
            metadata_bits: list[str] = []
            if score.missing_uses:
                metadata_bits.append(f"missing_uses={sorted(score.missing_uses)}")
            if score.extra_uses:
                metadata_bits.append(f"extra_uses={sorted(score.extra_uses)}")
            if score.missing_lean:
                metadata_bits.append(f"missing_lean={sorted(score.missing_lean)}")
            if score.extra_lean:
                metadata_bits.append(f"extra_lean={sorted(score.extra_lean)}")
            if score.placeholder_lean_attachments:
                metadata_bits.append(
                    f"placeholder_lean={sorted(score.placeholder_lean_attachments)}"
                )
            if score.label_regrounding_candidates:
                metadata_bits.append(f"label_reground={sorted(score.label_regrounding_candidates)}")
            if score.witness_mismatch_hints:
                metadata_bits.append(f"witness_hints={list(score.witness_mismatch_hints)}")
            lines.append(
                f"  line {score.block.start_line} {kind}: "
                + "; ".join(metadata_bits)
                + f" text={score.block.preview()}"
            )

    if ref_review_pairs:
        lines.append("- ref-review:")
        for score in ref_review_pairs[: min(5, top)]:
            kind = "prose" if score.block.kind == "prose" else "node"
            review_bits: list[str] = []
            if score.strong_ref_candidates:
                review_bits.append(f"strong_refs={sorted(score.strong_ref_candidates)}")
            if score.env_ref_hints:
                review_bits.append(f"env_ref_hints={sorted(score.env_ref_hints)}")
            if score.soft_ref_hints:
                review_bits.append(f"soft_ref_hints={sorted(score.soft_ref_hints)}")
            lines.append(
                f"  line {score.block.start_line} {kind}: "
                + "; ".join(review_bits)
                + f" text={score.block.preview()}"
            )

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Block-level LT similarity checker using adjacent tex witnesses. "
            "LT is the canonical repository term; LF and TF are accepted aliases. "
            "This first draft follows David's suggestion to add a mechanical LT drift signal."
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
    parser.add_argument(
        "--warn-below",
        type=float,
        default=0.70,
        help="Report blocks whose token similarity falls below this threshold.",
    )
    parser.add_argument(
        "--fail-below",
        type=float,
        default=None,
        help="Exit with code 1 if any block falls below this threshold.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum number of low-similarity blocks to print per file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the detailed per-block drift and metadata dump. Default output is summary-first.",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    paths = resolve_chapter_paths(project_root, args.paths)

    missing = [path for path in paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing file: {path}", file=sys.stderr)
        return 2

    overall_fail = False
    any_scores = False

    for path in paths:
        pairs, errors = paired_blocks(path)
        if errors:
            print(f"{path}: cannot compare because some blocks are missing adjacent tex witnesses:")
            for error in errors:
                print(f"- {error}")
            overall_fail = True
            continue

        scores = [score_pair(block, tex) for block, tex in pairs]
        if not scores:
            print(f"{path}: no comparable block pairs found")
            continue
        any_scores = True

        for line in summarize_file(path, scores, args.warn_below, args.top, args.verbose):
            print(line)

        if args.fail_below is not None and any(score.primary_ratio < args.fail_below for score in scores):
            overall_fail = True

    if not any_scores and not overall_fail:
        print("No comparable LT block pairs found.")

    return 1 if overall_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
