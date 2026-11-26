"""Every value in the word senses has a warrant, or it is thrown out (Rohan, 2026-11-25).

"If some addition doesn't have a rule behind it or a direct warrant from the underlying NLP data
sources we have, then it gets tossed." Each assigned value records where it came from, and this
check confirms the warrant is real:

- from members: each named definition exists in the release and holds that value (the release's
  definitions are replay-validated against their own source assertions and rules);
- from source-agreement: at least two named families, each measuring the bank, and each family has
  a stored source vote for that sign;
- from rules: each named rule is an admitted rule, either the release's own or a word-sense rule
  recorded with admission statistics that meet the population policy;
- from genus-differentia (Rohan, 2026-11-26, decision 1): each named definition has a stored closure
  record (``genus_differentia_closure``) that settled that cell to that value, and the record names
  its warrant: the axiom that set it, or the genus edge (genus words and their definitions) plus its
  differentia.

A value with no warrant, or a warrant of any other kind, fails. Model-made values are limited to
Rohan's 127 by ``test_lexicon_no_new_model_values``. The check runs on a built candidate:

    GSE_SENSE_CANDIDATE=data/lexicon_builder/2026-11-12/sparse-release-022-word-senses.db \\
        .venv/bin/python -m pytest tests/test_lexicon_every_value_has_a_warrant.py
"""

from __future__ import annotations

import ast
import json
import os
import sqlite3
from pathlib import Path

import pytest

from GSE.curation.lexicon_builder import source_agreement as sa

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = os.environ.get("GSE_SENSE_CANDIDATE", "")
# The population policy for admitting a coherence rule (design, FC-5 / WP-3).
MIN_CONDITIONAL_PROBABILITY = 0.85
MIN_SUPPORT_PER_PARTITION = 40
MAX_HELD_OUT_DRIFT = 0.1
WORD_SENSE_MODULES = sorted(
    {
        *ROOT.glob("GSE/curation/lexicon_builder/word_sense*.py"),
        ROOT / "GSE/curation/lexicon_builder/source_agreement.py",
        ROOT / "GSE/lexicon/senses.py",
        ROOT / "scripts/build_word_senses.py",
    }
)
LARGEST_LITERAL = 25  # a hand-typed word list in code is not a rule


@pytest.mark.parametrize("path", WORD_SENSE_MODULES, ids=lambda p: p.name)
def test_no_hand_typed_word_list_is_disguised_as_code(path):
    """A rule is a few lines over the sources; a long literal list of strings is a word list."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, (ast.List, ast.Set, ast.Tuple, ast.Dict)):
            items = node.keys if isinstance(node, ast.Dict) else node.elts
            strings = [i for i in items if isinstance(i, ast.Constant) and isinstance(i.value, str)]
            assert len(strings) <= LARGEST_LITERAL, f"{path.name}:{node.lineno} has {len(strings)} literal strings"


def _admitted_rules(conn) -> set[str]:
    meta = dict(conn.execute("SELECT key, value FROM builder_metadata WHERE key IN ('relations', 'word_sense_rules')"))
    admitted = {rule["rule_id"] for rule in json.loads(meta["relations"]) if rule.get("approved")}
    for rule in json.loads(meta.get("word_sense_rules") or "[]"):
        admission = rule["admission"]
        assert admission["conditional_probability"] >= MIN_CONDITIONAL_PROBABILITY, rule["rule_id"]
        assert admission["min_partition_support"] >= MIN_SUPPORT_PER_PARTITION, rule["rule_id"]
        assert admission["held_out_drift"] <= MAX_HELD_OUT_DRIFT, rule["rule_id"]
        admitted.add(rule["rule_id"])
    return admitted


def _closure_records(conn) -> dict[str, tuple[dict, dict]]:
    """entry -> (cells the genus/differentia closure settled, its edge or axiom record)."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='genus_differentia_closure'").fetchone():
        return {}
    return {
        entry: (json.loads(settled), json.loads(edge))
        for entry, settled, edge in conn.execute("SELECT entry_id, settled, edge FROM genus_differentia_closure")
    }


def _closure_warrant(record, bank, value) -> bool:
    if record is None:
        return False
    settled, edge = record
    if settled.get(bank) != value:
        return False
    axiom = edge.get("axiom") or {}
    if bank in axiom.get("settled", {}):
        return bool(axiom.get("kind"))
    return bool(edge.get("genus")) and "differentia" in edge and bool(edge.get("template"))


def _unwarranted(value, origin, domains, votes, admitted, bank, closure=None) -> str | None:
    kind = origin.get("from") if isinstance(origin, dict) else None
    if kind == "genus-differentia":
        entries = origin.get("entries") or []
        bad = [e for e in entries if not _closure_warrant((closure or {}).get(e), bank, value)]
        return None if entries and not bad else f"no closure record settles it: {bad[:3] or 'none named'}"
    if kind == "members":
        entries = origin.get("entries") or []
        bad = [e for e in entries if domains.get(e, {}).get(bank) != [value]]
        return None if entries and not bad else f"members do not hold it: {bad[:3] or 'none named'}"
    if kind == "source-agreement":
        families = origin.get("families") or []
        backed = [
            f
            for f in set(families)
            if sa.measures(f, bank)
            and any(sa.family_of(s) == f and signs.get(bank) == value for s, signs in votes.items())
        ]
        return None if len(backed) >= sa.MIN_FAMILIES else f"families {families} back it {len(backed)} times"
    if kind == "nsm-molecule":  # recomputed from the verified NSM extracts and WordNet (word_sense_nsm_molecules)
        from GSE.curation.lexicon_builder.word_sense_nsm_molecules import inherited

        warrant = origin.get("warrant") or {}
        entries = [e for e in warrant.get("entries") or [] if e.startswith("wordnet:")]
        bad = [e for e in entries if inherited(e.rsplit(":", 1)[1]).get(bank, (None,))[0] != value]
        return None if entries and not bad else f"NSM molecule inheritance does not give it: {bad[:3] or 'none named'}"
    if kind == "rules":
        rules = origin.get("rules") or []
        unknown = [r for r in rules if r not in admitted]
        return None if rules and not unknown else f"rules not admitted: {unknown or 'none named'}"
    return f"no warrant of an allowed kind: {origin!r}"


@pytest.mark.skipif(not CANDIDATE, reason="set GSE_SENSE_CANDIDATE to a built candidate")
def test_every_value_in_the_word_senses_has_a_warrant():
    conn = sqlite3.connect(Path(CANDIDATE).as_uri() + "?mode=ro", uri=True)
    admitted = _admitted_rules(conn)
    closure = _closure_records(conn)
    domains = {entry: json.loads(d) for entry, d in conn.execute("SELECT entry_id, domains FROM definition_states")}
    votes = {
        lemma: json.loads(record)["votes"]
        for lemma, record in conn.execute("SELECT lemma, agreement FROM word_source_agreement")
    }
    failures, checked = [], 0
    for lemma, pos, sense, assignments, provenance in conn.execute(
        "SELECT lemma, pos, sense, assignments, provenance FROM word_senses"
    ):
        provenance = json.loads(provenance)
        for bank, value in json.loads(assignments).items():
            checked += 1
            reason = _unwarranted(value, provenance.get(bank), domains, votes.get(lemma, {}), admitted, bank, closure)
            if reason:
                failures.append(f"{lemma}/{pos}/{sense} {bank}={value}: {reason}")
    assert checked > 0
    assert not failures, f"{len(failures)} of {checked} values have no warrant, e.g.\n" + "\n".join(failures[:20])
