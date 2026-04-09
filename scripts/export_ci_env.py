#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_project_root  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CI-relevant values from verso-harness.toml."
    )
    parser.add_argument("--project-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = resolve_project_root(args.project_root)
    config = load_config(project_root)
    print(f"formalization_path={config.formalization_path}")
    print(f"blueprint_main_path={config.blueprint_main}.lean")
    print(f"package_name={config.package_name}")
    print(f"chapter_root={config.chapter_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
