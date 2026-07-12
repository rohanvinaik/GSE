"""Phase B1 tests — AST node types + from_trace builder.

Verifies the structural transformation from OperationTrace into a typed
Expression tree. No semantics tested here (that's B2/B3).
"""

import pytest

from gse.api import GSEEncoder
from gse.api.parse_repair import verbs_to_promote
from gse.symbolic.expression import (
    Atom,
    Negation,
    Op,
    Phrase,
    _select_clause_verb,
    from_trace,
)
from gse.symbolic.operators import evaluate_tree


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


class TestAstNodes:
    """Smoke tests on the node dataclasses themselves."""

    def test_atom_holds_lemma_and_primitives(self):
        a = Atom(lemma="dog", word_primitives={"ALIVE": 1, "BODY": 1})
        assert a.lemma == "dog"
        assert a.word_primitives["ALIVE"] == 1

    def test_atom_is_hashable(self):
        # Frozen dataclass + custom __hash__
        a = Atom(lemma="dog", word_primitives={"ALIVE": 1})
        b = Atom(lemma="dog", word_primitives={"ALIVE": 1})
        assert hash(a) == hash(b)

    def test_phrase_carries_atom_list(self):
        p = Phrase(atoms=[Atom("a"), Atom("b")])
        assert len(p.atoms) == 2

    def test_negation_wraps_an_expression(self):
        n = Negation(operand=Atom("good"))
        assert isinstance(n.operand, Atom)
        assert n.operand.lemma == "good"

    def test_op_has_operation_and_args(self):
        a = Atom("dog")
        b = Atom("cat")
        op = Op(primitive="COMP_THAN", operation="SET_DIFF", arity=2, args=[a, b])
        assert op.operation == "SET_DIFF"
        assert op.arity == 2
        assert op.args == [a, b]


class TestFromTraceNoOperators:
    """Sentences without compositional operators should produce Atoms/Phrases."""

    def test_single_word_returns_atom(self, encoder):
        trace = encoder.encode("dog")
        expr = from_trace(trace)
        assert isinstance(expr, Atom)
        assert expr.lemma == "dog"

    def test_verb_clause_returns_event(self, encoder):
        # A plain verb clause now synthesizes an EVENT roleframe (the base-case
        # predicate), rather than collapsing to a bare Phrase.
        expr = from_trace(encoder.encode("the dog ran fast"))
        assert isinstance(expr, Op) and expr.operation == "EVENT"
        assert expr.primitive == "run"  # the verb lemma rides on Op.primitive

    def test_verbless_phrase_stays_phrase(self, encoder):
        # No verb and no operator → still a bare Phrase of its content atoms.
        expr = from_trace(encoder.encode("the big red ball"))
        assert isinstance(expr, Phrase)
        assert "ball" in {a.lemma for a in expr.atoms}


