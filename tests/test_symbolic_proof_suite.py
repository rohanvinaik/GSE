"""Pytest wrapper for the symbolic proof suite (Phase B7).

Runs the suite from GSE.verification.symbolic_proof_suite once at module
level, then asserts each individual proof passed. Failures are reported
per-proof so test output identifies the specific architectural claim
that broke.
"""

import pytest

from GSE.api import GSEEncoder
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.storage import open_build, store_entry
from GSE.verification import symbolic_proof_suite as proofs
from GSE.verification.symbolic_proof_suite import PROOFS, run_all


def geometry_dictionary(path, *, mode="selected"):
    """Synthetic coordinates isolate proof mechanics; these are not lexical gold."""
    conn = open_build(path)
    try:
        for word, bank, value in (("big", "BIG", 1), ("small", "BIG", -1), ("love", "GOOD", 1), ("hate", "GOOD", 1)):
            if mode == "absent" and word == "big":
                continue
            if mode == "zero" and word == "big":
                value = 0
            if mode == "non_evaluation" and word == "big":
                bank = "FEEL"
            if mode == "counterexample" and word == "small":
                value = 1
            values = {} if mode == "unknown" and word == "big" else {bank: value}
            for suffix in ("one", "two") if mode == "ambiguous" and word == "big" else ("one",):
                entry = f"fixture:{word}:{suffix}"
                assertions = tuple(Assertion(key, val, "fixture", entry, "dictionary") for key, val in values.items())
                store_entry(
                    conn,
                    Definition(entry, word, "a", "synthetic geometry fixture"),
                    propagate((bank,), assertions, ()),
                    assertions,
                )
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    path = geometry_dictionary(tmp_path_factory.mktemp("symbolic-proof") / "fixture.db")
    with GSEEncoder(path) as encoder:
        return run_all(encoder)


@pytest.mark.parametrize("proof_fn", PROOFS, ids=[p.__name__ for p in PROOFS])
def test_proof_passes(suite, proof_fn):
    # Find the result for this proof by matching the function name to the
    # ProofResult.name (which we ensure mirrors the function name minus "proof_").
    expected_name = proof_fn.__name__[len("proof_") :]
    matches = [r for r in suite.results if r.name == expected_name]
    assert len(matches) == 1, f"Couldn't locate result for {proof_fn.__name__}"
    result = matches[0]
    assert result.passed, f"Proof {result.name!r} failed: {result.description}\ndetail: {result.detail}"


def test_suite_runs_all_proofs(suite):
    assert suite.n_total == len(PROOFS)


def test_full_suite_passes(suite):
    # Explicit synthetic geometry validates the mechanism, not the quality or
    # completeness of whichever production dictionary is currently active.
    assert suite.n_passed == suite.n_total, (
        f"{suite.n_total - suite.n_passed} of {suite.n_total} proofs failed; "
        f"failed: {[r.name for r in suite.results if not r.passed]}"
    )


@pytest.mark.parametrize("mode", ["absent", "ambiguous", "zero", "unknown", "non_evaluation"])
def test_missing_selected_evaluation_evidence_abstains_before_cosine(tmp_path, monkeypatch, mode):
    path = geometry_dictionary(tmp_path / "fixture.db", mode=mode)
    with GSEEncoder(path) as encoder:
        # Produce real traces first: encoder activation diagnostics themselves
        # use cosine. The proof's comparison must not run on these traces.
        traces = {word: encoder.encode(word) for word in ("big", "small", "love", "hate")}
        monkeypatch.setattr(encoder, "encode", traces.__getitem__)
        vector_class = type(encoder.word_basis.get_primitive("GOOD"))

        def forbidden_cosine(*args, **kwargs):
            raise AssertionError("Undefined lexical comparison must not compute cosine")

        monkeypatch.setattr(vector_class, "cosine", forbidden_cosine)
        result = proofs.proof_bipolar_distinct_from_relational(encoder)
    assert result.code == "ABSTAINED"
    assert result.passed is False
    assert "LEXICAL_SELECTION_UNAVAILABLE" in result.detail or "EMPTY_EVALUATION_BANK" in result.detail


def test_selected_nonzero_counterexample_is_failure_not_abstention(tmp_path):
    with GSEEncoder(geometry_dictionary(tmp_path / "fixture.db", mode="counterexample")) as encoder:
        result = proofs.proof_bipolar_distinct_from_relational(encoder)
    assert result.code == "FAILED"
    assert result.passed is False
    assert "big/small EVAL=1.000" in result.detail


@pytest.mark.parametrize("mode,status", [("selected", 0), ("absent", 2), ("counterexample", 1)])
def test_cli_distinguishes_success_failure_and_abstention(tmp_path, monkeypatch, capsys, mode, status):
    path = geometry_dictionary(tmp_path / "fixture.db", mode=mode)
    real_encoder = GSEEncoder
    with real_encoder(path) as encoder:
        monkeypatch.setattr(proofs, "GSEEncoder", lambda: encoder)
        monkeypatch.setattr(proofs, "PROOFS", [proofs.proof_bipolar_distinct_from_relational])
        assert proofs.main() == status
    output = capsys.readouterr().out
    expected = {0: "PASSED", 1: "FAILED", 2: "ABSTAINED"}[status]
    assert f"[{expected}]" in output


def test_result_compatibility_and_aggregate_counts_do_not_merge_abstention_with_failure(monkeypatch):
    results = proofs.ProofSuiteResult(
        [
            proofs.ProofResult("pass", True, "selected proof"),
            proofs.ProofResult("fail", False, "counterexample"),
            proofs.ProofResult("unknown", False, "missing evidence", code="ABSTAINED"),
        ]
    )
    assert results.n_passed == results.n_failed == results.n_abstained == 1
    assert results.n_total == 3
    monkeypatch.setattr(proofs, "run_all", lambda: results)
    assert proofs.main() == 1
    with pytest.raises(ValueError, match="INVALID_PROOF_DECISION"):
        proofs.ProofResult("bad", True, "cannot call abstention passed", code="ABSTAINED")
