#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SCRATCH_ROOT = ROOT / ".scratch"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_lt_similarity import paired_blocks, score_pair  # noqa: E402
from check_lt_source_pairs import Block  # noqa: E402


def verso_block(body: str, header: str = ':::theorem "demo"') -> Block:
    lines = [header, *body.splitlines(), ":::"]
    return Block("verso", 1, len(lines), header, lines)


def tex_block(body: str) -> Block:
    lines = ['```tex "demo"', *body.splitlines(), "```"]
    return Block("tex", 1, len(lines), 'tex "demo"', lines)


class CheckLtSimilarityTests(unittest.TestCase):
    def scratch_dir(self) -> tempfile.TemporaryDirectory[str]:
        SCRATCH_ROOT.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=SCRATCH_ROOT)

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
        with self.scratch_dir() as tmp:
            path = Path(tmp) / "Demo.lean"
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
        with self.scratch_dir() as tmp:
            path = Path(tmp) / "Demo.lean"
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
                cwd=ROOT,
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
        with self.scratch_dir() as tmp:
            path = Path(tmp) / "Demo.lean"
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
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("- metadata-focus:", result.stdout)
            self.assertNotIn("missing_uses=['bar']", result.stdout)

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
        with self.scratch_dir() as tmp:
            path = Path(tmp) / "Demo.lean"
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
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("missing_uses=['bar']", result.stdout)


if __name__ == "__main__":
    unittest.main()