class TestFromTraceComparisonOperator:
    """A sentence with COMP_THAN should produce an Op node."""

    def test_than_lifts_to_set_diff_op(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        expr = from_trace(trace)
        assert isinstance(expr, Op)
        assert expr.primitive == "COMP_THAN"
        assert expr.operation == "SET_DIFF"
        assert expr.arity == 2
        assert len(expr.args) == 2

    def test_than_args_have_mike_and_rex(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        expr = from_trace(trace)
        assert isinstance(expr, Op)
        # Collect all lemmas across both args (handles Phrase or Atom)
        def _lemmas(e):
            if isinstance(e, Atom):
                return {e.lemma}
            if isinstance(e, Phrase):
                return {a.lemma for a in e.atoms}
            if isinstance(e, Negation):
                return _lemmas(e.operand)
            if isinstance(e, Op):
                out = set()
                for a in e.args:
                    out |= _lemmas(a)
                return out
            return set()

        all_lemmas = set()
        for a in expr.args:
            all_lemmas |= _lemmas(a)
        assert "mike" in all_lemmas
        assert "rex" in all_lemmas


class TestFromTraceAllCompOperators:
    """All 10 operators should lift cleanly with correct operation labels."""

    @pytest.mark.parametrize("sentence,expected_primitive,expected_operation,expected_arity", [
        ("Mike is taller than Rex",          "COMP_THAN",   "SET_DIFF",       2),
        ("Mike is tall as Rex",              "COMP_AS",     "BIND_EQ",        2),
        ("How tall is Mike?",                "COMP_HOW",    "DEGREE_QUERY",   1),
        ("What is Mike?",                    "COMP_WHAT",   "TYPE_QUERY",     1),
        ("Mike has just enough food",        "COMP_JUST",   "CARD_LOWER",     2),
        ("Only Mike sings",                  "COMP_ONLY",   "SET_RESTRICT",   1),
        ("Even Mike sings",                  "COMP_EVEN",   "SCALAR_EXTREME", 1),
        ("Mike sings but Rex runs",          "COMP_BUT",    "CONTRAST",       2),
        ("Mike sang so Rex left",            "COMP_SO",     "CONSEQUENCE",    2),
        ("Mike left because Rex sang",       "COMP_BECAUSE","CAUSAL_SOURCE",  2),
    ])
    def test_operator_lifts_with_correct_label(
        self, encoder, sentence, expected_primitive, expected_operation, expected_arity
    ):
        trace = encoder.encode(sentence)
        expr = from_trace(trace)
        # Find the Op in the AST (may be nested if there are multiple operators)
        op = _find_op(expr, expected_primitive)
        assert op is not None, (
            f"No Op({expected_primitive}) found in AST built from {sentence!r}"
        )
        assert op.operation == expected_operation
        assert op.arity == expected_arity


class TestFromTraceNegation:
    """Sentences with NOT should produce Negation nodes in the AST."""

    def test_not_run_wraps_run_atom_in_negation(self, encoder):
        # Test "He did not run" — encoder should pull NOT into arg span
        # of some operator, OR the bare phrase should include negation
        # at the top level.
        trace = encoder.encode("Mike did not run")
        expr = from_trace(trace)
        # No COMP_* operator here — should be a Phrase or a Negation
        assert _contains_negation(expr) or _contains_lemma(expr, "not"), (
            f"NOT not surfaced in AST for 'Mike did not run': {expr!r}"
        )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _find_op(expr, primitive_name):
    """Locate an Op node by primitive name anywhere in the tree."""
    if isinstance(expr, Op):
        if expr.primitive == primitive_name:
            return expr
        for a in expr.args:
            found = _find_op(a, primitive_name)
            if found is not None:
                return found
    elif isinstance(expr, Negation):
        return _find_op(expr.operand, primitive_name)
    return None


def _contains_negation(expr):
    if isinstance(expr, Negation):
        return True
    if isinstance(expr, Op):
        return any(_contains_negation(a) for a in expr.args)
    return False


def _contains_lemma(expr, lemma):
    if isinstance(expr, Atom):
        return expr.lemma == lemma
    if isinstance(expr, Phrase):
        return any(a.lemma == lemma for a in expr.atoms)
    if isinstance(expr, Negation):
        return _contains_lemma(expr.operand, lemma)
    if isinstance(expr, Op):
        return any(_contains_lemma(a, lemma) for a in expr.args)
    return False


def _agent_lemmas(ev):
    a = ev.agent
    return [t.lemma for t in a.atoms] if hasattr(a, "atoms") else [getattr(a, "lemma", a)]


def _theme_lemmas(ev):
    out = []
    for th in ev.themes:
        out += [t.lemma for t in th.atoms] if hasattr(th, "atoms") else [getattr(th, "lemma", th)]
    return out


class TestOfPostmodifierNamePreservation:
    """A genitive/territorial ``of``-postmodifier of a NAME / head-NOUN subject stays WITH the subject —
    it is not peeled off as a SYN_OBL (which ``event()`` would mis-read as a `theme`). Regression: a
    territorial-name subject ("Richard of Gloucester blames X", "Duncan of Scotland sees Y") used to leak
    the place-name as an EVENT arg2 theme. The fix is PRE-verb only; a real post-verb "of ⟨act⟩" complement
    still surfaces as a theme, and a non-``of`` fronted PP stays an oblique."""

    def test_propn_of_propn_subject_stays_whole_no_theme(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("Richard of Gloucester blames Queen Elizabeth.")))
        assert "gloucester" in _agent_lemmas(ev)     # kept in the subject name
        assert ev.themes == ()                       # NOT leaked as a theme

    def test_duncan_of_scotland_stays_whole_no_theme(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("Duncan of Scotland sees Macbeth.")))
        assert "scotland" in _agent_lemmas(ev)
        assert ev.themes == ()

    def test_noun_of_propn_subject_stays_whole(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("The son of Duncan killed Macbeth.")))
        assert "duncan" in _agent_lemmas(ev)
        assert ev.themes == ()

    def test_post_verb_of_complement_still_a_theme(self, encoder):
        # the fix is pre-verb only — a genuine imputed-act complement after the verb still becomes a theme.
        ev = evaluate_tree(from_trace(encoder.encode("Richard accuses Elizabeth of treason.")))
        assert "treason" in _theme_lemmas(ev)

    def test_non_of_fronted_pp_object_not_kept_in_the_name(self, encoder):
        # restricted to 'of': a fronted "in the daytime" PP object is NOT a name postmodifier.
        ev = evaluate_tree(from_trace(encoder.encode("In the daytime Macbeth ran.")))
        assert "daytime" not in _agent_lemmas(ev)


