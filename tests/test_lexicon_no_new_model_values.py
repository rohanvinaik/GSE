"""No model decides a lexical value (Rohan, 2026-11-25).

Every value is derived by the symbolic process: sources, rules, coherence and closure. The only
model-made values are the 127 cells Rohan authorized by hand before 2026-11-25; their set is
pinned by digest, so one new model-made cell fails this test. The word-sense build and its runtime
reader import nothing that calls a model.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_MODEL_CELLS = 127
AUTHORIZED_MODEL_CELLS_SHA256 = "446f643f57bb76a26f3f74eb6ba2cc3e24176d7f6ab0555609e79a44226a4782"
SYMBOLIC_MODULES = (
    "GSE/curation/lexicon_builder/source_agreement.py",
    "GSE/curation/lexicon_builder/word_senses.py",
    "GSE/lexicon/senses.py",
    "scripts/build_word_senses.py",
)
MODEL_CALLERS = ("residual", "completion", "model_protocol", "model_batch", "model_evidence", "model_receipts", "llm")


@pytest.mark.parametrize("path", SYMBOLIC_MODULES)
def test_the_symbolic_build_imports_nothing_that_calls_a_model(path):
    tree = ast.parse((ROOT / path).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.update(node.module.split("."))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.update(alias.name.split("."))
    assert not imported & set(MODEL_CALLERS), f"{path} imports {sorted(imported & set(MODEL_CALLERS))}"


def _lexicons():
    from GSE.lexicon_resource import resolve_lexicon_path

    paths = [resolve_lexicon_path()]  # the active lexicon
    if os.environ.get("GSE_SENSE_CANDIDATE"):
        paths.append(Path(os.environ["GSE_SENSE_CANDIDATE"]))
    return [p for p in paths if p.is_file()]


@pytest.mark.skipif(not _lexicons(), reason="no local lexicon")
@pytest.mark.parametrize("path", _lexicons(), ids=lambda p: p.name)
def test_the_only_model_made_cells_are_the_authorized_ones(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT entry_id, payload FROM accepted_model_receipts").fetchall()
    cells = sorted({(entry, json.loads(payload)["assertion"]["bank"]) for entry, payload in rows})
    assert len(cells) == AUTHORIZED_MODEL_CELLS
    assert hashlib.sha256(json.dumps(cells).encode()).hexdigest() == AUTHORIZED_MODEL_CELLS_SHA256
