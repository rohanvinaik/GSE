#!/usr/bin/env bash
# The gate. Run before every commit and push; CI (.github/workflows/ci.yml) runs exactly this.
#
#   ruff check      lint — blocking
#   ruff format     format check — blocking (Python only; Markdown is excluded in pyproject)
#   pytest          the suite — blocking (strict markers/config, xfail_strict; see pyproject)
#   ty              type check — ADVISORY: printed, never fails the gate (findings are leads)
#
# ruff is pinned to the version the repo was formatted with, so a newer ruff can never move the
# format gate silently; bump it deliberately, reformat, and record the commit in .git-blame-ignore-revs.
set -euo pipefail
cd "$(dirname "$0")/.."

RUFF="uvx ruff@0.16.10"

echo "== ruff check"
$RUFF check .

echo "== ruff format --check"
$RUFF format --check .

echo "== pytest"
uv run pytest

echo "== ty check gse (advisory)"
if uvx ty check gse --output-format concise; then
    echo "== ty passed"
else
    echo "== ty reported advisory findings (full output above)"
fi

echo "== gate passed"
