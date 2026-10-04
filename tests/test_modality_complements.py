"""An attitude verb's clausal complement is a belief whatever clause kind it is bound as (#125).

assertion_mode keeps its clause kinds as a literal so gse.symbolic.modality stays import-free and pinnable; this holds
the literal equal to the predicate registry, so a new predicate kind cannot escape the belief discipline unnoticed.
"""

import pytest

from gse.symbolic.modality import _CLAUSAL_COMPLEMENT_KINDS, assertion_mode
from gse.symbolic.predicates import OPERAND_FIELDS


def test_every_clause_kind_is_a_clausal_complement():
    assert frozenset(OPERAND_FIELDS) | {"Negation"} == _CLAUSAL_COMPLEMENT_KINDS


@pytest.mark.parametrize("kind", ["Negation", "Control", "RelativeRestriction", "Comparison", "Conditional"])
def test_a_clause_under_an_attitude_verb_is_a_belief(kind):
    assert assertion_mode("Event", "believe", kind) == "belief"


@pytest.mark.parametrize("patient", ["Entity", "Atom", "Phrase", "Coordination", "NoneType", ""])
def test_a_thing_under_an_attitude_verb_is_no_complement(patient):
    # "believes the story" takes an object, not a clause: the attitude event is asserted as usual.
    assert assertion_mode("Event", "believe", patient) == "asserted"
