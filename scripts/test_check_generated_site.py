#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_generated_site.py"


def write_site(
    root: Path,
    *,
    html: str | None = None,
    manifest: object | None = None,
    html_cache: object | None = None,
    legacy_manifest: object | None = None,
    asset_files: list[str] | None = None,
) -> Path:
    site = root / "_out" / "site" / "html-multi"
    data = site / "-verso-data"
    data.mkdir(parents=True)
    (site / "-verso-search").mkdir()
    (site / "index.html").write_text(
        textwrap.dedent(
            html
            or """
            <!doctype html>
            <html>
              <head>
                <script src="-verso-data/runtime.js"></script>
                <script>
                  fetch("-verso-data/blueprint-html-cache.json");
                </script>
              </head>
            </html>
            """
        ),
        encoding="utf-8",
    )
    for name in asset_files or ["runtime.js"]:
        (data / name).write_text("", encoding="utf-8")
    if manifest is not None:
        (data / "blueprint-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if html_cache is not None:
        (data / "blueprint-html-cache.json").write_text(json.dumps(html_cache), encoding="utf-8")
    if legacy_manifest is not None:
        (data / "blueprint-preview-manifest.json").write_text(
            json.dumps(legacy_manifest),
            encoding="utf-8",
        )
    return site


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(root),
            "--site-dir",
            "_out/site/html-multi",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckGeneratedSiteTests(unittest.TestCase):
    def test_accepts_current_split_preview_data_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_site(
                root,
                manifest={"previews": [{"key": "demo"}]},
                html_cache={"entries": [{"key": "demo", "html": "<p>demo</p>"}], "hoverDocs": []},
            )

            result = run_check(root)

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("[generated-site] ok", result.stdout)

    def test_accepts_empty_split_preview_data_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_site(
                root,
                manifest={"previews": []},
                html_cache={"entries": [], "hoverDocs": []},
            )

            result = run_check(root)

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_accepts_legacy_combined_preview_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_site(
                root,
                html="""
                <!doctype html>
                <html>
                  <head>
                    <script>
                      fetch("-verso-data/blueprint-preview-manifest.json");
                    </script>
                  </head>
                </html>
                """,
                legacy_manifest={"previews": [{"key": "demo", "html": "<p>demo</p>"}]},
            )

            result = run_check(root)

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_reports_missing_referenced_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_site(
                root,
                html="""
                <!doctype html>
                <html>
                  <head>
                    <script>
                      fetch("-verso-data/missing-cache.json");
                    </script>
                  </head>
                </html>
                """,
                manifest={"previews": [{"key": "demo"}]},
                html_cache={"entries": [{"key": "demo", "html": "<p>demo</p>"}]},
            )

            result = run_check(root)

            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("references missing asset", result.stderr)
            self.assertIn("missing-cache.json", result.stderr)

    def test_reports_missing_rendered_preview_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_site(root, manifest={"previews": [{"key": "demo"}]})

            result = run_check(root)

            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("missing rendered preview data", result.stderr)


if __name__ == "__main__":
    unittest.main()
