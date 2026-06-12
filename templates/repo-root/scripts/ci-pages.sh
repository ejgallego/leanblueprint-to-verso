#!/usr/bin/env bash

set -euo pipefail

python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root . --warm-cache
lake build +__BLUEPRINT_MAIN__ 2>&1 | python3 scripts/filter_docstring_warnings.py --project-root .
python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root .
lake env lean --run __BLUEPRINT_MAIN__.lean --output _out/site 2>&1 | python3 scripts/filter_docstring_warnings.py --project-root .

check_file() {
  if [ ! -f "$1" ]; then
    printf 'missing expected generated file: %s\n' "$1" >&2
    exit 1
  fi
}

check_file _out/site/html-multi/index.html
check_file _out/site/html-multi/-verso-data/blueprint-manifest.json
check_file _out/site/html-multi/-verso-data/blueprint-html-cache.json
