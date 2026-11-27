"""Probes of GSE's reading through the real encoder: pass 0 of the voice-profiler fix set.

The cases are the constructed sentences of the 2026-10-04 theory audit's lead probes, each stated as the reading GSE
owes at a layer consumers read: a token's surface, lemma and POS; a word's prime signature; the events of the
published contract. The SquishOS voice tool reads exactly these layers. A case GSE does not read yet is a strict xfail
naming its issue, so the fix that lands it fails the xfail and the marker comes off in the same commit. Unmarked cases
are guards against over-correction: a name stays a name, a comparative keeps its stem.
"""

import pytest

from GSE.api import GSEEncoder
from GSE.curation.external_sources.nrc_emotion import EmotionEntry, NRCEmotionParser
from GSE.curation.external_sources.nrc_vad import NRCVADParser
from GSE.curation.lexicon_builder import store
from GSE.curation.lexicon_builder.cells import BANKS, START
from GSE.symbolic import emit_contract, evaluate_tree, from_trace, resolve


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


def _row(encoder, entry_id):
    """One explicit definition's stored signs; homographs are never merged."""
    reading = encoder.lookup_definition(entry_id)
    assert reading["code"] == "IDENTIFIED"
    return {bank: value for bank, value in reading["selected"]["assignments"].items() if value}


def _fixture(entry_id, lemma, pos, values):
    return store.FixtureEntry(entry_id, lemma, pos, "Explicit identity fixture", values)


@pytest.fixture
def word_encoder(tmp_path):
    """Declared signs exercise identity preservation; they are not dictionary gold."""
    path = tmp_path / "word-identities.db"
    store.fixture(
        path,
        [
            _fixture("fixture:inside:spatial", "inside", "adj", {"OUTSIDE": -1}),
            _fixture("fixture:independent:adjective", "independent", "adj", {"CAN": 1}),
            _fixture("fixture:side", "side", "noun", {"SOMETHING": 1}),
            _fixture("fixture:dependent", "dependent", "adj", {"WANT": 1}),
        ],
    )
    with GSEEncoder(path) as instance:
        yield instance


@pytest.fixture
def category_encoder(tmp_path):
    path = tmp_path / "noun-categories.db"
    # No evidence: each definition holds exactly what the authored laws give a noun.
    store.fixture(
        path,
        [
            store.FixtureEntry(f"fixture:noun:{word}", word, "noun", "Explicit noun-category fixture")
            for word in ("rule", "elements", "case", "compassion")
        ],
        closed=True,
    )
    with GSEEncoder(path) as instance:
        yield instance


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


def test_an_adjective_after_a_copula_is_an_adjective(encoder):
    assert _token(encoder, "It is necessary to do this.", "necessary").pos == "ADJ"


def test_an_opening_quote_is_not_a_contraction(encoder):
    assert _token(encoder, "He wrote 'dividing' on the board.", "dividing").lemma == "divide"


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


def test_dislike_is_not_like(encoder):
    like = _token(encoder, "I like it.", "like").word_primitives
    assert _token(encoder, "I dislike it.", "dislike").word_primitives != like


@pytest.mark.parametrize(
    ("sentence", "surface", "entry_id"),
    [
        ("It is inside.", "inside", "fixture:inside:spatial"),
        ("The country is independent.", "independent", "fixture:independent:adjective"),
    ],
)
def test_a_word_keeps_its_own_row(word_encoder, sentence, surface, entry_id):
    token = _token(word_encoder, sentence, surface)
    assert token.lemma == surface
    assert token.lexical_evidence["selected_record"]["entry_id"] == entry_id
    assert dict(token.word_primitives) == _row(word_encoder, entry_id)

    # A noun homograph cannot be unioned into the adjective or selected first.
    other = f"fixture:{surface}:noun"
    store.add_fixtures(word_encoder.conn, [_fixture(other, surface, "noun", {"SOMETHING": 1, "ALIVE": 1})])
    word_encoder.conn.commit()
    ambiguous = _token(word_encoder, sentence, surface)
    assert ambiguous.lemma == surface
    assert ambiguous.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert set(ambiguous.lexical_evidence["candidate_entry_ids"]) == {entry_id, other}
    assert ambiguous.word_primitives == {}
    assert _row(word_encoder, other) == {"SOMETHING": 1, "ALIVE": 1}
    assert _row(word_encoder, entry_id) == dict(token.word_primitives)


