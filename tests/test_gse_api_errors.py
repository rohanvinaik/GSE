"""Manual contract tests for gse.api.errors.

LintGate classified these 5 exception class __init__ methods as
manual_contract (routing decision: trivial wrappers with no auto-generatable
oracle values). Each test exercises the constructor and verifies the
attribute storage + formatted message.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.api.errors import (
    DecodingError,
    EncodingError,
    GSEError,
    OOVError,
    OperatorError,
    PrimitiveError,
)


class TestOOVError:
    def test_inherits_from_gse_error(self):
        assert issubclass(OOVError, GSEError)

    def test_stores_word_attribute(self):
        err = OOVError("foobar")
        assert err.word == "foobar"

    def test_message_contains_word(self):
        err = OOVError("zxqv")
        assert "zxqv" in str(err)

    def test_message_format(self):
        err = OOVError("widget")
        assert str(err) == "Out-of-vocabulary word: 'widget'"

    def test_raisable(self):
        with pytest.raises(OOVError) as exc_info:
            raise OOVError("missing")
        assert exc_info.value.word == "missing"

    def test_catchable_as_gse_error(self):
        with pytest.raises(GSEError):
            raise OOVError("x")


class TestEncodingError:
    def test_inherits_from_gse_error(self):
        assert issubclass(EncodingError, GSEError)

    def test_stores_text_and_reason(self):
        err = EncodingError("the cat", "out of memory")
        assert err.text == "the cat"
        assert err.reason == "out of memory"

    def test_message_contains_text_and_reason(self):
        err = EncodingError("hello world", "tokenizer failed")
        msg = str(err)
        assert "hello world" in msg
        assert "tokenizer failed" in msg

    def test_message_truncates_long_text(self):
        long_text = "x" * 200
        err = EncodingError(long_text, "bad")
        msg = str(err)
        # The formatter slices text[:50]
        assert "x" * 50 in msg
        # Ensure full 200-char text isn't dumped
        assert "x" * 200 not in msg

    def test_raisable(self):
        with pytest.raises(EncodingError) as exc_info:
            raise EncodingError("input", "why")
        assert exc_info.value.text == "input"
        assert exc_info.value.reason == "why"


class TestPrimitiveError:
    def test_inherits_from_gse_error(self):
        assert issubclass(PrimitiveError, GSEError)

    def test_stores_primitive_attribute(self):
        err = PrimitiveError("NONEXISTENT")
        assert err.primitive == "NONEXISTENT"

    def test_message_contains_primitive(self):
        err = PrimitiveError("FAKE_PRIM")
        assert "FAKE_PRIM" in str(err)

    def test_message_format(self):
        err = PrimitiveError("BOGUS")
        assert str(err) == "Invalid primitive: 'BOGUS'"

    def test_raisable(self):
        with pytest.raises(PrimitiveError) as exc_info:
            raise PrimitiveError("BAD")
        assert exc_info.value.primitive == "BAD"


class TestOperatorError:
    def test_inherits_from_gse_error(self):
        assert issubclass(OperatorError, GSEError)

    def test_stores_operator_and_reason(self):
        err = OperatorError("COMP_THAN", "missing arg2")
        assert err.operator == "COMP_THAN"
        assert err.reason == "missing arg2"

    def test_message_contains_operator_and_reason(self):
        err = OperatorError("COMP_BUT", "arity mismatch")
        msg = str(err)
        assert "COMP_BUT" in msg
        assert "arity mismatch" in msg

    def test_raisable(self):
        with pytest.raises(OperatorError) as exc_info:
            raise OperatorError("OP", "why")
        assert exc_info.value.operator == "OP"
        assert exc_info.value.reason == "why"


class TestDecodingError:
    def test_inherits_from_gse_error(self):
        assert issubclass(DecodingError, GSEError)

    def test_stores_reason_attribute(self):
        err = DecodingError("vector too sparse")
        assert err.reason == "vector too sparse"

    def test_message_contains_reason(self):
        err = DecodingError("ambiguous primitive")
        assert "ambiguous primitive" in str(err)

    def test_message_format(self):
        err = DecodingError("low confidence")
        assert str(err) == "Decoding failed: low confidence"

    def test_raisable(self):
        with pytest.raises(DecodingError) as exc_info:
            raise DecodingError("bad vec")
        assert exc_info.value.reason == "bad vec"


class TestGSEErrorBase:
    def test_is_exception_subclass(self):
        assert issubclass(GSEError, Exception)

    def test_all_subclasses_catchable_as_gse_error(self):
        subclasses = [
            OOVError("w"),
            EncodingError("t", "r"),
            PrimitiveError("p"),
            OperatorError("op", "r"),
            DecodingError("r"),
        ]
        for err in subclasses:
            with pytest.raises(GSEError):
                raise err


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
