#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_lt_similarity import paired_blocks, score_pair  # noqa: E402
from check_lt_source_pairs import Block  # noqa: E402


def verso_block(body: str, header: str = ':::theorem "demo"') -> Block:
    lines = [header, *body.splitlines(), ":::"]
    return Block("verso", 1, len(lines), header, lines)


def tex_block(body: str) -> Block:
    lines = ['```tex "demo"', *body.splitlines(), '```']
    return Block("tex", 1, len(lines), 'tex "demo"', lines)


def write_config(root: Path, default_chapters: list[str]) -> None:
    config = "\n".join(
        [
            'package_name = "DemoBlueprint"',
            'blueprint_main = "BlueprintMain"',
            'formalization_path = "Demo"',
            'chapter_root = "."',
            'tex_source_glob = "./blueprint/src/chapter/*.tex"',
            '',
            '[lt]',
            f'default_chapters = [{", ".join(repr(path) for path in default_chapters)}]',
            '',
            '[harness]',
            'non_port_chapters = []',
            '',
        ]
    )
    (root / 'verso-harness.toml').write_text(config, encoding='utf-8')


class CheckLtSimilarityTests(unittest.TestCase):
    def test_metadata_and_markup_are_ignored(self) -> None:
        verso = verso_block('Alpha {uses "foo"}[] [Beta](https://example.com) and $`Gamma`$.')
        tex = tex_block(
            r"""
\label{foo}
\uses{bar}
Alpha Beta and Gamma.
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertGreaterEqual(score.token_ratio, 0.99)

    def test_multiple_uses_and_comma_separated_metadata_are_extracted(self) -> None:
        verso = verso_block(
            'Alpha {uses "foo"}[] and {uses "bar"}[].',
            header=':::theorem "demo" (lean := "Baz.qux, Demo.quux")',
        )
        tex = tex_block(
            r"""
\lean{Baz.qux, Demo.quux}
\uses{foo, bar}
Alpha.
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.verso_uses, {"foo", "bar"})
        self.assertEqual(score.tex_uses, {"foo", "bar"})
        self.assertEqual(score.verso_lean, {"Baz.qux", "Demo.quux"})
        self.assertEqual(score.tex_lean, {"Baz.qux", "Demo.quux"})
        self.assertEqual(score.metadata_diff_count, 0)

    def test_refs_are_reported_as_hints_not_uses(self) -> None:
        verso = verso_block("Alpha.")
        tex = tex_block(
            r"""
\uses{foo}
By theorem~\ref{bar} and theorem~\ref{baz}.
Alpha.
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.tex_uses, {"foo"})
        self.assertEqual(score.tex_refs, {"bar", "baz"})
        self.assertEqual(score.strong_ref_candidates, set())
        self.assertEqual(score.soft_ref_hints, {"bar", "baz"})

    def test_env_refs_with_uses_are_strong_candidates(self) -> None:
        verso = verso_block('Alpha {uses "foo"}[].')
        tex = tex_block(
            r"""
\begin{proof}
\uses{foo}
By theorem~\ref{bar}.
\end{proof}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.tex_env_kind, "proof")
        self.assertEqual(score.strong_ref_candidates, {"bar"})
        self.assertGreaterEqual(score.metadata_diff_count, 2)

    def test_env_refs_without_uses_are_medium_hints(self) -> None:
        verso = verso_block("Alpha.")
        tex = tex_block(
            r"""
\begin{proof}
By theorem~\ref{bar}.
\end{proof}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.tex_env_kind, "proof")
        self.assertEqual(score.env_ref_hints, {"bar"})
        self.assertEqual(score.strong_ref_candidates, set())

    def test_label_regrounding_candidates_detect_wrapper_node(self) -> None:
        verso = verso_block("Alpha.", header=':::theorem "english_wrapper" (lean := "Demo.foo")')
        tex = tex_block(
            r"""
\begin{theorem}
\label{Demo.foo}
\lean{Demo.foo}
Alpha.
\end{theorem}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.label_regrounding_candidates, {"Demo.foo"})

    def test_outer_repo_placeholder_lean_is_flagged(self) -> None:
        verso = verso_block("Alpha.", header=':::theorem "demo" (lean := "Demo.foo_placeholder")')
        tex = tex_block(
            r"""
\begin{theorem}
\label{demo}
Alpha.
\end{theorem}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.placeholder_lean_attachments, {"Demo.foo_placeholder"})

    def test_source_placeholder_lean_is_not_flagged_as_outer_repo_placeholder(self) -> None:
        verso = verso_block("Alpha.", header=':::theorem "demo" (lean := "Demo.foo_placeholder")')
        tex = tex_block(
            r"""
\begin{theorem}
\label{demo}
\lean{Demo.foo_placeholder}
Alpha.
\end{theorem}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertEqual(score.placeholder_lean_attachments, set())

    def test_witness_mismatch_detects_multi_env_proof_witness(self) -> None:
        verso = verso_block("Alpha.", header=':::proof "Demo.foo"')
        tex = tex_block(
            r"""
\begin{lemma}
\label{Demo.foo}
Alpha.
\end{lemma}
\begin{proof}
Alpha.
\end{proof}
""".strip()
        )
        score = score_pair(verso, tex)
        self.assertIn("multi_env_witness", score.witness_mismatch_hints)
        self.assertNotIn("proof_without_proof_env", score.witness_mismatch_hints)

    def test_unrelated_pair_scores_low(self) -> None:
        verso = verso_block("alpha beta gamma")
        tex = tex_block("delta epsilon zeta")
        score = score_pair(verso, tex)
        self.assertLessEqual(score.token_ratio, 0.1)

    def test_local_witness_scores_better_than_oversized_witness(self) -> None:
        verso = verso_block("Restricted products commute with finite products.")
        local_tex = tex_block(
            r"""
\begin{corollary}
Restricted products commute with finite products.
\end{corollary}
""".strip()
        )
        oversized_tex = tex_block(
            r"""
\subsection{Products}
\begin{lemma}
Restricted products commute with finite products.
\end{lemma}
\begin{remark}
This may fail without openness because filtered colimits and products need not commute.
\end{remark}
\begin{proof}
We need continuity in both directions and several finite-stage reductions.
\end{proof}
\begin{corollary}
Matrices over restricted products are also homeomorphic.
\end{corollary}
""".strip()
        )

        local_score = score_pair(verso, local_tex)
        oversized_score = score_pair(verso, oversized_tex)
        self.assertGreater(local_score.token_ratio, oversized_score.token_ratio)

    def test_adjacent_pairing_matches_informal_blocks(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "demo"
Alpha beta gamma.
:::
```tex "demo/theorem"
\\begin{theorem}
Alpha beta gamma.
\\end{theorem}
```

Plain prose block.
```tex "demo/prose"
Plain prose block.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            pairs, errors = paired_blocks(path)
            self.assertEqual(errors, [])
            self.assertEqual(len(pairs), 2)

    def test_cli_fail_below_catches_bad_pair(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "demo"
Alpha beta gamma.
:::
```tex "demo/theorem"
\\begin{theorem}
Delta epsilon zeta.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_similarity.py"),
                    "--project-root",
                    tmp,
                    str(path),
                    "--fail-below",
                    "0.50",
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)

    def test_cli_default_is_summary_first(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "demo" (lean := "Demo.foo")
Alpha {uses "foo"}[].
:::
```tex "demo/theorem"
\\begin{theorem}
\\lean{Demo.bar}
\\uses{bar}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_similarity.py"),
                    "--project-root",
                    tmp,
                    str(path),
                    "--top",
                    "3",
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("- metadata-focus:", result.stdout)
            self.assertNotIn("missing_uses=['bar']", result.stdout)
            self.assertIn("pure_metadata=", result.stdout)

    def test_cli_separates_ref_review_from_exact_drift(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::proof "demo"
Alpha.
:::
```tex "demo/proof"
\\begin{proof}
By theorem~\\ref{bar}.
\\end{proof}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_similarity.py"),
                    "--project-root",
                    tmp,
                    str(path),
                    "--top",
                    "3",
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("drift=0", result.stdout)
            self.assertIn("ref_review=1", result.stdout)
            self.assertIn("- ref-review:", result.stdout)
            self.assertNotIn("- metadata-focus:", result.stdout)

    def test_cli_surfaces_placeholder_lean_priority(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "demo" (lean := "Demo.foo_placeholder")
Alpha.
:::
```tex "demo/theorem"
\\begin{theorem}
\\label{demo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_similarity.py"),
                    "--project-root",
                    tmp,
                    str(path),
                    "--top",
                    "3",
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("placeholder_lean=1", result.stdout)
            self.assertIn("- LT-priority-1:", result.stdout)

    def test_cli_verbose_shows_detailed_metadata(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "demo" (lean := "Demo.foo")
Alpha {uses "foo"}[].
:::
```tex "demo/theorem"
\\begin{theorem}
\\lean{Demo.bar}
\\uses{bar}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ["Demo.lean"])
            path = root / "Demo.lean"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_similarity.py"),
                    "--project-root",
                    tmp,
                    str(path),
                    "--top",
                    "3",
                    "--verbose",
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("missing_uses=['bar']", result.stdout)
            self.assertIn("label_reground=", result.stdout)


if __name__ == "__main__":
    unittest.main()
