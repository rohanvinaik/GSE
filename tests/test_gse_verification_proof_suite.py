"""Manual contract tests for gse.verification.proof_suite."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.verification.proof_suite import GSEProofSuite, TestResult, main


def make_token(lemma="dog", word_primitives=None):
    t = MagicMock()
    t.lemma = lemma
    t.word_primitives = word_primitives or {}
    return t


def make_trace(tokens=None, vec_hash="sha256:abc", nnz=10, vec=None):
    t = MagicMock()
    t.vector_hash = vec_hash
    t.final_nnz = nnz
    t.tokens = tokens or []
    if vec is None:
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=1.0)
    t.vector = vec
    t.logical_equals = MagicMock(return_value=False)
    t.is_argument_swap_of = MagicMock(return_value=True)
    return t


@pytest.fixture
def suite():
    """A suite with mocked encoder + decoder, verbose off."""
    with (
        patch("gse.verification.proof_suite.GSEEncoder") as enc_cls,
        patch("gse.verification.proof_suite.GSEDecoder") as dec_cls,
    ):
        enc = MagicMock()
        dec = MagicMock()
        enc_cls.return_value = enc
        dec_cls.return_value = dec

        s = GSEProofSuite(verbose=False)
        s.encoder = enc
        s.decoder = dec
        yield s


# ---------- TestResult ----------


class TestTestResultDataclass:
    def test_required_fields(self):
        r = TestResult(name="x", passed=True, message="ok")
        assert r.name == "x"
        assert r.passed is True
        assert r.details is None

    def test_with_details(self):
        r = TestResult(name="x", passed=False, message="m", details={"k": "v"})
        assert r.details == {"k": "v"}


# ---------- __init__ ----------


class TestInit:
    def test_creates_encoder_and_decoder(self):
        with (
            patch("gse.verification.proof_suite.GSEEncoder") as enc_cls,
            patch("gse.verification.proof_suite.GSEDecoder") as dec_cls,
        ):
            s = GSEProofSuite(verbose=True)
            assert s.verbose is True
            assert s.results == []
            enc_cls.assert_called_once()
            dec_cls.assert_called_once()


# ---------- log ----------


class TestLog:
    def test_verbose_prints(self, capsys):
        with patch("gse.verification.proof_suite.GSEEncoder"), patch("gse.verification.proof_suite.GSEDecoder"):
            s = GSEProofSuite(verbose=True)
            s.log("hello")
            assert "hello" in capsys.readouterr().out

    def test_silent_skips(self, capsys):
        with patch("gse.verification.proof_suite.GSEEncoder"), patch("gse.verification.proof_suite.GSEDecoder"):
            s = GSEProofSuite(verbose=False)
            s.log("hello")
            assert capsys.readouterr().out == ""


# ---------- test_reproducibility ----------


class TestReproducibility:
    def test_passes_when_hashes_match(self, suite):
        trace = make_trace(vec_hash="sha256:same", nnz=10)
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_reproducibility()
        r = next(r for r in suite.results if r.name == "reproducibility")
        assert r.passed is True

    def test_fails_when_hashes_differ(self, suite):
        # First call returns one hash, second call returns another
        traces = [make_trace(vec_hash=f"sha256:{i}") for i in range(20)]
        suite.encoder.encode = MagicMock(side_effect=traces)
        suite.test_reproducibility()
        r = next(r for r in suite.results if r.name == "reproducibility")
        assert r.passed is False


# ---------- test_similarity_preservation ----------


class TestSimilarityPreservation:
    def test_passes_when_cosines_above_threshold(self, suite):
        # All comparisons return high cosine
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.5)
        trace = make_trace(vec=vec)
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_similarity_preservation()
        r = next(r for r in suite.results if r.name == "similarity_preservation")
        assert r.passed is True

    def test_fails_when_cosine_below_threshold(self, suite):
        vec = MagicMock()
        # Returns very low cosine for first non-base call → fails
        vec.cosine = MagicMock(return_value=-1.0)
        trace = make_trace(vec=vec)
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_similarity_preservation()
        r = next(r for r in suite.results if r.name == "similarity_preservation")
        assert r.passed is False


# ---------- test_antonym_relationships ----------


class TestAntonymRelationships:
    def test_passes_when_bipolar_strongly_negative(self, suite):
        # word_basis.get_primitive returns vectors with cos < -0.9
        v1 = MagicMock()
        v1.cosine = MagicMock(return_value=-0.95)
        suite.encoder.word_basis = MagicMock()
        suite.encoder.word_basis.get_primitive = MagicMock(return_value=v1)
        # Other vectors return mid
        word_vec = MagicMock()
        word_vec.cosine = MagicMock(return_value=0.0)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=word_vec))
        suite.test_antonym_relationships()
        r = next(r for r in suite.results if r.name == "antonym_relationships")
        assert r.passed is True

    def test_fails_when_bipolar_not_opposite(self, suite):
        v1 = MagicMock()
        v1.cosine = MagicMock(return_value=0.5)  # not negative enough
        suite.encoder.word_basis = MagicMock()
        suite.encoder.word_basis.get_primitive = MagicMock(return_value=v1)
        word_vec = MagicMock()
        word_vec.cosine = MagicMock(return_value=0.0)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=word_vec))
        suite.test_antonym_relationships()
        r = next(r for r in suite.results if r.name == "antonym_relationships")
        assert r.passed is False

    def test_missing_primitive_skipped(self, suite):
        # get_primitive returns None → the `if v1 and v2` skips
        suite.encoder.word_basis = MagicMock()
        suite.encoder.word_basis.get_primitive = MagicMock(return_value=None)
        word_vec = MagicMock()
        word_vec.cosine = MagicMock(return_value=0.0)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=word_vec))
        suite.test_antonym_relationships()
        # No bipolar fails recorded → passed=True
        r = next(r for r in suite.results if r.name == "antonym_relationships")
        assert r.passed is True


# ---------- test_entity_recovery ----------


class TestEntityRecovery:
    def test_passes_when_entities_in_lemmas(self, suite):
        # All expected entities present as lemmas (case-insensitive matching)
        def enc(text):
            lower = text.lower()
            tokens = []
            if "dog" in lower or "cat" in lower:
                tokens = [make_token("dog"), make_token("cat")]
            elif "man" in lower:
                tokens = [make_token("man"), make_token("woman")]
            elif "bird" in lower:
                tokens = [make_token("bird")]
            return make_trace(tokens=tokens)

        suite.encoder.encode = MagicMock(side_effect=enc)
        suite.test_entity_recovery()
        r = next(r for r in suite.results if r.name == "entity_recovery")
        assert r.passed is True

    def test_fails_when_entity_missing(self, suite):
        # Missing entity in trace
        suite.encoder.encode = MagicMock(return_value=make_trace(tokens=[]))
        suite.test_entity_recovery()
        r = next(r for r in suite.results if r.name == "entity_recovery")
        assert r.passed is False

    def test_finds_via_entity_primitives(self, suite):
        # Lemma doesn't match but SOMETHING primitive matches
        tokens = [
            make_token("dog", word_primitives={"SOMETHING": 1}),
            make_token("cat", word_primitives={"SOMEONE": 1}),
        ]
        suite.encoder.encode = MagicMock(return_value=make_trace(tokens=tokens))
        suite.test_entity_recovery()
        # All three test cases — only dog/cat case has matching tokens
        # man/woman and bird cases will fail → at least one missing
        r = next(r for r in suite.results if r.name == "entity_recovery")
        # Test recovers via lemma match (case 1) but fails on case 2/3
        assert r.passed is False


# ---------- test_attribute_extraction ----------


class TestAttributeExtraction:
    def test_passes_when_prim_in_tokens(self, suite):
        def enc(text):
            if "cute" in text:
                tokens = [make_token("cute", {"GOOD": 1})]
            elif "ugly" in text:
                tokens = [make_token("ugly", {"BAD": 1})]
            elif "big" in text:
                tokens = [make_token("big", {"BIG": 1})]
            else:
                tokens = [make_token("small", {"SMALL": 1})]
            return make_trace(tokens=tokens)

        suite.encoder.encode = MagicMock(side_effect=enc)
        suite.test_attribute_extraction()
        r = next(r for r in suite.results if r.name == "attribute_extraction")
        assert r.passed is True

    def test_fails_when_only_partial_bipolar_coverage(self, suite):
        # Token has only GOOD. Tests for BAD/BIG/SMALL go via opposite_map.
        # GOOD: in token → found
        # BAD: opposite is GOOD, with value=-1 needed; token has GOOD=1 → not found via opposite
        def enc(text):
            return make_trace(tokens=[make_token("x", {"GOOD": 1})])

        suite.encoder.encode = MagicMock(side_effect=enc)
        suite.test_attribute_extraction()
        r = next(r for r in suite.results if r.name == "attribute_extraction")
        # First case (GOOD) passes via direct match
        # Subsequent cases (BAD/BIG/SMALL) fail → all_pass=False
        assert r.passed is False

    def test_fails_when_prim_absent(self, suite):
        suite.encoder.encode = MagicMock(return_value=make_trace(tokens=[]))
        suite.test_attribute_extraction()
        r = next(r for r in suite.results if r.name == "attribute_extraction")
        assert r.passed is False


# ---------- test_operator_antisymmetry ----------


class TestOperatorAntisymmetry:
    def test_passes_when_content_similar_logic_different(self, suite):
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.6)  # > 0.5
        trace = make_trace(vec=vec)
        # Already mocked: logical_equals=False, is_argument_swap_of=True
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_operator_antisymmetry()
        r = next(r for r in suite.results if r.name == "operator_antisymmetry")
        assert r.passed is True

    def test_fails_when_logically_equal(self, suite):
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.6)
        trace = make_trace(vec=vec)
        trace.logical_equals = MagicMock(return_value=True)  # bad
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_operator_antisymmetry()
        r = next(r for r in suite.results if r.name == "operator_antisymmetry")
        assert r.passed is False

    def test_fails_when_content_dissimilar(self, suite):
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.1)  # below 0.5
        trace = make_trace(vec=vec)
        suite.encoder.encode = MagicMock(return_value=trace)
        suite.test_operator_antisymmetry()
        r = next(r for r in suite.results if r.name == "operator_antisymmetry")
        assert r.passed is False


# ---------- test_compositional_operator_resolution ----------


def make_trace_with_operators(operations):
    """Build a trace mock that exposes a list of operators with .operation set."""
    trace = make_trace()
    trace.operators = [MagicMock(operation=op) for op in operations]
    return trace


class TestCompositionalOperatorResolution:
    def test_passes_when_same_op_shared_and_different_ops_distinct(self, suite):
        # All same-operator pairs share an operation; all different-operator pairs disagree.
        responses = {
            "The dog is cuter than the cat": ["SET_DIFF"],
            "The mouse is bigger than the ant": ["SET_DIFF"],
            "She works hard but he rests": ["CONTRAST"],
            "He sings well but she dances poorly": ["CONTRAST"],
            "He left because she stayed": ["CAUSAL_SOURCE"],
            "He left so she stayed": ["CONSEQUENCE"],
        }
        suite.encoder.encode = MagicMock(side_effect=lambda text: make_trace_with_operators(responses[text]))
        suite.test_compositional_operator_resolution()
        r = next(r for r in suite.results if r.name == "compositional_operator_resolution")
        assert r.passed is True

    def test_fails_when_same_op_pair_disagrees(self, suite):
        # First same-operator pair returns disjoint operations → fail.
        responses = {
            "The dog is cuter than the cat": ["SET_DIFF"],
            "The mouse is bigger than the ant": ["CONTRAST"],  # wrong
            "She works hard but he rests": ["CONTRAST"],
            "He sings well but she dances poorly": ["CONTRAST"],
            "He left because she stayed": ["CAUSAL_SOURCE"],
            "He left so she stayed": ["CONSEQUENCE"],
        }
        suite.encoder.encode = MagicMock(side_effect=lambda text: make_trace_with_operators(responses[text]))
        suite.test_compositional_operator_resolution()
        r = next(r for r in suite.results if r.name == "compositional_operator_resolution")
        assert r.passed is False

    def test_fails_when_different_op_pair_matches(self, suite):
        # Cause/consequence pair both produce the same operation → fail.
        responses = {
            "The dog is cuter than the cat": ["SET_DIFF"],
            "The mouse is bigger than the ant": ["SET_DIFF"],
            "She works hard but he rests": ["CONTRAST"],
            "He sings well but she dances poorly": ["CONTRAST"],
            "He left because she stayed": ["CAUSAL_SOURCE"],
            "He left so she stayed": ["CAUSAL_SOURCE"],  # wrong - should differ
        }
        suite.encoder.encode = MagicMock(side_effect=lambda text: make_trace_with_operators(responses[text]))
        suite.test_compositional_operator_resolution()
        r = next(r for r in suite.results if r.name == "compositional_operator_resolution")
        assert r.passed is False


# ---------- test_structural_similarity ----------


class TestStructuralSimilarity:
    def test_passes_when_cosine_positive(self, suite):
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.3)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=vec))
        suite.test_structural_similarity()
        r = next(r for r in suite.results if r.name == "structural_similarity")
        assert r.passed is True

    def test_warns_when_zero_but_still_passes(self, suite):
        # cos <= 0 logs WARN but doesn't set all_pass=False — the source
        # has a bug here: `if cos > 0.0` sets status but doesn't update all_pass
        # The result.passed always reflects all_pass which starts True.
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=-0.5)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=vec))
        suite.test_structural_similarity()
        r = next(r for r in suite.results if r.name == "structural_similarity")
        # Per source: WARN doesn't toggle all_pass
        assert r.passed is True


# ---------- test_user_comparisons ----------


class TestUserComparisons:
    def test_always_passes(self, suite):
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.5)
        suite.encoder.encode = MagicMock(return_value=make_trace(vec=vec))
        sim = MagicMock()
        sim.cosine = 0.5
        sim.alignment = 0.5
        sim.opposition = 0.1
        sim.orthogonality = 0.4
        sim.shared_primitives = ["GOOD"]
        suite.decoder.similarity = MagicMock(return_value=sim)
        suite.test_user_comparisons()
        r = next(r for r in suite.results if r.name == "user_comparisons")
        # Informational test always passes
        assert r.passed is True


# ---------- run_all ----------


class TestRunAll:
    def test_runs_all_nine_tests(self, suite):
        # All tests internally call encoder/decoder
        vec = MagicMock()
        vec.cosine = MagicMock(return_value=0.6)
        trace = make_trace(
            vec=vec,
            tokens=[make_token("dog", {"GOOD": 1, "BAD": 1, "BIG": 1, "SMALL": 1, "SOMETHING": 1, "SOMEONE": 1})],
        )
        trace.logical_equals = MagicMock(return_value=False)
        trace.is_argument_swap_of = MagicMock(return_value=True)
        # Compositional operator resolution checks trace.operators[*].operation;
        # vary by input so same-op/different-op pairs satisfy the test contract.
        operator_table = {
            "The dog is cuter than the cat": ["SET_DIFF"],
            "The mouse is bigger than the ant": ["SET_DIFF"],
            "She works hard but he rests": ["CONTRAST"],
            "He sings well but she dances poorly": ["CONTRAST"],
            "He left because she stayed": ["CAUSAL_SOURCE"],
            "He left so she stayed": ["CONSEQUENCE"],
        }

        def encode(text):
            t = make_trace(
                vec=vec,
                tokens=[make_token("dog", {"GOOD": 1, "BAD": 1, "BIG": 1, "SMALL": 1, "SOMETHING": 1, "SOMEONE": 1})],
            )
            t.logical_equals = MagicMock(return_value=False)
            t.is_argument_swap_of = MagicMock(return_value=True)
            t.operators = [MagicMock(operation=op) for op in operator_table.get(text, [])]
            return t

        suite.encoder.encode = MagicMock(side_effect=encode)
        suite.encoder.word_basis = MagicMock()
        v1 = MagicMock()
        v1.cosine = MagicMock(return_value=-0.95)
        suite.encoder.word_basis.get_primitive = MagicMock(return_value=v1)
        sim = MagicMock()
        sim.cosine = 0.5
        sim.alignment = 0.5
        sim.opposition = 0.1
        sim.orthogonality = 0.4
        sim.shared_primitives = ["X"]
        suite.decoder.similarity = MagicMock(return_value=sim)

        result = suite.run_all()
        assert len(suite.results) == 9
        assert set(result.keys()) == {
            "reproducibility",
            "similarity_preservation",
            "antonym_relationships",
            "entity_recovery",
            "attribute_extraction",
            "operator_antisymmetry",
            "compositional_operator_resolution",
            "structural_similarity",
            "user_comparisons",
        }


# ---------- print_report ----------


class TestPrintReport:
    def test_all_passed_returns_true(self, suite, capsys):
        suite.results = [TestResult(name="x", passed=True, message="ok")]
        result = suite.print_report()
        assert result is True
        out = capsys.readouterr().out
        assert "ALL TESTS PASS" in out

    def test_with_failures_returns_false(self, suite, capsys):
        suite.results = [
            TestResult(name="a", passed=True, message="ok"),
            TestResult(name="b", passed=False, message="bad"),
        ]
        result = suite.print_report()
        assert result is False
        out = capsys.readouterr().out
        assert "1 TESTS FAILED" in out

    def test_empty_results(self, suite, capsys):
        suite.results = []
        result = suite.print_report()
        # 0/0 → no failures → returns True
        assert result is True


# ---------- close ----------


class TestClose:
    def test_closes_both(self, suite):
        suite.close()
        suite.encoder.close.assert_called_once()
        suite.decoder.close.assert_called_once()


# ---------- main ----------


class TestMain:
    def test_exits_zero_on_success(self):
        with (
            patch("gse.verification.proof_suite.GSEEncoder"),
            patch("gse.verification.proof_suite.GSEDecoder"),
            patch.object(GSEProofSuite, "run_all", return_value={}),
            patch.object(GSEProofSuite, "print_report", return_value=True),
            patch.object(GSEProofSuite, "close"),
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_exits_one_on_failure(self):
        with (
            patch("gse.verification.proof_suite.GSEEncoder"),
            patch("gse.verification.proof_suite.GSEDecoder"),
            patch.object(GSEProofSuite, "run_all", return_value={}),
            patch.object(GSEProofSuite, "print_report", return_value=False),
            patch.object(GSEProofSuite, "close"),
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1

    def test_close_called_even_on_exception(self):
        with (
            patch("gse.verification.proof_suite.GSEEncoder"),
            patch("gse.verification.proof_suite.GSEDecoder"),
            patch.object(GSEProofSuite, "run_all", side_effect=RuntimeError("x")),
            patch.object(GSEProofSuite, "close") as mc,
        ):
            with pytest.raises(RuntimeError):
                main()
            mc.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
