#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap

from check_verso_math_delimiters import suspicious_math_syntax


def write_tmp(tmp: Path, body: str) -> Path:
    path = tmp / "Sample.lean"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_heading_raw_dollar() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            # Heading with $x$
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "heading contains raw dollar math" in errs[0]


def test_malformed_inline_math() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            This contains malformed inline math $`a`$ in prose.
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "malformed Verso inline math delimiter" in errs[0]


def test_valid_verso_inline_math_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            This contains valid Verso inline math $`a` in prose.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_missing_closing_backtick() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            This contains malformed inline math $`a$ in prose.
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "missing closing backtick" in errs[0]


def test_extra_closing_backtick() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            This contains malformed inline math $`a`` in prose.
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "extra closing backtick" in errs[0]


def test_skip_fenced_tex() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            ```tex "witness"
            This TeX witness contains $a$ and should be ignored.
            ```
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_obsolete_bold_switch_is_flagged() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            This rendered math uses $`{\bf I}(x)` and can break PDF generation.
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "obsolete TeX font switch '\\bf'" in errs[0]
        assert "\\mathbf" in errs[0]


def test_modern_bold_commands_are_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            This uses $`\mathbf{I}(x)` in math and **bold text** in prose.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_mathy_code_span_is_flagged() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            This accidentally uses `\rho : G_F \to \GL_2(k)` as code.
            """,
        )
        errs = suspicious_math_syntax(path)
        assert len(errs) == 1
        assert "looks like math" in errs[0]


def test_lean_name_code_span_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            This keeps `FixedPoints.toAlgAut_surjective` as code.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_blueprint_tex_marker_code_span_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            This documents `\leanok`, `\uses{foo}`, and `\bpref{bar}` as source syntax.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_hyphenated_phrase_code_span_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            This keeps `source-paired LT audit required` as an ordinary label.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_shell_command_code_span_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            Run `python3 tools/verso-harness/scripts/check_lt_similarity.py --project-root .` after the edit.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_file_path_code_span_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            """
            #doc (Manual) "X" =>

            Compare against `FLT/blueprint/src/chapter/*.tex` before guessing.
            """,
        )
        assert suspicious_math_syntax(path) == []


def test_inline_math_next_to_code_span_is_not_cross_matched() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_tmp(
            Path(tmpdir),
            r"""
            #doc (Manual) "X" =>

            Here $`\ell \ge 5` is math, but `2` should remain code.
            """,
        )
        assert suspicious_math_syntax(path) == []


if __name__ == "__main__":
    test_heading_raw_dollar()
    test_malformed_inline_math()
    test_valid_verso_inline_math_is_ignored()
    test_missing_closing_backtick()
    test_extra_closing_backtick()
    test_skip_fenced_tex()
    test_obsolete_bold_switch_is_flagged()
    test_modern_bold_commands_are_ignored()
    test_mathy_code_span_is_flagged()
    test_lean_name_code_span_is_ignored()
    test_blueprint_tex_marker_code_span_is_ignored()
    test_hyphenated_phrase_code_span_is_ignored()
    test_shell_command_code_span_is_ignored()
    test_file_path_code_span_is_ignored()
    test_inline_math_next_to_code_span_is_not_cross_matched()
    print("check_verso_math_delimiters tests passed")
