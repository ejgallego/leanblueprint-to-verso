#!/usr/bin/env bash

set -euo pipefail

step() {
  printf '\n[ci-pages] %s\n' "$*" >&2
}

step "checking source-paired chapter metadata"
python3 tools/verso-harness/scripts/status_completion.py --project-root . --require-metadata-clean

if [ -x scripts/ci-pre-build.sh ]; then
  step "running pre-build hook"
  scripts/ci-pre-build.sh
fi

step "warming dependency cache"
python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root . --warm-cache__MAX_MISSING_MATHLIB_MODULES_OPTION__

step "building Blueprint site"
lake exe vbp build --output _out/site 2>&1 | python3 scripts/filter_docstring_warnings.py --project-root .

step "checking dependency cache after build"
python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root .__MAX_MISSING_MATHLIB_MODULES_OPTION__

step "checking generated site"
python3 tools/verso-harness/scripts/check_generated_site.py --project-root . --site-dir _out/site/html-multi

if [ -x scripts/ci-post-build.sh ]; then
  step "running post-build hook"
  scripts/ci-post-build.sh
fi
