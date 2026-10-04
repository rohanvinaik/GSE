"""Pytest wrapper for the symbolic proof suite (Phase B7).

Runs the suite from gse.verification.symbolic_proof_suite once at module
level, then asserts each individual proof passed. Failures are reported
per-proof so test output identifies the specific architectural claim
that broke.
"""

import pytest

from gse.api import GSEEncoder
from gse.verification.symbolic_proof_suite import PROOFS, run_all


@pytest.fixture(scope="module")
def suite():
    encoder = GSEEncoder()
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
    # Bottom-line: the full set of architecture-document line 154
    # validation queries succeed end-to-end against the live encoder.
    assert suite.n_passed == suite.n_total, (
        f"{suite.n_total - suite.n_passed} of {suite.n_total} proofs failed; "
        f"failed: {[r.name for r in suite.results if not r.passed]}"
    )