class TestLeadingAdjunctSubjectRecovery:
    """A LEADING ADJUNCT set off by a comma ("Angered by the insult, the king …") is NOT the subject — the
    real subject is the nominal after the comma. A capitalized sentence-initial participle ("Angered",
    "Consumed", "Exhausted") POS-tags as PROPN, indistinguishable from a proper-noun subject by tag, so the
    old subject-span pulled it into the agent ("angered by the king"). The fix keys on the COMMA (the fronted-
    adjunct boundary), guarded so a comma-separated LIST subject and a subject-initial appositive are left
    intact. Regression: leading participial/absolute phrases corrupted the agent across the corpus."""

    def test_participial_adjunct_dropped_real_subject_kept(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("Angered by the insult, the king banished the knight.")))
        assert "king" in _agent_lemmas(ev)           # the real subject survives
        assert "angered" not in _agent_lemmas(ev)    # the participial adjunct head no longer contaminates it

    def test_second_participial_adjunct(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("Exhausted from the long march, the soldier collapsed.")))
        assert "soldier" in _agent_lemmas(ev)
        assert "exhausted" not in _agent_lemmas(ev)

    def test_participial_adjunct_before_named_subject(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("Spurred by his wife, Macbeth killed the king.")))
        assert "macbeth" in _agent_lemmas(ev)
        assert "spurred" not in _agent_lemmas(ev)

    def test_list_subject_not_stripped(self, encoder):
        # GUARD: a comma-separated list subject has the coordinator AFTER the comma -> NOT a leading adjunct;
        # the whole list stays the subject (do not strip the first conjunct).
        ev = evaluate_tree(from_trace(encoder.encode("Tom, Dick and Harry ran home.")))
        assert "tom" in _agent_lemmas(ev)            # the first conjunct is not dropped

    def test_subject_initial_appositive_keeps_the_name(self, encoder):
        # GUARD: "NAME, description, verb" has NO nominal after its last comma -> this abstains and the
        # appositive path keeps the name; the leading-adjunct rule must not eat "Haemon".
        ev = evaluate_tree(from_trace(encoder.encode("Haemon, Creon son, pledged loyalty.")))
        assert "haemon" in _agent_lemmas(ev)

    def test_no_adjunct_subject_unchanged(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode("The king banished the knight.")))
        assert "king" in _agent_lemmas(ev)


