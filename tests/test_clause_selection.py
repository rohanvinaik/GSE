"""The sentence as one constraint problem over word senses (GSE.symbolic.clause_selection)."""

from GSE.symbolic import clause_selection as cs


class _Token:
    def __init__(self, text, pos):
        self.text, self.pos_, self.lemma_ = text, pos, text


class _Encoder:
    """Senses keyed by (lemma, pos); every lookup reads them."""

    def __init__(self, senses):
        self.senses = senses
        self.conn = self

    def execute(self, _sql, params):
        lemma, pos = params
        rows = self.senses.get((lemma, pos), {})
        import json

        return type(
            "R", (), {"fetchall": lambda _s: [(s, json.dumps(c), json.dumps(m)) for s, (c, m) in rows.items()]}
        )()

    def lexical_lookup(self, *_args, **_kwargs):
        return {}


DOG = {
    0: ({"SOMETHING": 1}, ("wordnet:dog:andiron.n.01",)),
    1: ({"ALIVE": 1, "SOMEONE": 1}, ("wordnet:dog:cad.n.01",)),
    2: ({"ALIVE": 1, "BODY": 1}, ("wordnet:dog:dog.n.01",)),
}


def test_a_person_typed_adjective_keeps_its_nouns_someone_and_creature_senses():
    encoder = _Encoder({("happy", "adj"): {0: ({"FEEL": 1}, ("wordnet:happy:happy.a.01",))}, ("dog", "noun"): DOG})
    doc = [_Token("the", "DET"), _Token("happy", "ADJ"), _Token("dog", "NOUN")]
    assert cs.solve(encoder, doc) == {2: frozenset({"wordnet:dog:cad.n.01", "wordnet:dog:dog.n.01"})}


def test_a_predicate_sense_without_a_person_typed_bearer_restricts_nothing():
    encoder = _Encoder(
        {
            ("happy", "adj"): {
                0: ({"FEEL": 1}, ("wordnet:happy:happy.a.01",)),
                1: ({"GOOD": 1}, ("wordnet:happy:felicitous.s.02",)),
            },
            ("dog", "noun"): DOG,
        }
    )
    doc = [_Token("the", "DET"), _Token("happy", "ADJ"), _Token("dog", "NOUN")]
    assert cs.solve(encoder, doc) == {}


def test_a_domain_is_never_emptied():
    encoder = _Encoder({("happy", "adj"): {0: ({"FEEL": 1}, ("a",))}, ("box", "noun"): {0: ({"SOMETHING": 1}, ("b",))}})
    doc = [_Token("happy", "ADJ"), _Token("box", "NOUN")]
    assert cs.solve(encoder, doc) == {}