def test_an_unknown_word_and_a_designed_zero_are_told_apart(tmp_path):
    path = tmp_path / "explicit-zero.db"
    # The designed zero supplies an explicit zero on every bank. No missing coordinate or real grammatical word is
    # declared zero: the partial fixture keeps every bank at its starting domain.
    store.fixture(
        path,
        [
            _fixture("fixture:zero", "zerofixture", "noun", dict.fromkeys(BANKS, 0)),
            _fixture("fixture:partial", "partialfixture", "noun", {}),
            _fixture("fixture:fall", "fall", "verb", {"HAPPEN": 1}),
        ],
    )
    with GSEEncoder(path) as instance:
        tokens = {token.token: token for token in instance.encode("Zerofixture partialfixture xqzzt fell.").tokens}
    assert tokens["xqzzt"].lexicon_status == "unknown"
    assert tokens["xqzzt"].lexical_evidence["state"] == "no_row"
    assert tokens["fell"].lexicon_status == "found"
    assert tokens["fell"].lexical_evidence["selected_record"]["entry_id"] == "fixture:fall"
    zero = tokens["Zerofixture"]
    assert zero.lexicon_status == "found"
    assert zero.lexical_evidence["state"] == "no_primes"
    assert zero.lexical_evidence["domains"] == {bank: [0] for bank in BANKS}
    partial = tokens["partialfixture"]
    assert partial.lexical_evidence["selection_status"] == "IDENTIFIED"
    assert partial.lexicon_status == "unread"
    assert partial.lexical_evidence["state"] == "unread"
    assert partial.lexical_evidence["domains"] == {bank: store.signs(int(m)) for bank, m in zip(BANKS, START)}


@pytest.mark.xfail(
    strict=True,
    reason="no noun GOOD-0 law (the lead's ruling C, 2026-11-27): F057 ('Can a noun have a sentiment weight to it? Of "
    "course not.') against ruling (c) of 2026-11-25 05:30 (feeling nouns carry their valence) would need a negated "
    "guard, and Rohan called an earlier mass-zero rule slop (2026-11-25 17:56); his decision",
)
@pytest.mark.parametrize("lemma", ["rule", "elements", "case"])
def test_a_neutral_word_carries_no_valence(category_encoder, tmp_path, lemma):
    # #51: native v2 zero is the scale center, not negative v1 valence.
    path = tmp_path / "vad-v2.txt"
    path.write_text(f"term\tvalence\tarousal\tdominance\n{lemma}\t0\t0\t0\n")
    parser = NRCVADParser(str(path))
    assert parser.load()
    native = parser.entries[lemma]
    assert native.native_version == "2" and native.native_scale == (-1.0, 1.0)
    assert native.valence == 0
    assert parser.projection_candidates_for_entry(native) == []
    reading = category_encoder.lookup_definition(f"fixture:noun:{lemma}")["selected"]
    # Noun evaluation zero comes from the explicit category rule, not the
    # absence of an affect candidate. Other missing banks remain unresolved.
    assert reading["domains"]["GOOD"] == [0]
    assert reading["domains"]["FEEL"] == [-1, 0, 1]
    assert "GOOD" not in _row(category_encoder, f"fixture:noun:{lemma}")


@pytest.mark.xfail(
    strict=True,
    reason="no noun GOOD-0 law (the lead's ruling C, 2026-11-27): F057 ('Can a noun have a sentiment weight to it? Of "
    "course not.') against ruling (c) of 2026-11-25 05:30 (feeling nouns carry their valence) would need a negated "
    "guard, and Rohan called an earlier mass-zero rule slop (2026-11-25 17:56); his decision",
)
def test_compassion_is_not_negative(category_encoder):
    # #52: keep opposing affect associations, independent of insertion order.
    parser = NRCEmotionParser()
    forward = parser.projection_candidates_for_entry(EmotionEntry("compassion", {"positive": 1, "sadness": 1}))
    reverse = parser.projection_candidates_for_entry(EmotionEntry("compassion", {"sadness": 1, "positive": 1}))
    assert forward == reverse
    assert forward is not None
    evaluation = next(candidate for candidate in forward if candidate["bank"] == "GOOD")
    assert evaluation["suggested_values"] == [-1, 1]
    assert evaluation["evidence_disposition"] == "ASSOCIATION_OWN_DEFINITION_UNESTABLISHED"
    reading = category_encoder.lookup_definition("fixture:noun:compassion")["selected"]
    assert reading["domains"]["GOOD"] == [0]
    assert reading["domains"]["FEEL"] == [-1, 0, 1]
    assert _row(category_encoder, "fixture:noun:compassion").get("GOOD") != -1