class TestPossessiveNounNotPromotedToVerb:
    """A verb-sense NOUN governed by a possessive determiner ("his ambition", "her plan") is the possessed
    NOUN HEAD, not the clause verb. The native front-end tags a possessive as PRON, so the flank-skip missed
    it and `verbs_to_promote` read it as an entity-like subject — burying the noun as a VERB ("his AMBITION,
    Macbeth murdered …" picked `ambition` as the verb over `murder`, corrupting the whole clause). The guard
    excludes a possessive determiner from being a subject flanker."""

    def test_possessive_governed_noun_not_promoted(self, encoder):
        doc = encoder.nlp("Consumed by his ambition, Macbeth murdered King Duncan.")
        amb = next(t.i for t in doc if t.lemma_ == "ambition")
        assert amb not in verbs_to_promote(doc)      # "his ambition" -> ambition is a NOUN, not a verb

    def test_genuine_buried_verb_still_promotes(self, encoder):
        # POSITIVE control: the guard must not neuter promotion — a real buried verb flanked by entities (no
        # possessive) is still promoted ("Duncan is a king" promotes the copula, the module's own cited case).
        doc = encoder.nlp("Duncan is a king.")
        assert verbs_to_promote(doc)

    def test_real_verb_and_subject_recovered_end_to_end(self, encoder):
        # both fixes compose: possessive-guard makes `murder` the verb, the leading-adjunct rule strips
        # "Consumed by his ambition," so the subject is Macbeth, not "consumed by".
        ev = evaluate_tree(from_trace(encoder.encode("Consumed by his ambition, Macbeth murdered King Duncan.")))
        assert ev.verb == "murder"
        assert "macbeth" in _agent_lemmas(ev)
        assert "ambition" not in _agent_lemmas(ev)

    def test_possessive_np_stays_the_subject_when_it_is_the_subject(self, encoder):
        # "His ambition drove the tyrant" — here the possessive NP IS the subject and `drive` the verb; the
        # noun must NOT be promoted (which would leave the clause verbless / mis-read).
        ev = evaluate_tree(from_trace(encoder.encode("His ambition drove the tyrant.")))
        assert ev.verb == "drive"
        assert "ambition" in _agent_lemmas(ev)


class TestLeadingAdjunctVerbSelection:
    """A coordinated/fronted PARTICIPLE inside a leading adjunct is POS=VERB and comes first ("Consumed by
    X and spurred by Y, Macbeth murders …" → `spur` before `murder`), so the naive first-VERB pick took the
    adjunct's verb. `_select_clause_verb` redirects to the main-clause verb after the comma — but ONLY when
    the first verb is not preceded by its own subject, so a TRAILING adjunct ("Macbeth fled, fearing capture"
    / "Macbeth fled, his sword drawn") keeps its real first verb."""

    def _verb_lemma(self, encoder, text):
        return _select_clause_verb(encoder.encode(text).tokens).lemma

    def test_coordinated_leading_participle_not_taken_as_verb(self, encoder):
        # the real macbeth story sentence: `spurred` (adjunct participle before the comma) must NOT win.
        assert self._verb_lemma(
            encoder,
            "Consumed by his latent ambition and spurred to violence by his wife, "
            "Macbeth murders King Duncan.") == "murder"

    def test_trailing_participial_keeps_its_first_verb(self, encoder):
        # "Macbeth fled, fearing capture" — `fled` is preceded by its subject Macbeth -> main verb, not redirected.
        assert self._verb_lemma(encoder, "Macbeth fled, fearing capture.") == "flee"

    def test_trailing_absolute_keeps_its_first_verb(self, encoder):
        # the over-fire guard: "Macbeth fled, his sword drawn" -> `fled` stays the verb (NOT `drawn`).
        assert self._verb_lemma(encoder, "Macbeth fled, his sword drawn.") == "flee"

    def test_plain_clause_verb_unchanged(self, encoder):
        assert self._verb_lemma(encoder, "Macbeth murders Duncan.") == "murder"

    def test_end_to_end_real_verb_and_subject(self, encoder):
        ev = evaluate_tree(from_trace(encoder.encode(
            "Consumed by his latent ambition and spurred to violence by his wife, "
            "Macbeth murders King Duncan and takes the Scottish throne.")))
        # evaluate_tree returns the CLAUSE_COORD; the left clause is the first predication
        left = ev.left if hasattr(ev, "left") else ev
        assert left.verb == "murder"
        assert "macbeth" in _agent_lemmas(left)
