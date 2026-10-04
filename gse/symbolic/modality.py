"""
Assertion modality — what a predicate tree ASSERTS, as distinct from what it only mentions.

A clause tree holds more than its facts. A negated clause holds with inverted polarity; a
conditional's clauses hold only under each other; a propositional-attitude verb's clausal
complement is the believer's belief; an irrealis control verb's inner act is negated or
unasserted. Every consumer that turns a tree into facts must apply the SAME discipline, so the
decision lives here, once, and both :mod:`gse.symbolic.narrative` (the story skeleton) and
:mod:`gse.symbolic.inference` (the knowledge base) consume it (#7). Each consumer maps the named
mode to its own action — the skeleton still records a conditional's clauses as story content;
the knowledge base records a rule and asserts neither.
"""

from __future__ import annotations

# Propositional-attitude verbs: they take a CLAUSAL complement ("believes that he is righteous"),
# which the parser binds as Event(believe; agent, <nested predicate>). That complement is the agent's
# BELIEF, not a fact — so it is surfaced as a THEME of the attitude event (kept attributed to the
# believer), never yielded as a standalone assertion. This is what lets the V1 self-deception read
# fire (believes v ∧ deeds betray v → betrays v), without asserting the belief as true.
ATTITUDE_VERBS = frozenset(
    {
        "believe",
        "think",
        "know",
        "suspect",
        "doubt",
        "realize",
        "realise",
        "understand",
        "imagine",
        "suppose",
        "assume",
        "expect",
        "fear",
        "hope",
        "feel",
        "perceive",
        "consider",
        "conclude",
        "deem",
        "fancy",
        "reckon",
    }
)
# IRREALIS control matrices: the controlled INNER act is not a fact and must never be yielded
# as a standalone assertion (the same discipline as ATTITUDE_VERBS' clausal complement and the
# Negation non-container). Two closed classes (Karttunen's implicative-verb taxonomy):
#   negative-implicative — the matrix ASSERTS the inner act did NOT happen ("Mordecai REFUSES to
#   bow" was emitting a bare `mordecai —bow→`, the polarity-inverted fact);
#   non-factive/desiderative — the matrix leaves the inner act unasserted ("Haman PLOTS to kill
#   all the Jews" was emitting a bare kill). The MATRIX edge (refuse/plot, from_document's Control
#   branch) still carries the story signal. Positive implicatives (manage, dare) and narrative-
#   completive matrices (persuade, order, force — the story convention asserts the caused act)
#   keep the inner act.
IRREALIS_CONTROL_VERBS = frozenset(
    {
        # negative implicative
        "refuse",
        "decline",
        "fail",
        "forbid",
        "prevent",
        "avoid",
        "resist",
        "neglect",
        "omit",
        # non-factive / desiderative / conative
        "plot",
        "plan",
        "attempt",
        "try",
        "want",
        "wish",
        "hope",
        "intend",
        "seek",
        "aim",
        "scheme",
        "conspire",
        "threaten",
        "propose",
        "aspire",
        "yearn",
        "long",
    }
)

# The node types an attitude verb's clausal complement can be bound as (the Event's patient): every clause-level
# predicate kind and a negated clause. Under "believes that ..." each is the believer's belief, not a fact. The set
# once held only TypeAssertion and Event, so "believes that Banquo did not see him" asserted not-see, and a Control or
# RelativeRestriction complement asserted its content (#125). It is a literal so this module stays import-free and
# pinnable; tests/test_modality_complements.py holds it equal to gse.symbolic.predicates.OPERAND_FIELDS plus Negation.
_CLAUSAL_COMPLEMENT_KINDS = frozenset(
    {
        "BoundaryCase",
        "Causation",
        "ClauseCoordination",
        "Comparison",
        "Conditional",
        "Contrast",
        "Control",
        "DegreeQuery",
        "Equality",
        "Event",
        "MinimalSufficiency",
        "Negation",
        "RelativeRestriction",
        "SetRestriction",
        "Temporal",
        "TypeAssertion",
        "TypeQuery",
    }
)


def assertion_mode(kind: str, verb: str = "", patient_kind: str = "") -> str:
    """How a predicate-tree node asserts its clausal content (#7, pure — pinned).

    Split out of the tree walkers so the decision is total over plain strings and pinnable: a
    walker passes the node's type name, its ``verb`` and its patient's type name, and keeps the
    object handling. Before the split, the knowledge base had no copy of this decision at all and
    the story skeleton held two inline copies of half of it.

    Returns a named code, never a bool, because each mode needs a different remedy:

    * ``"negated"`` — a ``Negation``: its operand holds with inverted polarity, never as stated.
    * ``"conditional"`` — a ``Conditional``: the consequent holds only if the antecedent does;
      neither clause is asserted on its own.
    * ``"belief"`` — an attitude ``Event`` over a clausal complement ("believes that X"): the
      patient is the agent's belief, not a fact; the attitude itself is asserted.
    * ``"irrealis"`` — a ``Control`` under an irrealis matrix ("refused to bow", "plots to
      kill"): the inner act is negated or unasserted; the matrix itself is asserted.
    * ``"asserted"`` — anything else: its operand content holds as stated.
    """
    if kind == "Negation":
        return "negated"
    if kind == "Conditional":
        return "conditional"
    if kind == "Event" and verb in ATTITUDE_VERBS and patient_kind in _CLAUSAL_COMPLEMENT_KINDS:
        return "belief"
    if kind == "Control" and verb in IRREALIS_CONTROL_VERBS:
        return "irrealis"
    return "asserted"
