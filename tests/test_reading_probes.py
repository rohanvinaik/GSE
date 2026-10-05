"""Probes of GSE's reading through the real encoder: pass 0 of the voice-profiler fix set.

The cases are the constructed sentences of the 2026-10-04 theory audit's lead probes, each stated as the reading GSE
owes at a layer consumers read: a token's surface, lemma and POS; a word's prime signature; the events of the
published contract. The SquishOS voice tool reads exactly these layers. A case GSE does not read yet is a strict xfail
naming its issue, so the fix that lands it fails the xfail and the marker comes off in the same commit. Unmarked cases
are guards against over-correction: a name stays a name, a comparative keeps its stem.
"""

import sqlite3
from contextlib import closing

import pytest

from gse.api import GSEEncoder
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _token(encoder, sentence, surface):
    """The one token with this surface in the sentence's trace."""
    tokens = encoder.encode(sentence).tokens
    found = [t for t in tokens if t.token == surface]
    assert len(found) == 1, f"{surface!r} among {[t.token for t in tokens]}"
    return found[0]


def _events(node, negated=False):
    """Every EVENT in a contract as (verb, negated), negated under a NOT."""
    if isinstance(node, list):
        return [event for item in node for event in _events(item, negated)]
    if not isinstance(node, dict):
        return []
    own = [(node.get("features", {}).get("verb"), negated)] if node.get("op") == "EVENT" else []
    return own + _events(node.get("args", []), negated or node.get("op") == "NOT")


def _contract_events(encoder, sentence):
    return _events(emit_contract(evaluate_tree(resolve(from_trace(encoder.encode(sentence)))))["predicate"])


def _row(encoder, lemma):
    """A lemma's stored signature, non-zero values only, in the lexicon this encoder reads."""
    query = (
        "SELECT pv.primitive, pv.value FROM primitive_values pv JOIN lexemes l ON l.id = pv.lexeme_id "
        "WHERE l.lemma = ? AND pv.value != 0"
    )
    with closing(sqlite3.connect(f"file:{encoder.db_path}?mode=ro", uri=True)) as db:
        return dict(db.execute(query, (lemma,)).fetchall())


# ── tokens: the front end ─────────────────────────────────────────────────────────────────────────────────


def test_contracted_am_is_be(encoder):
    tok = _token(encoder, "I'm happy.", "'m")
    assert tok.lemma == "be" and tok.pos in ("AUX", "VERB")


def test_contracted_can_is_can(encoder):
    tok = _token(encoder, "I can't swim.", "ca")
    assert tok.lemma == "can" and tok.pos in ("AUX", "VERB")


def test_contracted_will_keeps_its_verb(encoder):
    assert ("go", False) in _contract_events(encoder, "We'll go.")


def test_cannot_negates_its_verb(encoder):
    assert ("swim", True) in _contract_events(encoder, "Birds cannot swim.")


@pytest.mark.parametrize(
    ("sentence", "lemma"),
    [
        ("It's necessary to do this.", "be"),
        ("It's raining.", "be"),
        ("That's why it works.", "be"),
        ("It's gone.", "have"),
    ],
)
def test_its_is_it_is(encoder, sentence, lemma):
    # A host that never takes a possessive makes 's the verb, and a V-ing word is the progressive, not the perfect (#87).
    assert _token(encoder, sentence, "'s").lemma == lemma


@pytest.mark.parametrize(
    ("sentence", "lemma"),
    [
        ("I'd already gone home.", "have"),
        ("I'd never seen it.", "have"),
        ("I'd go home.", "would"),
        ("I'd be leaving.", "would"),
    ],
)
def test_a_contracted_d_is_read_from_its_verb_past_any_adverb(encoder, sentence, lemma):
    # Before a participle 'd is "had", since "would" never takes one, whatever adverb or negation stands between (#78).
    assert _token(encoder, sentence, "'d").lemma == lemma


@pytest.mark.parametrize("sentence", ["It's not raining.", "It's instead retained as a whole."])
def test_a_contracted_s_before_an_adverb_stays_is(encoder, sentence):
    # 's is read from the next token: past an adverb a participle may be passive ("is retained") as well as perfect.
    assert _token(encoder, sentence, "'s").lemma == "be"


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#76 F-passive: 's before a passive participle reads as has"
)
def test_a_contracted_s_before_a_passive_is_is(encoder):
    assert _token(encoder, "It's retained as a whole.", "'s").lemma == "be"


def test_an_uppercase_contraction_splits(encoder):
    # The fragments split whatever their case (#77, #78).
    assert _token(encoder, "I'M READY.", "'M").lemma == "be"
    assert ("go", False) in _contract_events(encoder, "WE'LL GO.")
    assert ("know", True) in _contract_events(encoder, "I DON'T KNOW.")
    assert ("swim", True) in _contract_events(encoder, "YOU CANNOT SWIM.")


