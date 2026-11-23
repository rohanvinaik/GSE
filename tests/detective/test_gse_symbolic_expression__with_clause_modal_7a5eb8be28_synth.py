"""Preserved Detective modality witness, adapted to Atom's degree fields.

Typed equality checks the complete expression, including empty default degree
metadata, without tying the behavioral witness to dataclass repr formatting.
This adaptation is an ordinary regression test, not a fresh mutation receipt.
"""

import pytest

from GSE.api.trace import TokenTrace
from GSE.symbolic.expression import Atom, Op, _with_clause_modal


@pytest.mark.detective
def test__with_clause_modal_value_0():
    """VALUE survivor — distinguishing witness (equivalence search)."""
    result = _with_clause_modal(
        expr=Op(
            primitive="COPULA",
            operation="TYPE_ASSERT",
            arity=2,
            args=[
                Atom(
                    lemma="it",
                    word_primitives={},
                    role=None,
                    position=0,
                    pos=None,
                    number=None,
                    graded=False,
                    apposition=None,
                ),
                Atom(
                    lemma="dog",
                    word_primitives={},
                    role=None,
                    position=0,
                    pos=None,
                    number=None,
                    graded=False,
                    apposition=None,
                ),
            ],
            modal=(),
        ),
        tokens=[
            TokenTrace(
                token="it",
                lemma="it",
                pos="PRON",
                position=0,
                word_primitives={"SOMETHING": 1},
                sent_primitives={},
                word_vec_nnz=0,
                sent_vec_nnz=0,
                full_vec_nnz=0,
                is_operator=False,
                comp_primitive=None,
                comp_operation=None,
                comp_arity=0,
            ),
            TokenTrace(
                token="might",
                lemma="might",
                pos="AUX",
                position=1,
                word_primitives={"MAYBE": 1},
                sent_primitives={},
                word_vec_nnz=0,
                sent_vec_nnz=0,
                full_vec_nnz=0,
                is_operator=False,
                comp_primitive=None,
                comp_operation=None,
                comp_arity=0,
            ),
            TokenTrace(
                token="be",
                lemma="be",
                pos="AUX",
                position=2,
                word_primitives={"BE": 1},
                sent_primitives={},
                word_vec_nnz=0,
                sent_vec_nnz=0,
                full_vec_nnz=0,
                is_operator=False,
                comp_primitive=None,
                comp_operation=None,
                comp_arity=0,
            ),
        ],
    )
    assert result == Op(
        primitive="COPULA",
        operation="TYPE_ASSERT",
        arity=2,
        args=[Atom(lemma="it"), Atom(lemma="dog")],
        modal=("MAYBE",),
    )
