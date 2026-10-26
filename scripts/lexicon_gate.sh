#!/usr/bin/env bash
# Lexicon-builder gate. Run before every lexicon-builder change; the repo gate (ci_local.sh) still runs too.
#
#   ruff check / format   blocking, same pinned ruff as ci_local.sh, scoped to the builder, its tests and scripts
#   pytest                blocking: lexicon tests plus Detective-generated lexicon tests
#   ty                    advisory, as in ci_local.sh
#   frozen build          blocking: a symbolic-only build of gate_words.txt is compared with the baseline by
#                         scripts/lexicon_frozen_build.py. Source files must match the lock first (exit 3 =
#                         data changed, not code); outputs must be byte-identical or equal as JSON (key order is
#                         not part of the output contract). Exit 2 (UNMEASURED) when the local sources are absent.
#
# Output is never filtered or truncated. The build directory and its log are kept, and their path is printed.
# A same-answer change must pass unchanged. Only a deliberate contract or data change may refresh the
# baseline: `scripts/lexicon_gate.sh --rebaseline`, committed with the change that justifies it.
set -euo pipefail
cd "$(dirname "$0")/.."

RUFF="uvx ruff@0.16.10"
GATE=docs/verification/lexicon-rebuild/closeout-2026-10-25/gate
PY_PATHS=(gse/lexicon_builder tests/lexicon_sources.py tests/test_lexicon_*.py
    scripts/lexicon_coherence.py scripts/lexicon_frozen_build.py)

echo "== ruff check"
$RUFF check "${PY_PATHS[@]}"

echo "== ruff format --check"
$RUFF format --check "${PY_PATHS[@]}"

echo "== pytest (lexicon)"
uv run pytest tests/test_lexicon_*.py tests/detective/ -k "lexicon or coherence or bank or admission"

echo "== ty check gse/lexicon_builder (advisory)"
uvx ty check gse/lexicon_builder --output-format concise || echo "== ty reported advisory findings"

echo "== frozen symbolic build"
if [[ ! -f data/external/usas/semantic_lexicon_en.tsv || ! -d "$HOME/nltk_data/corpora/verbnet" ]]; then
    echo "UNMEASURED: lexicon sources absent (data/external, ~/nltk_data/corpora)"
    exit 2
fi
out=$(mktemp -d)
echo "build directory and log: $out"
uv run python -m gse.lexicon_builder build --symbolic-only --word-file "$GATE/gate_words.txt" --output "$out" \
    >"$out/build.log" 2>&1
if [[ "${1:-}" == "--rebaseline" ]]; then
    uv run python scripts/lexicon_frozen_build.py write "$out" "$GATE"
    exit 0
fi
uv run python scripts/lexicon_frozen_build.py check "$out" "$GATE"

echo "== lexicon gate passed"