def test_a_name_before_a_mistagged_plural_is_possessive(encoder):
    # The third-singular rule tags "guards" VERB; after a name the 's is the possessive, not "has", and the plural is
    # the possessed noun, so it is no predicate of its own (#87).
    sentence = "Duncan's guards became drunk."
    assert _token(encoder, sentence, "'s").pos == "PART"
    assert _token(encoder, sentence, "guards").pos == "NOUN"
    events = _contract_events(encoder, sentence)
    assert ("become", False) in events and ("guard", False) not in events


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#88 F-copula-adj: after a copula an adjective with any noun sense is tagged NOUN",
)
def test_an_adjective_after_a_copula_is_an_adjective(encoder):
    assert _token(encoder, "It is necessary to do this.", "necessary").pos == "ADJ"


def test_an_opening_quote_is_not_a_contraction(encoder):
    assert _token(encoder, "He wrote 'dividing' on the board.", "dividing").lemma == "divide"


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#94 F-titlecase: every capitalised sentence-initial word is a name"
)
@pytest.mark.parametrize(("sentence", "surface"), [("Consider the cell.", "Consider"), ("Yes, it works.", "Yes")])
def test_a_sentence_initial_common_word_is_not_a_name(encoder, sentence, surface):
    assert _token(encoder, sentence, surface).pos != "PROPN"


@pytest.mark.parametrize(
    ("sentence", "surface"),
    [
        ("Macbeth killed Duncan.", "Macbeth"),
        ("Macbeth killed Duncan.", "Duncan"),
        # A capitalised word followed by another keeps its name reading until the proper-noun list exists (#94,
        # accepted under Rohan's 2026-10-04 22:53 UTC go).
        ("Lady Macbeth slept.", "Lady"),
    ],
)
def test_a_name_stays_a_name(encoder, sentence, surface):
    assert _token(encoder, sentence, surface).pos == "PROPN"


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#79 F-degree: a word is stripped to a shorter word (number -> numb)"
)
@pytest.mark.parametrize(
    ("sentence", "surface"),
    [
        ("The number grew.", "number"),
        ("The inner wall fell.", "inner"),
        ("The forest burned.", "forest"),
        ("The layer holds.", "layer"),
    ],
)
def test_a_word_is_not_stripped_to_a_shorter_word(encoder, sentence, surface):
    assert _token(encoder, sentence, surface).lemma == surface


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#79 F-degree: cuter -> cut (the silent e is lost)")
def test_a_comparative_keeps_its_silent_e(encoder):
    assert _token(encoder, "Rex is cuter.", "cuter").lemma == "cute"


@pytest.mark.parametrize(
    ("sentence", "surface", "lemma"),
    [("The room is cleaner.", "cleaner", "clean"), ("Rex is bigger.", "bigger", "big")],
)
def test_a_comparative_keeps_its_stem(encoder, sentence, surface, lemma):
    # 'cleaner' also has a row of its own (the noun): a rule that never strips a word with its own row breaks this.
    assert _token(encoder, sentence, surface).lemma == lemma


def test_a_participle_after_a_determiner_is_not_the_predicate(encoder):
    assert _token(encoder, "The meaning of the story is clear.", "meaning").pos == "NOUN"
    events = _contract_events(encoder, "The dividing cell moved.")
    assert ("divide", False) not in events and ("move", False) in events


def test_a_participle_after_a_pronoun_keeps_its_verb(encoder):
    # #81's rule covers articles and plain possessives only: a determiner that stands alone as a pronoun, and "her"
    # (also the object pronoun), leave the V-ing/V-ed word its verb reading.
    assert ("agree", False) in _contract_events(encoder, "All agreed.")
    assert ("divide", False) in _contract_events(encoder, "Each divided into two.")
    assert _token(encoder, "I saw her running.", "running").pos == "VERB"


# ── words: signatures and the lexicon ─────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#80 F-neg-prefix: dislike reads as like")
def test_dislike_is_not_like(encoder):
    like = _token(encoder, "I like it.", "like").word_primitives
    assert _token(encoder, "I dislike it.", "dislike").word_primitives != like


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#80 F-neg-prefix: a false negative prefix overrides the word's own row"
)
@pytest.mark.parametrize(
    ("sentence", "surface"), [("It is inside.", "inside"), ("The country is independent.", "independent")]
)
def test_a_word_keeps_its_own_row(encoder, sentence, surface):
    assert dict(_token(encoder, sentence, surface).word_primitives) == _row(encoder, surface)


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#99 E-oov: an unknown word and a designed zero both read {}"
)
def test_an_unknown_word_and_a_designed_zero_are_told_apart(encoder):
    status = {t.token: getattr(t, "lexicon_status", None) for t in encoder.encode("The xqzzt fell.").tokens}
    assert status["xqzzt"] == "unknown"
    assert status["fell"] == "found"
    assert status["The"] not in (None, "unknown")


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#51 L-vad: the v2 VAD lexicon read on the v1 scale votes GOOD -1"
)
@pytest.mark.parametrize("lemma", ["rule", "elements", "case"])
def test_a_neutral_word_carries_no_valence(encoder, lemma):
    assert "GOOD" not in _row(encoder, lemma)


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#52 L-emolex: a GOOD conflict is settled by alphabetical emotion order"
)
def test_compassion_is_not_negative(encoder):
    assert _row(encoder, "compassion").get("GOOD") != -1
