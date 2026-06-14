"""Per-operator COMP_* trace verification.

Phase A of the COMP_* integration work (per sentence_architecture.md
lines 141-148, 164). Asserts that every compositional operator
declared in :data:`COMP_METADATA` produces a correctly-labeled
``OperatorTrace`` when the encoder sees the operator's English form.

This test does NOT implement the set-theory semantics (SET_DIFF,
BIND_EQ, CAUSAL_SOURCE, ...). Per the architecture document line 164,
those operations live in a symbolic Python layer that reads the trace,
not in the HDC vector math. This test verifies the trace metadata
itself flows through correctly — operator name, operation label, arity.

When this test fails, the failure mode tells you which layer is broken:

* "NO operator with primitive=COMP_X" — the lexicon lookup or the
  pipeline's operator detection didn't fire. Most likely cause: the
  ``comp_primitive`` column in ``lexemes`` is NULL for that lemma.
* Wrong ``operation`` label — the COMP_METADATA → encoder propagation
  broke between primitives_v2.py and the encoder.
* Wrong ``arity`` — same wiring issue, different field.
"""

import pytest

from gse.api import GSEEncoder
from gse.primitives_v2 import COMP_METADATA

# Representative sentence + the operator it should activate.
# Lemma forms are drawn directly from COMP_METADATA keys; sentences are
# minimal so the operator's role is unambiguous to spaCy.
COMP_CASES = [
    ("Mike is taller than Rex",         "COMP_THAN"),
    ("Mike is tall as Rex",             "COMP_AS"),
    ("How tall is Mike?",               "COMP_HOW"),
    ("What is Mike?",                   "COMP_WHAT"),
    ("Mike has just enough food",       "COMP_JUST"),
    ("Only Mike sings",                 "COMP_ONLY"),
    ("Even Mike sings",                 "COMP_EVEN"),
    ("Mike sings but Rex runs",         "COMP_BUT"),
    ("Mike sang so Rex left",           "COMP_SO"),
    ("Mike left because Rex sang",      "COMP_BECAUSE"),
]


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


class TestCompMetadataCoverage:
    """Sanity check: COMP_METADATA covers exactly the 10 cases we test."""

    def test_all_metadata_entries_have_test_case(self):
        tested = {expected for _, expected in COMP_CASES}
        declared = set(COMP_METADATA.keys())
        missing = declared - tested
        assert not missing, (
            f"COMP_METADATA declares operators with no Phase A test case: {missing}"
        )

    def test_no_test_case_for_unknown_operator(self):
        tested = {expected for _, expected in COMP_CASES}
        declared = set(COMP_METADATA.keys())
        extra = tested - declared
        assert not extra, (
            f"Phase A test cases reference operators not in COMP_METADATA: {extra}"
        )


class TestOperatorTracePerComp:
    """For each COMP_* operator, the encoder produces an OperatorTrace
    with the right primitive, operation label, and arity."""

    @pytest.mark.parametrize(
        "sentence,expected_primitive",
        COMP_CASES,
        ids=[op for _, op in COMP_CASES],
    )
    def test_trace_records_correct_operator(
        self, encoder, sentence, expected_primitive
    ):
        trace = encoder.encode(sentence)
        ops = [op for op in trace.operators if op.primitive == expected_primitive]
        assert ops, (
            f"No OperatorTrace with primitive={expected_primitive!r} for "
            f"{sentence!r}. Encoder produced {len(trace.operators)} operators "
            f"in total: {[o.primitive for o in trace.operators]}."
        )

    @pytest.mark.parametrize(
        "sentence,expected_primitive",
        COMP_CASES,
        ids=[op for _, op in COMP_CASES],
    )
    def test_trace_records_correct_operation_label(
        self, encoder, sentence, expected_primitive
    ):
        trace = encoder.encode(sentence)
        ops = [op for op in trace.operators if op.primitive == expected_primitive]
        if not ops:
            pytest.skip("operator not detected — covered by separate test")
        expected_operation = COMP_METADATA[expected_primitive]["operation"]
        actual = ops[0].operation
        assert actual == expected_operation, (
            f"{expected_primitive}: trace.operation={actual!r}, "
            f"expected {expected_operation!r} per COMP_METADATA"
        )

    @pytest.mark.parametrize(
        "sentence,expected_primitive",
        COMP_CASES,
        ids=[op for _, op in COMP_CASES],
    )
    def test_trace_records_correct_arity(
        self, encoder, sentence, expected_primitive
    ):
        trace = encoder.encode(sentence)
        ops = [op for op in trace.operators if op.primitive == expected_primitive]
        if not ops:
            pytest.skip("operator not detected — covered by separate test")
        expected_arity = COMP_METADATA[expected_primitive]["arity"]
        actual = ops[0].arity
        assert actual == expected_arity, (
            f"{expected_primitive}: trace.arity={actual}, "
            f"expected {expected_arity} per COMP_METADATA"
        )
